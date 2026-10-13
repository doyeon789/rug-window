# Rug Window

> Status: **in progress**. Redesigned after the original video: the whole screen is the stage, and you grab, drag, and fold a rug seen from straight above. It bumps up over desktop icons. Remaining: test cases (designed by the maintainer) and fine tuning.

## 1. Overview

A Windows desktop app that **covers the messy files on your desktop with a virtual rug**.
The idea comes from a macOS app by Terkel at GitHub Next.

MVP scope: on launch, a 3D cloth rug drops onto the desktop, wrinkles as it spreads out, and can be dragged with the mouse.
Files are never moved; they are **only covered visually**. Bumps that depend on how many files are underneath come after the MVP.

## 2. Background

### Window Z-order (front-to-back order)

Every top-level window in Windows sits in one front-to-back list.

```
[front]  other app windows (browser, editor ...)
         ── rug window (must sit right in front of Progman)
[back]   Progman / WorkerW  ← desktop icons + wallpaper
```

- The second argument of `SetWindowPos(hwnd, insert_after, ...)` is "where to stand". Pass a window's hwnd to stand **right behind that window**; pass `HWND_BOTTOM` to stand **at the very back**.
- ⚠ **Correction**: the first plan used `HWND_BOTTOM`, but Progman is also a top-level window, so the rug could hide **behind** the desktop (unverified). Alternative: stand behind the window right in front of Progman (`GetWindow(progman, GW_HWNDPREV)`). Check both by eye during implementation.
- When the user clicks the rug, the OS **activates it and pulls it to the front**. Plan of defence: ① block activation itself with `WS_EX_NOACTIVATE` → if that fails, ② intercept `WM_WINDOWPOSCHANGING` and swap the position → last resort ③ push it back down after the click (flickers).
- Attaching as a child of `WorkerW` (what live-wallpaper apps do) puts the window **behind** the icons, so it cannot cover them.

### Window styles and Qt options

A window style is a **bundle of bit switches**. To turn one on, always read → OR it in → write.

```python
style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)
```

Whatever Qt options can do is done with Qt; `desktop.py` keeps only what Qt cannot do.

| Need | How |
|---|---|
| No frame | `Qt.FramelessWindowHint` |
| Hide from the taskbar | `Qt.Tool` (turns on `WS_EX_TOOLWINDOW`) |
| Stand right in front of Progman | `desktop.py` (Win32 directly) |
| Do not come to the front on click | `WS_EX_NOACTIVATE` in `desktop.py`, or a Qt option (to verify) |

### Transparent windows

In Qt, removing the frame with `FramelessWindowHint` and turning on `WA_TranslucentBackground` gives a window with per-pixel alpha.
Wherever the rug is not drawn, alpha is 0, so the desktop behind shows through.

### Building cloth with Verlet integration

The cloth is a grid of **particles** plus **constraints (sticks)** that try to keep pairs of particles at a fixed distance.

Every frame:
1. **Integrate**: `new position = current + (current - previous) * damping + acceleration * dt²`
   - Velocity is not stored; the "difference from the previous position" is the velocity. So when a position is forced (collision, constraint), the velocity follows naturally.
2. **Solve constraints**: for each stick, find the difference between its current and rest length and pull or push both ends by half. Repeating this several times (e.g. 8) makes the whole cloth converge.
3. **Collide**: particles below the floor (z=0) are lifted back onto it.

Stick types:

| Type | Connects | Role |
|---|---|---|
| Structural | horizontal and vertical neighbours | keeps the cloth from stretching |
| Shear | diagonal neighbours | keeps squares from squashing into parallelograms |
| Bending | two cells apart | resists folding → sets wrinkle size |

### Normals and Lambert lighting

The particle grid is split into triangles, and each vertex's **normal** (the direction the surface faces) is the average of the faces around it.
Brightness = `max(0, normal · light direction)`. Wrinkles tilt the normals and look darker. All of the cloth's depth comes from this shading.

## 3. Structure

### Files

**App code (`src/rug_window/`)**, in data-flow order

| File | One-line role | Analogy | Knows about |
|---|---|---|---|
| `__main__.py` | Assembles the app and runs the event loop | Unlocking the art room | Qt (assembly only) |
| `rug_widget.py` | The hub: moves the cloth on a timer, repaints, takes drags | The painter | Qt |
| `desktop.py` | Win32 work Qt cannot do: stand right in front of Progman, do not come forward on click | The line monitor | Win32 (hwnd only) |
| `cloth.py` | Computes the cloth's motion with beads and sticks | The calculation notebook | numpy only |
| `renderer.py` | Turns bead positions into shaded cloth | Paint and brush | OpenGL |

Data flow: `QTimer(16ms)` → `ClothSimulation.step()` → `positions` array → `update()` → `paintGL` → `ClothRenderer.draw()` → screen

**Project settings**

