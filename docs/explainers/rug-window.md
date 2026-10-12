# Rug Window

> 상태: **초안** (계획 승인 시점). 구현이 동작하면 실제 코드 기준으로 갱신한다.

## 1. 개요

바탕화면의 지저분한 파일들을 **가상의 러그로 덮는** Windows 데스크톱 앱.
GitHub Next의 Terkel이 만든 macOS 앱에서 아이디어를 가져왔다.

MVP 범위: 실행하면 3D 천 러그가 바탕화면 위로 떨어져 주름지며 펼쳐지고, 마우스로 끌어 옮길 수 있다.
파일은 실제로 옮기지 않고 **시각적으로만 덮는다**. 파일 개수에 따른 불룩함은 MVP 이후에 한다.

## 2. 배경 지식

### 창의 Z-order (앞뒤 순서)

Windows의 모든 최상위 창은 앞뒤 순서 목록에 들어 있다.

```
[맨 앞]  다른 앱 창들 (브라우저, 에디터 ...)
         ── 러그 창 (Progman 바로 앞에 붙어 있어야 함)
[맨 뒤]  Progman / WorkerW  ← 바탕화면 아이콘 + 배경화면
```

- `SetWindowPos(hwnd, insert_after, ...)`의 두 번째 인자는 "어디에 세울지"다. 특정 창의 hwnd를 넣으면 **그 창 바로 뒤**, `HWND_BOTTOM`을 넣으면 **줄 맨 뒤**.
- ⚠ **정정**: 처음 계획은 `HWND_BOTTOM`이었지만, Progman도 최상위 창이라 러그가 바탕화면 **뒤**로 숨어버릴 수 있다(미검증). 대안: Progman 바로 앞 창(`GetWindow(progman, GW_HWNDPREV)`)의 뒤에 세운다. 구현 때 둘 다 눈으로 확인한다.
- 사용자가 러그를 클릭하면 OS가 러그를 **활성화하면서 맨 앞으로** 끌어올린다. 대응 순서: ① `WS_EX_NOACTIVATE`로 활성화 자체를 막기 → 안 되면 ② `WM_WINDOWPOSCHANGING`을 가로채 위치를 바꿔치기 → 최후 수단 ③ 클릭 후 다시 내려보내기(깜빡임).
- `WorkerW`에 자식 창으로 붙이는 방식(라이브 배경화면 앱들이 쓰는 방식)은 아이콘 **뒤**로 들어가서 아이콘을 덮을 수 없다.

### 창 스타일과 Qt 옵션

창 스타일은 **비트 스위치 묶음**이다. 하나만 켤 때는 반드시 읽고 → OR로 더하고 → 쓴다.

```python
style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)
```

Qt 옵션으로 되는 건 Qt로 하고, `desktop.py`에는 Qt가 못 하는 것만 남긴다.

| 필요한 것 | 방법 |
|---|---|
| 테두리 없애기 | `Qt.FramelessWindowHint` |
| 작업표시줄에서 숨기기 | `Qt.Tool` (`WS_EX_TOOLWINDOW`를 켬) |
| Progman 바로 앞에 세우기 | `desktop.py` (Win32 직접) |
| 클릭해도 앞으로 안 나오기 | `desktop.py`의 `WS_EX_NOACTIVATE` 또는 Qt 옵션 (검증 필요) |

### 투명 창

Qt에서 `FramelessWindowHint`로 테두리를 없애고 `WA_TranslucentBackground`를 켜면 픽셀마다 알파값을 가진 창이 된다.
러그가 그려지지 않은 부분은 알파 0이라서 뒤에 있는 바탕화면이 보인다.

### Verlet 적분으로 천 만들기

천을 격자 모양의 **입자**와, 입자 쌍 사이 거리를 유지하려는 **제약(막대)**으로 나타낸다.

매 프레임 순서:
1. **적분**: `새 위치 = 현재 + (현재 - 이전) * 감쇠 + 가속도 * dt²`
   - 속도를 따로 저장하지 않고 "이전 위치와의 차이"를 속도로 쓴다. 그래서 위치를 강제로 고쳐도(충돌, 제약) 속도가 자연스럽게 따라온다.
2. **제약 풀기**: 각 막대마다 현재 길이와 원래 길이의 차이를 구해, 양 끝 입자를 절반씩 당기거나 민다. 이걸 여러 번(예: 8회) 반복하면 전체가 수렴한다.
3. **충돌**: 바닥(z=0) 아래로 내려간 입자는 바닥 위로 올린다.

