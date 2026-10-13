# Rug-on-rug friction

> Status: **implemented and checked on screen** (folds stay, reopening and dragging feel fine, no visible stretch). Tests: later, designed by the maintainer.

## 1. Overview

When you fold a corner of the rug back to uncover an icon and let go, the
fold used to slide back and the rug spread flat again within about two
seconds, covering the icon you wanted to click. Now a layer resting on
another layer grips it the way the rug grips the floor, so a fold stays put.

## 2. Background

- **Floor friction** (`FLOOR_FRICTION`, set to 0.8 by `rug_widget.py`): for
  particles touching the floor, part of this step's sideways movement is
  cancelled. This existed before.
- **Self-collision** (`_find_close_layers`, `_separate_layers`): particles of
  different layers that come too close are pushed apart, so a fold lies on
  top instead of sinking through. It only pushes; it never held anything in
  place.
- So a fold lying on the rug touched no floor and had no friction at all.
  The bending constraints across the crease, which are squeezed shorter
  than their rest length, push the fold open, and nothing resisted. Analogy:
  two sheets of plastic on top of each other versus two blankets.
- **Relative friction**: a layer on top should move *with* the layer below,
  not stay fixed in the world. Otherwise dragging a folded rug would leave
  the fold behind. So the slip that is cancelled is the upper particle's
  movement minus the average movement of the particles under it.

## 3. Structure

- `cloth.py`
  - `SELF_FRICTION = 0.4`: fraction of the slip cancelled in each constraint
    pass.
  - `SELF_FRICTION_CONTACT = 1.1`: pairs up to 1.1× the collision distance
    count as touching.
  - `ClothSimulation._apply_self_friction(flat, pairs)`: reuses the pairs
    already found for self-collision this step (no extra KD-tree search),
    keeps the touching ones, picks the upper particle of each pair, and pulls
    its sideways movement toward the average movement of its lower partners
    (`bincount` sums per particle). The held particle is skipped.
  - `step()`: calls it at the start of every constraint pass.

## 4. Design decisions

Measured with a script that folds the top-right corner 54 cm inward, holds it
for a moment, releases, and watches for 5 seconds.

| Approach | Slid back after 0.5 / 1 / 2 / 5 s | Notes |
|---|---|---|
| No rug-on-rug friction (before) | 9.7 / 37.1 / 53.8 / 53.8 cm | Unfolds completely |
| Lower bending stiffness 0.9 → 0.3 | 7.8 / 35.0 / 53.8 / 53.8 cm | Not the cause |
| Friction once per step, before the passes (0.8) | 1.5 / 2.8 / 5.7 / 14.2 cm | Keeps creeping: the bending push in each pass gets through |
| Friction once per step, after the passes (0.8) | 0.8 / 1.0 / 1.4 / 2.5 cm | Holds, but stretches the rug 2.15× while dragging |
| **Friction at the start of every pass (0.4, chosen)** | 0.1 / 0.2 / 0.5 / 1.3 cm | Holds; dragging stretch 1.33× (1.19× before) |

- Applying friction once per step is the obvious copy of the floor friction,
  but the floor case has no constant force; a fold does (the squeezed bending
  constraints). Applying it in every pass catches that push every time.
- Applying it after the passes holds best but undoes the constraints' work,
  the same mistake that once stretched the rug 11.6× with floor friction.
- Lower bending stiffness alone changed nothing, and would also make the rug
  look thinner.
- "Remembering" the folded shape (plastic rest lengths) was rejected: more
  complex and not how a real rug behaves.

Step time while dragging: about 5–6 ms in both versions (no measurable cost,
since the pairs are reused).

## 5. Caveats

- **Locked-in stretch**: after a fold settles, 35 of 2,183 edges stay
  5–13% longer than rest, near the crease (none before). Friction holds the
  flap while the crease pulls. Not visible on screen (maintainer checked).
- **A folded rug dragged by the bottom layer**: the flap moved 16.7 cm on
  average while the rest of the rug moved 26.2 cm. Part of that is the rug
  bunching up under floor friction, but the flap may also lag behind. No lag
  was noticed on screen.
- **Feel**: pulling a fold back open could feel heavier, since only the held
  particle is exempt. It felt fine on screen.
- Untested: the maintainer designs the test cases.
