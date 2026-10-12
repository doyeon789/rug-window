# ECC Setup

> 상태: **구현 완료** (ECC v2.2.3 기준)

## 1. 개요

[ECC](https://github.com/affaan-m/ECC)는 Claude Code에 스킬, 에이전트, 훅을 한꺼번에 추가해 주는 제3자 플러그인 모음이다.
이 문서는 이 저장소에 ECC를 어떻게 설정했는지와, 왜 그렇게 정했는지를 적는다.

참고한 글: [gymcoding — ECC 설치·사용 가이드](https://www.gymcoding.co/articles/ecc-claude-code-install-usage-guide)

이번에 한 일은 세 가지다.

1. 플러그인을 켰다. `.claude/settings.json`의 `enabledPlugins`에 `"ecc@ecc": true`를 넣었다.
2. ECC 규칙 파일 중 이 프로젝트와 맞는 것만 골라 `.claude/rules/ecc/`에 복사했다.
3. GateGuard 훅을 껐다. 이건 개인 설정 파일(`.claude/settings.local.json`)에서 했고 커밋하지 않는다.

## 2. 배경 지식

### 플러그인을 이루는 네 가지

| 구성 요소 | 하는 일 | 비유 |
|---|---|---|
| 스킬 | `/ecc:plan`처럼 필요할 때 불러 쓰는 작업 설명서 | 서랍 속 요리 레시피 |
| 에이전트 | 특정 역할을 맡는 하위 Claude (예: `ecc:python-reviewer`) | 불러서 일을 맡기는 전문가 |
| 훅 | 도구를 쓰기 전이나 후에 **자동으로** 실행되는 스크립트 | 현관 센서등: 지나가면 저절로 켜짐 |
| 규칙(rules) | 세션마다 Claude가 읽는 지침 문서 | 교실 벽에 붙은 반 규칙 |

### 규칙은 자동으로 깔리지 않는다

플러그인을 설치해도 `rules/` 폴더는 배포되지 않는다. 그래서 직접 복사해야 한다.
원본은 플러그인 캐시에 이미 있으므로 `git clone`은 필요 없었다.

```
~/.claude/plugins/cache/ecc/ecc/2.2.3/rules/
```

### 훅 프로필과 끄는 방법

ECC 훅에는 강도별 프로필이 있다. 끄는 방법은 세 가지다.

- **프로필 바꾸기**: 환경변수 `ECC_HOOK_PROFILE`에 `minimal`, `standard`(기본값), `strict` 중 하나를 넣는다.
- **훅 하나만 끄기**: `ECC_DISABLED_HOOKS`에 훅 ID를 쉼표로 이어 적는다.
- **GateGuard만 끄기**: `ECC_GATEGUARD=off`. 전용 스위치이며, `scripts/hooks/gateguard-fact-force.js`에서 이 값을 읽는 것을 확인했다.

## 3. 구조

```
.claude/
├── settings.json           # enabledPlugins: ecc@ecc  (커밋)
├── settings.local.json     # env.ECC_GATEGUARD=off   (개인용, 커밋 안 함)
└── rules/ecc/
    ├── common/   code-review, coding-style, git-workflow, hooks,
    │             patterns, performance, security
    └── python/   coding-style, hooks, patterns, security
```

## 4. 설계 결정

### 넣지 않은 규칙 파일

| 파일 | 뺀 이유 |
|---|---|
| `common/testing.md` | "Claude가 테스트를 먼저 쓰는 TDD + 커버리지 80%"를 강제한다. CLAUDE.md의 "테스트 케이스는 사용자가 설계한다"와 충돌한다. |
| `common/development-workflow.md` | 같은 TDD 강제에 더해 PRD 같은 추가 문서를 요구한다. |
| `common/agents.md` | 사용자에게 묻지 않고 에이전트를 바로 실행하라고 한다. 이해를 우선하는 이 프로젝트의 흐름과 맞지 않는다. |
| `python/testing.md` | `common/testing.md`를 확장한 파일이다. |
| `python/fastapi.md` | 이 프로젝트와 관련이 없다. |

### 전역 대신 프로젝트에 둔 이유

참고한 글은 `~/.claude/rules/ecc/`(전역)에 두라고 권한다. 이 저장소에서는 프로젝트 안에 두었다.

- 다른 프로젝트에는 영향을 주지 않는다.
- git에 남기 때문에 어떤 규칙을 썼는지 리뷰하고 되돌릴 수 있다.

### GateGuard만 끈 이유

GateGuard는 세션에서 처음 명령을 실행하거나 파일을 수정할 때마다 "확인 사항을 먼저 적어라"라며 작업을 막는다.
계획 모드와 CLAUDE.md 규칙이 이미 비슷한 확인 역할을 하고 있어서, 중복으로 걸리는 단계만 늘어났다.
위험한 명령을 막는 검사 같은 나머지 훅은 `standard` 프로필 그대로 둔다.

## 5. 주의할 점

### 남아 있는 작은 충돌 — CLAUDE.md가 우선한다

복사한 파일은 원본을 그대로 유지했고, 수정하지 않았다. 그래서 아래 문장들이 남아 있다.

- `common/code-review.md`: 체크리스트에 "커버리지 80%"가 있다.
- `python/coding-style.md`, `python/hooks.md`: black, mypy를 언급한다. 이 프로젝트는 Ruff를 쓴다.

### 그 밖에

- `code-review.md`와 `git-workflow.md`는 넣지 않은 파일(`testing.md`, `agents.md`, `development-workflow.md`)로 링크한다. 이 링크는 깨져 있다.
- 복사본은 플러그인을 업데이트해도 따라 바뀌지 않는다. 업데이트 후 필요하면 다시 복사한다.
- 관찰 훅 같은 일부 훅은 세션 기록을 `~/.claude/` 아래에 남긴다. 이 기록은 로컬에만 저장된다.
- **미검증**: 프로젝트의 `.claude/rules/`가 전역 `~/.claude/rules/`와 똑같이 로드되는지는 아직 확인하지 않았다. 새 세션에서 확인한다.