| File | Role |
|---|---|
| `pyproject.toml` | Project info, allowed dependency ranges, ruff/pytest settings |
| `uv.lock` | The exact installed versions (managed by uv, must be committed) |
| `.gitattributes` | Normalises text-file line endings to LF |
| `.gitignore` | Keeps `.venv/`, `__pycache__/`, etc. out of commits |

**Claude collaboration rules** (local only, not tracked in git)

| File | Role |
|---|---|
| `CLAUDE.md` | Code, naming, commit, and workflow rules Claude follows |
| `.claude/settings.json` | Plan mode by default, blocks `gh pr merge` |
| `docs/explainers/rug-window.md` | This document: plan, background, design decisions, learning notes |

## 4. Design decisions

| Choice | Rejected alternatives | Why |
|---|---|---|
| PySide6 | PyQt6, pyglet, tkinter | Supports transparent windows, OpenGL, and the tray, and is LGPL |
| Depend on `pyside6-essentials` only | full `pyside6` | Every module used (QtGui, QtWidgets, QtOpenGL, QtOpenGLWidgets) is in essentials. `.venv` 769 MB → 327 MB |
| QOpenGLWidget + PyOpenGL | moderngl, Qt3D | Fewest layers, most documentation |
| Hand-written Verlet in numpy | PyBullet, Taichi | Light, and the principle can be understood directly |
| Stand right in front of Progman | attach to WorkerW, HWND_BOTTOM | WorkerW is behind the icons. HWND_BOTTOM may go behind Progman (to verify) |
| Function name `place_above_desktop` | `place_behind`, `pin_to_desktop_layer` | The calling line alone shows *why* it is called |
| Hide from the taskbar with `Qt.Tool` | edit the style in `desktop.py` | Simpler, and no risk of overwriting styles. The code that creates the window decides its nature |
| `positions` is a read-only view | the internal array, a copy | No copy even when read every frame (60 fps). An accidental write from outside raises instead of silently breaking the simulation |
| Bad input raises `ValueError` | documentation only | With `rows`/`cols` < 3 the bending sticks (two cells apart) cannot exist, and `spacing` ≤ 0 is not a cloth. Stopping at once is easier to debug than odd behaviour |
| No Progman → `OSError`; no window in front → `HWND_TOP` | silently ignore both | Not finding the desktop is a real failure and must be reported. With nothing in front, the very front *is* right in front of Progman |
| Call Win32 functions **after** the window is shown | in `__init__` | The real window (hwnd) exists only after show, and Qt may rewrite styles during show |
| `main()` calls the Win32 helpers | inside `RugWidget` (`showEvent`) | Keeps the widget unaware of Win32, and makes the "call after show" order visible in the one place that assembles the app |
| Wrap errors as `OSError` | raw `pywintypes.error` | pywin32 errors are not `OSError` (verified). `FindWindow` just returns 0 on failure, so it is checked and raised by hand |
| Walk forward from Progman, skipping topmost windows | stand behind the window right in front | If the window in front is topmost (e.g. the taskbar), a rug behind it also becomes topmost and floats over every app (unverified). Without one, `HWND_NOTOPMOST` |
| Drag with the left button only, no `mouseReleaseEvent` | end the drag in a release handler | Move events only arrive while a button is held. Instead, block dragging with the right button |
| Renderer in device pixels, conversion in the widget | each converts on its own | On HiDPI, logical × `devicePixelRatio()` = device. Convert in one place only |
| Turn on ruff `"D"` rules | only keep the settings | `pydocstyle` settings do nothing unless `"D"` is in `select` |
| Indices uploaded once in `__init__`, only positions and normals each frame | upload everything every frame | The grid shape (which beads connect) never changes |
| ~~Slanted light (`LIGHT_DIRECTION`)~~ → a lamp above the screen centre (`LIGHT_HEIGHT` 4 m) | one distant directional light | Maintainer's request. Folded faces get brighter or darker by how much they face the lamp |
| `ClothRenderer.release()`, called by the widget on close | leave it to garbage collection | GPU objects are not returned when Python deletes the wrapper, and can only be returned while the context is current |
| Validate `draw()` input (`ValueError`) | upload without checks | With a wrong shape or type the GPU draws garbage without complaint |
| Borrow only the texture (B) | use the model as is (A), turn the model into cloth (C), skeleton + skin (D) | The model has 330k points, two layers, and sculpted, frozen wrinkles → A cannot move, C is slow and springs back to the old wrinkles, D doubles the wrinkles. If unsatisfying, try A and C too |
| Use the CC0 original texture from ambientCG | the CGTrader file | CGTrader's terms (21A.1, 21A.6) forbid redistributing files as downloaded. The same texture's CC0 original was downloaded directly. `assets/rug/` is in `.gitignore` |
| Texture inside the package (`src/rug_window/assets/`) | repo-root `assets/` | Files outside `src/` are left out on install |
| `load_texture` returns `QImage` | `QPixmap` | `QPixmap` needs an application object, which makes tests awkward. `QBrush` accepts both |
| Placeholder: small repeated check (1/4 size) + rounded corners + navy border | one big check spread like the model, square corners | Both were built and the maintainer chose. The big check looked plain when flat, without wrinkles or shadows |
| Thickness: one layer in physics, two when drawing (Solidify) | simulate two layers | The renderer pushes beads ±thickness/2 along the normal to make top and bottom faces and joins the edges with a band. Costs only the edge cells. No problem of two layers drifting apart (step 4) |
| Split sticks into odd/even batches computed at once | one stick at a time in a for loop | numpy batch work is hundreds of times faster. Beads must not repeat within a batch or writes overwrite each other → (1-2, 3-4) first, (2-3, 4-5) after |
| Floor friction = cancel this step's sideways move (grip, `FLOOR_FRICTION = 1.0`) | only slow the velocity | With only slowing, the stick solver slides floor beads like ice and the wrinkles flatten |
| Drop at a tilt (`DROP_TILT = 0.4`) | level | Cloth dropped level lands level. One side must touch first and be held so the rest is pushed into wrinkles |
| `tilt` and `floor_friction` as constructor arguments | constants only | To compare and tune in the preview tool. Defaults are the constants |
| Easy-to-test module functions `verlet_step`, `relax_pairs`, `structural_pairs` | everything inside the class | The number examples in the learning notes can be used as tests directly |
| Camera straight above (orthographic, 1 m = 450 px) | 30° tilt | The original video looks from above. Converting the mouse position to world coordinates also becomes simple |
| Full-screen transparent window + click-through toggled every frame (`WS_EX_TRANSPARENT`) | small window + window dragging | The rug can go anywhere on the desktop. Does not rely on transparent pixels passing clicks automatically, so it is reliable |
| No shadow | offset shadow, shadow projected from a lamp | Both were built, but the maintainer chose to drop them (later brought back; see below) |
| Floor friction → stick solving order + tether from the grabbed point | sticks → friction, more iterations | Stretch 11.6× → 1.07×. The sticks must have the last word |
| The grabbed point follows the mouse 25% per frame (`GRAB_FOLLOW`) | snap to it | Lagging a beat behind gives a sense of weight (maintainer confirmed) |
| Self-collision: find pairs once (KD-tree, scipy), push apart every iteration, measure height at 0.7× | search every time, plain 3D | Searching every time costs 27–64 ms. Discounting height keeps beads from slipping through the gaps of the layer below. Visibly piercing pairs 719 → 0 |
| Stick batches as grid slices | index lists (fancy indexing) | Same pairs, but no copies: 2× faster |
| 3× denser only when drawing (Catmull-Rom matrices) | 3D model, scipy `zoom` | A model only adds smoothness and cannot handle collision or interaction. Matrices take 0.25 ms (`zoom` 15.5 ms) |
| Pause the simulation when nothing moves | always 60 fps | Compositing a large transparent window every frame uses a lot of CPU |