막대 종류:

| 종류 | 연결 | 역할 |
|---|---|---|
| 구조 | 가로·세로 이웃 | 천이 늘어나지 않게 |
| 전단 | 대각선 이웃 | 평행사변형으로 찌그러지지 않게 |
| 굽힘 | 두 칸 건너 | 접힘에 저항 → 주름 크기 결정 |

### 법선과 Lambert 조명

입자 격자를 삼각형으로 나누고, 각 꼭짓점의 **법선**(표면이 향하는 방향)을 주변 면들의 평균으로 구한다.
밝기 = `max(0, 법선 · 빛 방향)`. 주름진 곳은 법선이 기울어져 어둡게 보인다. 천의 입체감은 전부 이 음영에서 나온다.

## 3. 구조

### 파일별 역할

**앱 코드 (`src/rug_window/`)**: 데이터가 흐르는 순서대로

| 파일 | 한 줄 역할 | 비유 | 알고 있는 세계 |
|---|---|---|---|
| `__main__.py` | 앱을 조립하고 이벤트 루프를 돌린다 | 미술실 문 열기 | Qt (조립만) |
| `rug_widget.py` | 모든 걸 연결하는 중심: 타이머로 천을 움직이고 다시 그리고, 드래그를 받는다 | 화가 | Qt |
| `desktop.py` | Qt가 못 하는 Win32 일: Progman 바로 앞에 세우기, 클릭해도 앞으로 안 나오기 | 줄 서기 담당 | Win32 (hwnd만) |
| `cloth.py` | 구슬과 막대로 천의 움직임을 계산한다 | 계산 노트 | numpy만 |
| `renderer.py` | 구슬 위치를 받아 음영 있는 천으로 그린다 | 물감과 붓 | OpenGL |

데이터 흐름: `QTimer(16ms)` → `ClothSimulation.step()` → `positions` 배열 → `update()` → `paintGL` → `ClothRenderer.draw()` → 화면

**프로젝트 설정**

| 파일 | 역할 |
|---|---|
| `pyproject.toml` | 프로젝트 정보, 의존성 허용 범위, ruff/pytest 설정 |
| `uv.lock` | 실제 설치된 정확한 버전 (uv가 자동 관리, 커밋 필수) |
| `.gitattributes` | 텍스트 파일 줄바꿈을 LF로 통일 |
| `.gitignore` | `.venv/`, `__pycache__/` 등 커밋 제외 |

**Claude 협업 규칙**

| 파일 | 역할 |
|---|---|
| `CLAUDE.md` | Claude가 지킬 코드·네이밍·커밋·워크플로우 규칙 |
| `.claude/settings.json` | Plan 모드 기본값, `gh pr merge` 차단 |
| `docs/explainers/rug-window.md` | 이 문서: 계획, 배경 지식, 설계 결정, 학습 노트 |

## 4. 설계 결정