## 5. Caveats / open questions

- [x] Does QOpenGLWidget + transparent background composite correctly on Windows? → **yes** (step 2, maintainer confirmed. Checked with the `QPainter` placeholder; shader rendering to be checked again in step 4)
- [ ] With every other window minimised, does the window in front of Progman become topmost, and does skipping topmost windows keep the rug from floating over apps? (PR #6 review, unverified)
- [ ] Does Qt's `resizeGL` really give logical pixels? (unverified)
- [x] Standing right in front of Progman → **works** (step 2: read via Win32, 0 windows between the rug and Progman). `HWND_BOTTOM` itself was not tried
- [ ] (On this PC the icons are under Progman. Other setups unverified.) In some states, such as a wallpaper slideshow, the icons (`SHELLDLL_DefView`) may live under `WorkerW` instead of Progman. Then "right in front of Progman" may be behind the icons (reviewer's note, unverified)
- [ ] `GRAVITY = -9.8` assumes 1 rug unit = 1 m. Adjust if the fall looks odd on screen (unverified)
- [x] Is `WS_EX_NOACTIVATE` set, and does it work together with dragging? → **yes** (step 2: style checked + maintainer confirmed)
- [x] Extended style Qt sets on a transparent window → **`WS_EX_LAYERED`** (step 2, confirmed from output). So `disable_activation` must keep read → OR → write
- [ ] Do clicks pass through the window's transparent margin? (If not, icons near the rug cannot be clicked; unverified)
- [ ] Win+D (show desktop) will likely hide the rug too (accepted for the MVP)
- [x] numpy performance → one step of a 40×25 grid takes **about 4.5 ms** (budget 16.7 ms, measured in step 3)
- [ ] How far to tilt the camera so the thickness (side faces) looks natural. Seen straight from above, the sides are invisible (decide by eye in step 4)
- [ ] `RUG_THICKNESS` and bending stiffness: values that give the big, round folds of a thick rug (step 3)

## 6. Learning notes

### Skeleton review (2026-10-12)

**How it starts**
- `python -m rug_window` → runs the package's `__main__.py` directly → `__name__ == "__main__"`
- The `rug-window` command (`[project.scripts]`) → `from rug_window.__main__ import main`, then `sys.exit(main())` → this is an import, so the `if __name__ == "__main__":` block **does not run**
- Conclusion: all startup logic lives in `main()`. Anything in the `if` block is skipped by the `rug-window` command.

**`pyproject.toml` vs `uv.lock`**

| File | Contents | Managed by |
|---|---|---|
| `pyproject.toml` | Allowed ranges (`numpy>=2.0`) | People |
| `uv.lock` | The exact installed versions (`numpy==2.5.4`) | uv, automatically |

- Without a committed lock file another PC installs other versions, and "works on my machine" bugs appear → app projects commit the lock.
- `dependencies` are needed to run; the `dev` group only for development.
- `# noqa: N802`: turns off one of ruff's `N` (naming) rules on that line only. Qt method names are set by Qt and cannot change.

**The `src/` layout**
- Module = a `.py` file, package = a folder of modules, `__init__.py` = marks a package
- In a flat layout, tests may import the neighbouring folder instead of the installed copy and miss packaging errors.
- The `src/` layout always goes through the installed copy. `uv sync`'s editable install just writes the `src/` path into `.venv/Lib/site-packages/_editable_impl_rug_window.pth` → code edits apply immediately.

**Parts of a skeleton**
- Type hints: **labels** not checked at run time. For people, editors, and mypy.
- Docstrings: descriptions that stay at run time (`help()`, editor tooltips). Fix the meaning before implementing (e.g. `spacing` = the stick constraint's "rest distance").
- `raise NotImplementedError` vs `pass`: `pass` returns `None` and blows up somewhere unrelated; `NotImplementedError` stops right at the empty spot.

**Fencepost error** ← step 3 test candidate
- n particles have n−1 gaps.
- `ClothSimulation(rows=40, cols=30, spacing=0.1, ...)` → 1200 particles, width (x) = 29 × 0.1 = **2.9**, height (y) = 39 × 0.1 = **3.9** (not 3.0 / 4.0)

### Desktop window basics (2026-10-12)

**hwnd and separation of concerns**
- A window is data managed by the OS, and an hwnd is a number (handle) pointing to it. The value means nothing by itself; you only hand it back to the OS.
- Win32 APIs know nothing about Qt widgets, only hwnds. The conversion (`int(widget.winId())`) happens once, on the Qt side.
- `desktop.py` takes only hwnds, so it does not need Qt → replacing Qt with tkinter would only touch `rug_widget.py`.

**Styles = bit switches**
- Turn on with `|` (OR), off with `& ~`.
- `SetWindowLong` overwrites everything. Writing just `WS_EX_TOOLWINDOW` without reading first turns off every other switch (e.g. the ones Qt set for the transparent window).

**Z-order**
- Top-level windows stand in one front-to-back line. A click activates a window and pulls it to the front → the rug would cover other windows.
- The last argument of `SetWindowPos` is also a bitwise OR: `SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE`.

**Design change**
- Drop `hide_from_taskbar()` and use `Qt.Tool` (simpler, no overwrite risk).

### `__main__.py` / `rug_widget.py` review (2026-10-12)

**What `main()` does**: ① set alpha in `QSurfaceFormat` (before `QApplication`) → ② `QApplication` (one per process) → ③ `RugWidget()` → ④ `show()` (only a request) → ⑤ `return app.exec()`

**The event loop**
- Inside `app.exec()` it repeats "take an OS event → deliver it to the widget in charge". It returns only when the app ends → the next line runs only at exit.
- `paintGL`, `mousePressEvent`, and the like are not called by us but by the event loop (callbacks).

**The Ctrl+C trap** (MVP quit method = Ctrl+C)
- Python checks SIGINT only while running Python code, and `app.exec()` mostly runs in C++, so Ctrl+C is ignored.
- Fix: `signal.signal(signal.SIGINT, signal.SIG_DFL)` → the OS default (exit immediately). Cost: cleanup code does not run. Add a separate `app.quit()` path with the tray.

**Flip-book analogy: OpenGL callbacks**

| Real | Analogy |
|---|---|
| `RugWidget` | The painter |
| Qt event loop | The art teacher |
| OpenGL context | Paper and paint laid out on the desk |
| `__init__` | Arriving at work: only sets an alarm (timer). No paper → cannot make the renderer |
| `initializeGL` | The teacher lays out the paper → mix the paints (create the renderer), exactly once |
| `resizeGL` | The paper changes size |
| `update()` | Raising a hand: "I'll draw the next page" |
| `paintGL` | The teacher lays out the paper and says "now draw" |

- Rule: never call `paintGL()` directly. Context setup is skipped and it draws in the wrong place. Always `update()`.
- 16 ms timer → `cloth.step()` → `update()` → `paintGL` ≈ 60 pages per second.

**Dragging**
- On press, `grab offset = mouse - window top-left`; on move, `window top-left = mouse - grab offset`.
- Forget the offset and the window jumps by it, sticking the mouse to the window's corner.
- Example: window (50, 80), click (150, 130) → offset (100, 50). Mouse (250, 230) → window (150, 180).
- `mouseReleaseEvent` is not needed for the MVP: Qt sends `mouseMoveEvent` only while a button is held.
- The window (a transparent film) must be bigger than the rug, so parts flapping during the fall are not cut off.

### `desktop.py` review (2026-10-12)

- Queue analogy: `HWND_BOTTOM` = "the end of the line" → may go behind Progman. Instead, "stand behind the person right in front of Progman":
  `FindWindow("Progman", None)` → `GetWindow(progman, GW_HWNDPREV)` (the person one place **ahead**) → `SetWindowPos(hwnd, that person, ...)`
- Planned skeleton changes: remove `hide_from_taskbar` (`Qt.Tool`), `send_to_bottom` → `place_above_desktop`, add `disable_activation` (`WS_EX_NOACTIVATE`), correct the `HWND_BOTTOM` description in the module docstring.

### `cloth.py` A: cloth = beads + sticks (2026-10-12)

- Real cloth cannot be computed, so it is simplified into **beads (particles)** and **sticks (constraints)**.
- Bead: only an `(x, y, z)` position → `positions` has shape `(rows, cols, 3)`.
- Stick: a promise "let's stay this far apart". Rest length = `spacing`.

| Stick | Connects | Without it |
|---|---|---|
| Structural | horizontal and vertical neighbours | stretches like a rubber band |
| Shear | diagonal neighbours | squares squash into diamonds |
| Bending | two cells apart | folds sharply like paper. Strong = thick blanket, weak = silky wrinkles |

- Start: every bead flat at `drop_height` → each `step()` falls under gravity.
- **Number of structural sticks** (fencepost rule): horizontal = `rows × (cols − 1)`, vertical = `cols × (rows − 1)`.
  Example: `rows=3, cols=4` → horizontal 3×3 = 9, vertical 4×2 = 8, **total 17**. ← step 3 test candidate

### `cloth.py` B: predicting the next position / Verlet (2026-10-12)

- Analogy: two consecutive photos of a ball → "it moves as much as it did last time", plus the extra pull of gravity this frame.
- `new position = current + (current − previous) × damping + acceleration × dt²`

| Piece | Meaning |
|---|---|
| `current − previous` | Velocity (not stored separately) |
| `× damping` (e.g. 0.99) | Air resistance. Without it, it bounces forever |
| `acceleration × dt²` | Gravity. Needed for it to speed up |

- Why store the **previous position** instead of velocity: when sticks or collisions force a bead somewhere, that move automatically feeds into the next velocity → short code that rarely blows up.
- Example (no damping, gravity −0.01, previous 5.0, now 4.9):

| Frame | Height | Distance fallen |
|---|---|---|
| now | 4.9 | 0.1 |
| 1 | 4.79 | 0.11 |
| 2 | 4.67 | 0.12 |
| 3 | 4.54 | 0.13 |

- Common mistake: drop the gravity term and you get constant speed (4.8, 4.7, ...), and with zero starting speed the cloth **hangs in the air**. ← step 3 test candidates ("does z drop after a step", "does the fall distance grow every step")

### `cloth.py` C: keeping stick lengths / constraints (2026-10-12)

- With only B, the beads fall one by one like a "rain of sand". Sticks tie the beads into cloth.
- Analogy: two friends holding a 1 m tape measure. They **split the difference in half and both** move closer or apart.
  - Example: rest length 1.0, A = 0.0, B = 1.4 → 0.4 too long → 0.2 each → A = 0.2, B = 1.2 ← step 3 test candidate
- Fixing one stick bends its neighbours → repeat over everything several times (e.g. 8) to converge. Too few and it stretches like rubber; too many and it is slow.
- Floor collision: beads with `z < 0` go to `z = 0`. The previous position stays, so the downward velocity disappears by itself (a Verlet advantage).
- `step()` order: ① Verlet prediction → ② stick solving × N → ③ floor collision

### `cloth.py` skeleton review (2026-10-12)

- Removed the `positions` description from `Attributes:` → keep it only in the property docstring (duplicates drift when only one is updated).
- Hidden numbers become module constants: `DAMPING`, `GRAVITY`, `CONSTRAINT_ITERATIONS`. Promote them to constructor arguments when tests need it (avoid premature abstraction).
- `dt` is passed as a **fixed 1/60 s**.
  - Why: Verlet reuses "the distance moved last time". If the photo interval doubles from 16 ms to 32 ms, the bead should move twice as far, but Verlet moves only the previous (16 ms) distance → it suddenly slows down. If the interval shrinks, it moves too far, gains energy, and the cloth can explode.
  - Cost: when the computer stutters, the animation just slows down a little; the cloth stays stable.

### Addressing PR #6 review (2026-10-12)

Reviewed with ECC `python-reviewer`, then double-checked by Claude.

- **pywin32 exceptions**: the parent of `pywintypes.error` is `Exception`, not `OSError`. To document `OSError`, errors must be converted and raised by hand.
- **Queue trap**: the person right in front of Progman may belong to the "always in front" group (topmost) → standing behind them makes you a member too → walk forward and skip topmost windows.
- **Where we disagreed with the reviewer**: `mouseReleaseEvent` was not added, on the grounds that "Qt sends move only while a button is held". Instead, "move only with the left button" was made explicit. A reviewer's point can be rebutted with evidence instead of accepted as is.
- **A switch with the power off**: `[tool.ruff.lint.pydocstyle]` works only with `"D"` enabled. After enabling it, `D103` showed up on functions without docstrings.
- GPU cleanup (`release()`) and `draw()` input validation in `renderer.py` are handled in the `renderer.py` review.

### `renderer.py` learning and review (2026-10-12)

**A. Connect the dots**
- The GPU only fills triangles. One grid square = two triangles → a mesh.
- A connect-the-dots book: ① dot positions (`positions`, change every frame) ② the list of which dots to connect (indices, never change).
- Counts (fencepost rule):

| | Formula | rows=3, cols=4 | rows=40, cols=30 |
|---|---|---|---|
| Beads | `rows × cols` | 12 | 1200 |
| Squares | `(rows − 1) × (cols − 1)` | 6 | 1131 |
| Triangles | `2 × (rows − 1) × (cols − 1)` | 12 | 2262 |

- Common mistake: confusing the bead count (12) with the square count. ← renderer test candidate ("number of triangles in the indices")

**B. Normals and lighting**
- A flashlight and crumpled paper: faces that take the light head-on are bright; slanted ones are dark → wrinkles show.
- Normal = the direction a face looks (a toothpick stuck into it). Brightness = `max(0, normal · light)`.
  Here light = the direction **from the face to the light source** (now lamp position − face position). Read it as "where the light comes from" and flip the sign, and bright and dark swap.
- When the cloth moves the normals change, so they are recomputed every frame.
- A flat rug + light straight above = the same brightness everywhere → put the light at an angle.

**C. The GPU as an outsourced factory**

| Real | Analogy |
|---|---|
| Shader | Work instructions for the factory staff (compiled in `__init__`) |
| Buffer | A storage bay rented at the factory (positions, normals, index list) |
| `release()` | Returning the bays. Only possible while the context is current → `aboutToBeDestroyed` → `makeCurrent()` → `release()` → `doneCurrent()` |

- `draw()` input checks: shape `(rows, cols, 3)`, `float32` (numpy defaults to `float64`, an easy mistake), C-contiguous (copied in one piece).

### Addressing PR #7 review (2026-10-12)

- **Write a contract between modules on both sides**: the renderer said "only C-contiguous `float32`", but the cloth's `positions` did not promise it → the same promise was added on the cloth side. Both parties need the same contract in hand.
- **Rules after release**: only the first `release()` needs a context; calling again does nothing. `draw`/`resize` after release raise `RuntimeError`.
- **A renderer that does not exist yet**: `self._renderer` is `None` until `initializeGL` → `paintGL` and the release slot do nothing when it is `None`.
- **Fractional scaling**: `devicePixelRatio()` can be fractional like 1.25 → `round()`, not `int()` (truncation).
- **Zero size**: a minimised window can report 0 → `resize` ignores it (avoids division by zero).
- Still unverified: `makeCurrent()` failing inside the release slot.

### Step 2: desktop window results (2026-10-12)

**What was built**: a translucent brown rounded rectangle (the "placeholder rug") floats above the desktop icons and below other apps. Left-drag moves it. No cloth or renderer yet.

**Verified by reading Win32 state directly** (app shown for 4 s, then inspected)

| Item | Result |
|---|---|
| `WS_EX_TOOLWINDOW` (hidden from taskbar, `Qt.Tool`) | on |
| `WS_EX_NOACTIVATE` | on |
| `WS_EX_TOPMOST` | off |
| `WS_EX_LAYERED` | on (Qt sets it for transparent windows) |
| Windows between the rug and Progman | 0 → right in front of Progman |
| Stole focus? | no |

**Maintainer check**: ran it, "works well". Per-item results (clicks through the margin, minimise all, click empty desktop, Win+D) were not reported, so those open questions stay open.

**Learned while implementing**
- pywin32's `GetWindowLong`/`SetWindowLong` return **0 without error** for an invalid hwnd (`SetWindowPos`, `GetWindow` do raise). → check with `IsWindow` first.
- `FindWindow` returns 0 when nothing is found (not an error).
- On Windows a venv's `python.exe` is a launcher that starts the real Python as a child process, so the window owner's PID differs.
- How to check that a test is useful: plant a bug on purpose and see it fail. Planting the "overwrite" bug made `test_disable_activation_keeps_existing_style_bits` fail.

**Temporary for now** (replaced in steps 4 and 5)
- `_paint_placeholder()` in `paintGL` (removed once the renderer exists)
- `initializeGL` does not create the renderer yet
- No frame timer (no cloth to move)

### Rug texture and thickness (2026-10-12)

**3D model analysis** (CGTrader "Blue Rug", OBJ)
- 329,314 points (about 275× our cloth), quad faces only, one closed piece without gaps.
- Top and bottom layers + thin sides = a thick slab. No tassels.
- Plotting the top surface's height shows diagonal wrinkles **sculpted and frozen in place** → "a statue of the moment it was crumpled".
- The texture is ambientCG "Carpet006" (blue check, repeating pattern). It has colour, normal, roughness, AO, and height maps.

**Mannequin clothes vs real cloth**: a 3D model file holds only the "shape", not "how it bends". So our cloth makes the shape, and only the look (texture) is borrowed from the model (B).

**Licenses differ by where you got it**: even a free model on CGTrader cannot be redistributed. The original of the same texture (ambientCG, CC0) was found and used instead.

**Tried, then chosen**: a big check (one texture spread like the model) with square corners was also built, but looked plain when flat. Big patterns need wrinkles and shadows to come alive.

**Thickness (seaweed sheet vs thick blanket)**

| Why it looks thick | How to fake it | Step |
|---|---|---|
| ① The sides are visible | The renderer draws two faces ±thickness/2 apart and joins the edges with a band (Solidify) | 4 |
| ② It folds big and round | Stronger bending sticks | 3 |
| ③ It rests a thickness above the floor | Raise the floor collision by thickness/2 | 3 |
| ④ Shadows under folds | Lighting + normal map | 4 |

- Physics stays one layer, so it is fast, and the two layers never drift apart.
- Seen straight from above, the sides are invisible → tilt the camera slightly or wait for wrinkles to stand up to see the thickness.
- One `RUG_THICKNESS` constant is shared by `cloth.py` (collision height) and `renderer.py` (gap between the two faces).

### Addressing PR #9 review (2026-10-12)

- **Keep a promise on every path**: the docstring said "pywin32 errors become `OSError`", but only `place_above_desktop` had the `try/except`. Added it to `disable_activation` too. A promise kept in one function is easy to miss in the next.
- **Build per-frame objects in advance**: the texture brush (`QBrush`) is made once in `__init__`. At 60 fps it would otherwise be rebuilt 60 times a second.
- **Guarantee cleanup with `try/finally`**: `painter.end()` always runs, even if drawing raises.
- **Exit if the Win32 helpers fail** (decision): a rug that cannot attach to the desktop floats over other apps and looks broken. An error that shows the reason at once is better. Friendlier messages later.
- After the change, a redraw matched byte for byte → same behaviour, better structure.

### Step 3: cloth simulation (2026-10-12)

**Tests = the learning notes' number problems as they are** (`tests/test_cloth.py`, 5 tests)

| Note | Test |
|---|---|
| Fencepost | 40×30, spacing 0.1 → 1200 beads, 2.9 × 3.9 |
| Stick count | 17 structural sticks for 3×4 |
| Verlet heights | 4.79 → 4.67 → 4.54 |
| Forgotten gravity | The fall distance grows every step |
| Tape-measure friends | 1.0 / 0.0 / 1.4 → 0.2 / 1.2 |

**Learned while implementing**
- **Odd/even batches**: if one person is pulled by two partners at once, one result is lost. Confirmed 0 shared beads within every batch (12 batches).
- **A blanket dropped level lands level**: the first implementation passed every test but had no wrinkles at all. Passing tests does not mean it looks right; check that separately.
- **Friction as position**: only slowing the velocity lets the stick solver slide floor beads. Cancel this step's sideways move itself, so the side that lands first is held.
- Experiment (4 s from 0.3 m):

| Friction | Pose | Highest point | Size |
|---|---|---|---|
| slide | flat | 0 cm (flat) | 1.17 × 0.72 |
| grip | tilted (default) | **about 3.3 cm** | 1.09 × 0.72 |

**How to look**: `uv run python tools/cloth_preview.py` — side view + top-down height map; compare with the `f`/`t`/`r` keys. Constants (`FLOOR_FRICTION`, `DROP_TILT`, `BENDING_STIFFNESS`) are tuned bit by bit once on screen.

**Untested behaviour** (cases to design later): not falling through the floor, grip friction, `tilt`, input validation (`ValueError`), read-only `positions`.

### Redesign after the original video (2026-10-12)

**What the video shows** (`assets/rug/reference/rug.mp4`, not committed): a Persian rug seen from above; grab a corner and drag, and it folds as it is pulled; it moves anywhere on the desktop; covers files; bumps up over files.

**New structure**
- Window = a transparent stage covering the whole screen (minus the taskbar). It takes clicks only while the cursor is over the rug; everything else passes through to the desktop.
- Left press → grab the nearest bead and lift it 3 cm → drag → release. Window dragging is gone.
- Icon positions are read from Explorer's memory every 2 s (`desktop_icon_rects`) and laid on the floor as 2 cm hills.
- The screen edges are walls.

**Problems and fixes (in numbers)**

| Problem | Cause (analogy) | Fix | Result |
|---|---|---|---|
| Stretches when dragged | The hand teleports while the rest is held by friction (rubber band) | Friction first → sticks after + tether | 11.6× → 1.07× |
| Folded layers pass through | Beads slip through the mesh holes | Discounted height for a generous gap + push apart every iteration | 719 → 0 pairs |
| Mesh is visible | Points are 2 cm apart | 3× Catmull-Rom only when drawing | Folded lines without jaggies |
| Slow | Index-list copies, a generic curve function | Slices, precomputed matrices, sleeping | Step 10 → 5 ms (standalone), curve 15.5 → 0.25 ms |

**Measured (while dragging, this PC)**: frame interval about 24 ms, step about 15 ms, draw about 4 ms. The step is slower inside the app than standalone, probably because compositing the big transparent window shares the CPU (a guess).

**A capture trap**: `grabFramebuffer()` images are tagged "2× high resolution", so combining them with `QPainter` draws them at half size → `setDevicePixelRatio(1)`.

**Untested new behaviour** (maintainer will design later): `screen_to_world`, `bump_heights`, `nearest_particle`, `grab`/tether, walls, self-collision, `subdivide_grid`.

### Addressing PR #11 review (2026-10-12)

- **Sleep broken every 2 s**: reading icons every 2 s woke the rug even when nothing changed → keep it asleep when the value is the same as before.
- **Explorer hangs, rug hangs**: `SendMessage` waits for an answer forever → `SendMessageTimeout` (200 ms). On timeout the old icons are used.
- **An error repeated every frame**: an `OSError` inside a timer is logged once and the app keeps going. The click-through state is recorded even on failure so it is not retried every 16 ms.
- **Multiple monitors**: icon coordinates are offset by the list view's screen position (`ClientToScreen`) and mapped to window coordinates with `mapFromGlobal` (monitors with different scaling unverified).
- **The walls follow screen changes**: `availableGeometryChanged` → refit the window size and walls, and wake up.
- Also: delete the leftover shader when removing the shadow, two matrix products instead of `einsum` for the surface, a precise timer, detect a missed button release, request a depth buffer explicitly, build Win32 function prototypes once.

### Tray app, size and weight, shadow, grabbing the top layer (2026-10-12)

**Running and quitting**
- `[project.gui-scripts]` in `pyproject.toml` → `uv sync` builds a console-less `.venv\Scripts\rug-window.exe`. The terminal one is `rug-window-console`.
- `tools/make_shortcut.py` makes a shortcut (icon: `assets/rug.ico`, drawn by `tools/make_icon.py` from the CC0 carpet texture).
- Notification-area tray icon (`tray.py`): click for a menu — Hide rug / Show rug, Quit. (Originally Korean labels; switched to English when the repo went public.) `setQuitOnLastWindowClosed(False)` keeps the app alive with no window.
- A named mutex prevents running twice. With no console, logs go to `%LOCALAPPDATA%\rug-window\rug-window.log`.

**Size and weight**
- `PX_PER_METRE` 450 → 600: the rug is 1.33× bigger on screen (1.78× the area).
- Weight (`GRAB_FOLLOW`): 0.25 divided by the area ratio gives about 0.14; set from 0.12 to 0.15 by the maintainer's feel. Friction 0.7. The grabbed point moves at most 5 cm per frame (3 m/s).

**Stutter (when swinging fast)**
- Self-collision searched and threw away thousands of pairs among flat neighbours every time → search **only around lifted beads**.
- Python loops to gather and sum results → `sparse_distance_matrix` (results as arrays) and `bincount` (sum by index).
- In-app step 33 → 15 ms, mean frame 43 → 28 ms. The remaining cost is probably compositing the full-screen transparent window (unverified). Shrinking the window to the rug's size would fix it at the root.

**"It looks like it sinks in" and the shadow**
- The simulation was folding upward correctly (99.8% of the dragged layer above). Seen from above height is invisible, so the rug seemed to shrink.
- A back-face colour was tried, but the maintainer kept the original colour. Instead the **shadow came back**: projected from a lamp 4 m above the screen centre, with MAX blending so overlaps do not get darker.

**Grabbing the top layer**: where layers overlap, grab the bead closest to the mouse among the **highest layer** (within half a thickness) in the mouse radius. Clicked 15 overlapping spots on a folded rug → top layer all 15 times.

### Addressing PR #12 review (2026-10-12)

- **GPU cleanup missing on quit** (confirmed by experiment): even after `del rug`, references such as signal connections kept the widget alive, so the "context about to be destroyed" signal never came → `RugWidget.shutdown()` cleans up right before quitting. Afterwards it clears the renderer and disconnects the signal, so a late signal at process exit cannot touch a deleted widget.
- **No tray, no start**: the tray is the only way to quit, so without one the app logs and exits.
- **Showing again**: `attach_to_desktop()` reapplies the Z-order and activation blocking together and clears the click-through cache.
- **Hidden means resting**: hiding stops the frame and icon timers; showing restarts them.
- **Logging**: configured first (so a mutex failure is logged too), UTF-8. Floor friction 0.8 (maintainer's tuning). `*.lnk` is in `.gitignore`.