| 선택 | 버린 대안 | 이유 |
|---|---|---|
| PySide6 | PyQt6, pyglet, tkinter | 투명 창, OpenGL, 트레이를 모두 지원하고 LGPL |
| `pyside6-essentials`만 의존 | `pyside6` 전체 | 쓰는 모듈(QtGui, QtWidgets, QtOpenGL, QtOpenGLWidgets)이 전부 essentials에 있음. `.venv` 769MB → 327MB |
| QOpenGLWidget + PyOpenGL | moderngl, Qt3D | 레이어가 가장 적고 자료가 많음 |
| numpy로 직접 Verlet 구현 | PyBullet, Taichi | 가볍고, 원리를 직접 이해할 수 있음 |
| Progman 바로 앞에 세우기 | WorkerW 부착, HWND_BOTTOM | WorkerW는 아이콘 뒤. HWND_BOTTOM은 Progman보다 뒤로 갈 수 있음 (검증 예정) |
| 함수명 `place_above_desktop` | `place_behind`, `pin_to_desktop_layer` | 호출하는 줄만 봐도 *왜* 부르는지 보임 |
| 작업표시줄 숨김은 `Qt.Tool` | `desktop.py`에서 직접 스타일 수정 | 더 간단하고, 스타일 덮어쓰기 실수 위험이 없음. 창 성질은 창을 만드는 쪽이 정함 |
| `positions`는 읽기 전용 뷰 | 내부 배열 그대로, 복사본 | 매 프레임(60fps) 읽어도 복사가 없음. 바깥에서 실수로 쓰면 에러가 나서 시뮬레이션이 몰래 망가지지 않음 |
| 잘못된 입력은 `ValueError` | 검증 없이 문서로만 | `rows`/`cols` < 3이면 굽힘 제약(2칸 이웃)을 못 만들고, `spacing` ≤ 0이면 천이 성립하지 않음. 이상하게 동작하기보다 바로 멈추는 게 원인 찾기 쉬움 |
| Progman 없음 → `OSError`, 앞 창 없음 → `HWND_TOP` | 둘 다 조용히 무시 | 바탕화면을 못 찾는 건 진짜 고장이라 알려야 함. 앞 창이 없으면 맨 앞이 곧 Progman 바로 앞 |
| Win32 함수는 창을 띄운 **뒤** 호출 | `__init__`에서 호출 | 진짜 창(hwnd)은 show 이후에 생기고, Qt가 show 중에 스타일을 다시 덮어쓸 수 있음 |
| Win32 헬퍼 호출은 `main()`이 맡음 | `RugWidget` 안에서 (`showEvent`) | 위젯은 Win32를 모르게 두고, "show 다음에 부른다"는 순서를 조립하는 곳 한 군데에서 보이게 |
| 예외는 `OSError`로 통일 | `pywintypes.error` 그대로 | pywin32 에러는 `OSError`가 아니다(확인함). `FindWindow`는 실패해도 0을 돌려줄 뿐이라 직접 확인해서 올린다 |
| Progman 앞으로 걸어가며 topmost 창 건너뛰기 | 바로 앞 창 뒤에 세우기 | 바로 앞이 topmost 창(작업표시줄 등)이면 그 뒤에 선 러그도 topmost가 되어 모든 앱 위로 뜬다 (미검증). 없으면 `HWND_NOTOPMOST` |
| 왼쪽 버튼으로만 드래그, `mouseReleaseEvent` 없음 | release 핸들러로 드래그 종료 | move 이벤트는 버튼을 누를 때만 온다. 대신 오른쪽 버튼으로 끌리는 걸 막는다 |
| 렌더러는 device pixel, 변환은 위젯에서 | 각자 알아서 | HiDPI에서 logical × `devicePixelRatio()` = device. 변환을 한 곳에서만 |
| ruff `"D"` 규칙 켬 | 설정만 두기 | `pydocstyle` 설정은 `"D"`가 `select`에 없으면 아무 일도 안 한다 |
| 인덱스는 `__init__`에서 한 번, 위치·법선만 매 프레임 업로드 | 매 프레임 전부 업로드 | 격자 모양(어느 구슬끼리 잇는지)은 안 바뀐다 |
| 빛을 비스듬히 (`LIGHT_DIRECTION`) | 바로 위 | 바로 위면 평평한 러그가 전부 같은 밝기라 잔주름이 안 보인다 |
| `ClothRenderer.release()` + 닫힐 때 위젯이 호출 | 가비지 컬렉션에 맡기기 | GPU 객체는 Python이 지워도 반납되지 않고, 컨텍스트가 활성일 때만 반납 가능 |
| `draw()` 입력 검증 (`ValueError`) | 검증 없이 업로드 | 모양·타입이 틀려도 GPU는 불평 없이 엉뚱하게 그린다 |

## 5. 주의할 점 / 열린 질문

- [ ] QOpenGLWidget + 투명 배경이 Windows에서 제대로 합성되는지 (미검증)
- [ ] 다른 창을 모두 최소화했을 때 Progman 앞이 topmost 창이 되는지, topmost 건너뛰기가 러그를 앱 위로 띄우지 않는지 (PR #6 리뷰, 미검증)
- [ ] Qt `resizeGL`이 정말 logical pixel을 주는지 (미검증)
- [ ] `HWND_BOTTOM`이 Progman보다 뒤로 가는지, Progman 바로 앞에 세우는 방식이 동작하는지 (미검증)
- [ ] 배경화면 슬라이드쇼 등 일부 상태에서는 아이콘(`SHELLDLL_DefView`)이 Progman이 아닌 `WorkerW` 밑에 있을 수 있음. 그러면 "Progman 바로 앞"이 아이콘 뒤가 될 수도 있음 (리뷰어 지적, 미검증)
- [ ] `GRAVITY = -9.8`은 1 러그 단위 = 1m 가정. 화면에서 떨어지는 속도가 어색하면 조정 (미검증)
- [ ] 클릭 시 앞으로 끌려나오는 걸 `WS_EX_NOACTIVATE`로 막을 수 있는지, 드래그와 충돌하지 않는지 (미검증)
- [ ] Qt가 투명 창에 어떤 확장 스타일을 켜는지 (스타일 값 출력으로 확인 예정)
- [ ] 창의 투명한 여백이 클릭을 통과시키는지 (막으면 러그 근처 아이콘이 클릭되지 않음, 미검증)
- [ ] Win+D(바탕화면 보기)를 누르면 러그도 숨겨질 가능성이 큼 (MVP에서는 허용)
- [ ] numpy 성능: 40×30 격자에서 60fps가 나오는지 (미측정)

## 6. 학습 노트

### 스켈레톤 복습 (2026-10-12)

**실행 흐름**
- `python -m rug_window` → 패키지의 `__main__.py`를 직접 실행 → `__name__ == "__main__"`
- `rug-window` 명령 (`[project.scripts]`) → `from rug_window.__main__ import main` 후 `sys.exit(main())` → import이므로 `if __name__ == "__main__":` 블록은 **실행되지 않음**
- 결론: 시작 로직은 전부 `main()` 안에 둔다. `if` 블록에 넣으면 `rug-window` 명령에서 빠진다.

**`pyproject.toml` vs `uv.lock`**

| 파일 | 내용 | 관리 |
|---|---|---|
| `pyproject.toml` | 허용 범위 (`numpy>=2.0`) | 사람 |
| `uv.lock` | 실제 설치된 정확한 버전 (`numpy==2.5.4`) | uv 자동 |

- lock 파일을 커밋하지 않으면 다른 PC에 다른 버전이 깔려 "내 PC에선 되는데" 버그가 생긴다 → 앱 프로젝트는 lock을 커밋한다.
- `dependencies`는 실행에 필요, `dev` 그룹은 개발에만 필요.
- `# noqa: N802`: ruff의 `N`(네이밍) 규칙 중 하나를 그 줄에서만 끔. Qt 메서드명은 Qt가 정한 것이라 바꿀 수 없다.

**`src/` 구조**
- 모듈 = `.py` 파일, 패키지 = 모듈을 담은 폴더, `__init__.py` = 패키지 표시
- flat 구조는 테스트가 설치본 대신 옆 폴더를 import해서 패키징 오류를 놓칠 수 있다.
- `src/` 구조는 반드시 설치본을 거친다. `uv sync`의 editable 설치는 `.venv/Lib/site-packages/_editable_impl_rug_window.pth`에 `src/` 경로를 적어 링크만 건다 → 코드 수정이 바로 반영된다.

**뼈대의 구성 요소**
- 타입 힌트: 실행 중 검사하지 않는 **표시**. 사람·에디터·mypy를 위한 것.
- docstring: 실행 중에도 남는 설명 (`help()`, 에디터 툴팁). 구현 전에 의미를 확정한다 (예: `spacing` = 막대 제약의 "쉬는 거리").
- `raise NotImplementedError` vs `pass`: `pass`는 `None`을 돌려줘서 엉뚱한 곳에서 터지고, `NotImplementedError`는 비어 있는 그 자리에서 바로 멈춘다.

**울타리 기둥 오류 (fencepost error)** ← 3단계 테스트 후보
- 입자 n개 사이 간격은 n−1개.
- `ClothSimulation(rows=40, cols=30, spacing=0.1, ...)` → 입자 1200개, 가로(x) = 29 × 0.1 = **2.9**, 세로(y) = 39 × 0.1 = **3.9** (3.0 / 4.0 아님)

### 데스크톱 창 기초 (2026-10-12)

**hwnd와 관심사의 분리**
- 창은 OS가 관리하는 데이터이고, hwnd는 그걸 가리키는 숫자(핸들)다. 값 자체에는 의미가 없고 OS에 넘겨주기만 한다.
- Win32 API는 Qt 위젯을 모르고 hwnd만 안다. 변환(`int(widget.winId())`)은 Qt 쪽에서 한 번만 한다.
- `desktop.py`는 hwnd만 받으므로 Qt를 몰라도 된다 → Qt를 tkinter로 바꿔도 `rug_widget.py`만 고치면 된다.

**스타일 = 비트 스위치**
- `|`(OR)로 켜고 `& ~`로 끈다.
- `SetWindowLong`은 통째로 덮어쓴다. 읽지 않고 `WS_EX_TOOLWINDOW`만 넣으면 다른 스위치(예: Qt가 투명 창에 켜둔 것)가 전부 꺼진다.

**Z-order**
- 최상위 창은 앞뒤 한 줄로 서 있다. 클릭하면 활성화되며 맨 앞으로 끌려나온다 → 러그가 다른 창을 가린다.
- `SetWindowPos`의 마지막 인자도 비트 OR: `SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE`.

**설계 변경**
- `hide_from_taskbar()`는 지우고 `Qt.Tool`을 쓴다 (더 간단하고 덮어쓰기 위험 없음).

### `__main__.py` / `rug_widget.py` 리뷰 (2026-10-12)

**`main()`이 할 일**: ① `QSurfaceFormat` 알파 설정 (`QApplication`보다 먼저) → ② `QApplication` (프로세스에 하나) → ③ `RugWidget()` → ④ `show()` (요청만) → ⑤ `return app.exec()`

**이벤트 루프**
- `app.exec()` 안에서 "OS 이벤트 꺼내기 → 담당 위젯에 전달"을 반복한다. 앱이 끝나야 돌아온다 → 그 다음 줄은 종료 시에만 실행된다.
- `paintGL`, `mousePressEvent` 등은 우리가 부르지 않고 이벤트 루프가 부른다 (콜백).

**Ctrl+C 함정** (MVP 종료 방법 = Ctrl+C)
- Python은 SIGINT를 Python 코드 실행 중에만 확인하는데, `app.exec()`는 대부분 C++에서 돌아서 Ctrl+C가 무시된다.
- 해결: `signal.signal(signal.SIGINT, signal.SIG_DFL)` → OS 기본 동작(즉시 종료). 대가: 정리 코드가 실행되지 않음. 트레이를 넣을 때 `app.quit()` 경로를 따로 만든다.

**플립북 비유: OpenGL 콜백**

| 실제 | 비유 |
|---|---|
| `RugWidget` | 화가 |
| Qt 이벤트 루프 | 미술실 선생님 |
| OpenGL 컨텍스트 | 책상에 깔린 도화지와 물감 |
| `__init__` | 출근: 알람(타이머)만 맞춤. 도화지 없음 → 렌더러 못 만듦 |
| `initializeGL` | 선생님이 도화지를 깔아줌 → 물감 섞기(렌더러 생성), 딱 한 번 |
| `resizeGL` | 도화지 크기 변경 |
| `update()` | 손 들기: "다음 장 그릴게요" |
| `paintGL` | 선생님이 도화지를 깔아준 뒤 "자, 그려" |

- 규칙: `paintGL()`을 직접 부르지 않는다. 컨텍스트 준비가 빠져서 엉뚱한 곳에 그린다. 항상 `update()`.
- 16ms 타이머 → `cloth.step()` → `update()` → `paintGL` ≈ 초당 60장.

**드래그**
- 누를 때 `잡은 거리 = 마우스 - 창 왼쪽 위`, 움직일 때 `창 왼쪽 위 = 마우스 - 잡은 거리`.
- 잡은 거리를 빼먹으면 창이 잡은 거리만큼 순간이동해서 마우스가 창 모서리에 붙는다.
- 예: 창 (50, 80), 클릭 (150, 130) → 잡은 거리 (100, 50). 마우스 (250, 230) → 창 (150, 180).
- `mouseReleaseEvent`는 MVP에 불필요: Qt는 버튼을 누르고 있을 때만 `mouseMoveEvent`를 보낸다.
- 창(투명 필름)은 러그보다 커야 한다: 떨어지며 펄럭이는 부분이 잘리지 않도록.

### `desktop.py` 리뷰 (2026-10-12)

- 줄 서기 비유: `HWND_BOTTOM` = "줄 맨 뒤" → Progman보다 뒤로 갈 수 있음. 대신 "Progman 바로 앞 사람 뒤에 서기":
  `FindWindow("Progman", None)` → `GetWindow(progman, GW_HWNDPREV)` (한 칸 **앞** 사람) → `SetWindowPos(hwnd, 그 사람, ...)`
- 뼈대 변경 예정: `hide_from_taskbar` 삭제 (`Qt.Tool`), `send_to_bottom` → `place_above_desktop`, `disable_activation` 추가 (`WS_EX_NOACTIVATE`), 모듈 docstring의 `HWND_BOTTOM` 설명 정정.

### `cloth.py` A: 천 = 구슬 + 막대 (2026-10-12)

- 진짜 천은 계산할 수 없으니 **구슬(입자)**과 **막대(제약)**로 단순화한다.
- 구슬: `(x, y, z)` 위치만 가진다 → `positions` 모양 `(rows, cols, 3)`.
- 막대: "우리 둘은 이 거리만큼 떨어져 있자"는 약속. 원래 길이 = `spacing`.

| 막대 | 잇는 곳 | 없으면 |
|---|---|---|
| 구조 | 가로·세로 이웃 | 고무줄처럼 늘어남 |
| 전단 | 대각선 이웃 | 네모가 마름모로 찌그러짐 |
| 굽힘 | 두 칸 건너 | 종이처럼 칼같이 접힘. 강하면 두꺼운 담요, 약하면 실크 같은 주름 |

- 시작 상태: 모든 구슬이 `drop_height`에 평평하게 → `step()`마다 중력으로 떨어짐.
- **구조 막대 개수** (울타리 기둥 원리): 가로 = `rows × (cols − 1)`, 세로 = `cols × (rows − 1)`.
  예: `rows=3, cols=4` → 가로 3×3 = 9, 세로 4×2 = 8, **합계 17**. ← 3단계 테스트 후보

### `cloth.py` B: 다음 위치 예측하기 / Verlet (2026-10-12)

- 비유: 공 연속 사진 두 장 → "지난번에 움직인 만큼 또 움직인다" + 중력이 이번 장에 추가로 당기는 양.
- `새 위치 = 현재 + (현재 − 이전) × 감쇠 + 가속도 × dt²`

| 조각 | 의미 |
|---|---|
| `현재 − 이전` | 속도 (따로 저장하지 않음) |
| `× 감쇠` (예: 0.99) | 공기 저항. 없으면 영원히 출렁임 |
| `가속도 × dt²` | 중력. 이게 있어야 점점 빨라짐 |

- 속도 대신 **이전 위치**를 저장하는 이유: 막대 맞추기·충돌로 구슬을 억지로 옮기면 그만큼이 다음 속도에 저절로 반영된다 → 코드가 짧고 잘 안 터진다.
- 예제 (감쇠 없음, 중력 −0.01, 이전 5.0, 지금 4.9):

| 장 | 높이 | 내려간 거리 |
|---|---|---|
| 지금 | 4.9 | 0.1 |
| 1 | 4.79 | 0.11 |
| 2 | 4.67 | 0.12 |
| 3 | 4.54 | 0.13 |

- 흔한 실수: 중력 항을 빼먹으면 4.8, 4.7, ...처럼 등속 운동이 되고, 처음 속도가 0이면 천이 **공중에 멈춰 있다**. ← 3단계 테스트 후보 ("step 후 z가 줄어드는가", "내려가는 거리가 매번 늘어나는가")

### `cloth.py` C: 막대 길이 지키기 / 제약 (2026-10-12)

- B만 하면 구슬이 각자 떨어지는 "모래알 비"가 된다. 막대가 구슬을 천으로 묶는다.
- 비유: 1m 줄자를 잡은 두 친구. **차이를 반으로 나눠 둘이 똑같이** 다가가거나 멀어진다.
  - 예: 원래 길이 1.0, A = 0.0, B = 1.4 → 0.4 초과 → 각 0.2씩 → A = 0.2, B = 1.2 ← 3단계 테스트 후보
- 한 막대를 맞추면 이웃 막대가 틀어진다 → 전체를 여러 번(예: 8회) 반복해서 수렴시킨다. 적으면 고무줄처럼 늘어나고, 많으면 느리다.
- 바닥 충돌: `z < 0`인 구슬은 `z = 0`으로. 이전 위치는 그대로라 아래로 가던 속도가 저절로 사라진다 (Verlet 장점).
- `step()` 순서: ① Verlet 예측 → ② 막대 맞추기 × N → ③ 바닥 충돌

### `cloth.py` 뼈대 리뷰 (2026-10-12)

- `Attributes:`의 `positions` 설명 삭제 → 프로퍼티 docstring에만 둔다 (중복은 한쪽만 고쳐져 어긋난다).
- 숨은 숫자는 모듈 상수로: `DAMPING`, `GRAVITY`, `CONSTRAINT_ITERATIONS`. 테스트에 필요해지면 그때 생성자 인자로 올린다 (premature abstraction 피하기).
- `dt`는 **고정값 1/60초**로 넘긴다.
  - 이유: Verlet은 "지난번 움직인 거리"를 재사용한다. 사진 간격이 16ms → 32ms로 두 배가 되면 실제로는 두 배를 움직여야 하는데 Verlet은 지난번(16ms) 거리만큼만 움직인다 → 갑자기 느려진다. 반대로 간격이 줄면 너무 많이 움직여서 에너지가 생기고 천이 터질 수 있다.
  - 대가: 컴퓨터가 버벅이면 애니메이션이 조금 느려질 뿐, 천은 안정적이다.

### PR #6 리뷰 반영 (2026-10-12)

ECC `python-reviewer`로 리뷰하고 Claude가 다시 확인했다.

- **pywin32 예외**: `pywintypes.error`의 부모는 `Exception`이다. `OSError`가 아니다. 그래서 문서에 `OSError`라고 쓰려면 직접 바꿔서 올려야 한다.
- **줄 서기 함정**: Progman 바로 앞 사람이 "항상 맨 앞" 무리(topmost)일 수 있다 → 그 뒤에 서면 나도 그 무리가 된다 → 앞으로 걸어가며 topmost는 건너뛴다.
- **리뷰어와 다르게 판단한 것**: `mouseReleaseEvent`는 추가하지 않았다. 근거는 "Qt는 버튼을 누를 때만 move를 보낸다". 대신 "왼쪽 버튼일 때만 이동"을 명시했다. 리뷰어 의견을 그대로 받지 않고 근거를 대서 반박할 수 있다.
- **스위치는 있는데 전원이 꺼진 설정**: `[tool.ruff.lint.pydocstyle]`는 `"D"`를 켜야 동작한다. 켠 뒤 docstring 없는 함수에 `D103`이 뜨는 것을 확인했다.
- `renderer.py`의 GPU 정리(`release()`)와 `draw()` 입력 검증은 `renderer.py` 리뷰 때 다룬다.

### `renderer.py` 학습과 리뷰 (2026-10-12)

**A. 점 잇기**
- GPU는 삼각형만 칠한다. 격자의 네모 1칸 = 삼각형 2개 → 메시.
- 점 잇기 그림책: ① 점 위치(`positions`, 매 프레임 바뀜) ② 어느 점끼리 이을지 번호 목록(인덱스, 안 바뀜).
- 개수 (울타리 기둥 원리):

| | 공식 | rows=3, cols=4 | rows=40, cols=30 |
|---|---|---|---|
| 구슬 | `rows × cols` | 12 | 1200 |
| 네모 칸 | `(rows − 1) × (cols − 1)` | 6 | 1131 |
| 세모 | `2 × (rows − 1) × (cols − 1)` | 12 | 2262 |

- 흔한 실수: 구슬 개수(12)를 칸 개수로 착각. ← 렌더러 테스트 후보 ("인덱스의 삼각형 수")

**B. 법선과 조명**
- 손전등과 구겨진 종이: 빛을 정면으로 받는 면은 밝고, 비스듬하면 어둡다 → 주름이 보인다.
- 법선 = 면이 바라보는 방향(면에 꽂은 이쑤시개). 밝기 = `max(0, 법선 · 빛)`.
- 천이 움직이면 법선도 바뀌므로 매 프레임 다시 계산한다.
- 평평한 러그 + 바로 위 빛 = 전체가 같은 밝기 → 빛을 비스듬히 둔다.

**C. GPU 외주 공장**

| 실제 | 비유 |
|---|---|
| 셰이더 | 공장 직원에게 주는 작업 지시서 (`__init__`에서 컴파일) |
| 버퍼 | 공장에서 빌린 창고 칸 (위치, 법선, 번호 목록) |
| `release()` | 창고 반납. 컨텍스트가 활성일 때만 가능 → `aboutToBeDestroyed` → `makeCurrent()` → `release()` → `doneCurrent()` |

- `draw()` 입력 검사: 모양 `(rows, cols, 3)`, `float32`(numpy 기본은 `float64`라 실수하기 쉬움), C-contiguous(한 덩어리로 복사).
