# Custom rug image

> Status: **implemented** and checked on screen by the maintainer. Tests:
> later, designed by the maintainer.

## 1. Overview

The rug used to be a small blue check pattern repeated over the cloth. Now:

- The default rug is a photo of a real 16th-century carpet (The Met, object
  452309, public domain), covering the rug once, with its border on all four
  sides.
- **Tray → Choose rug image…** dresses the rug in any picture. The choice is
  remembered for the next run. **Use default rug** goes back.
- The app icon is redrawn from the new carpet.

## 2. Background

- **UV coordinates.** Every vertex of the mesh says which spot of the image
  colours it, as `(u, v)` from 0 to 1. Before, `u` and `v` grew past 1 and
  the texture repeated (`GL_REPEAT`), like wallpaper tiles. Now the first
  column gets `u = 0` and the last `u = 1`, so one picture covers the rug
  once, like a poster. Edges use `GL_CLAMP_TO_EDGE` so the left edge never
  blends with the right edge's pixels.
- **Image rows vs. world rows.** Image row 0 is the top of the picture, but
  grid row 0 is the bottom of the rug on screen (world `y` grows upward).
  So `v = 1 - r / (rows - 1)`; without the flip the picture is upside down.
- **Fitting a picture.** The rug is 59 x 36 cells, a width-to-height ratio
  of about 1.64. `fit_to_rug` turns portrait pictures a quarter turn (rug
  photos are usually upright), cuts the too-long side equally from both
  ends, and shrinks pictures larger than 4096 px. Cutting keeps the picture
  undistorted; stretching would squash it.
- **The GL context.** Textures can only be uploaded while the widget's
  OpenGL context is current. `set_rug_image` therefore only loads and fits
  the picture (so a bad file fails right away) and parks it; `paintGL`,
  where the context is current, uploads it. A hidden rug gets it when shown.
- **QSettings.** Qt's store for small preferences. On Windows it writes to
  the registry under the current user (`pizza-playground` / `rug-window`).
  Only the chosen file's path is stored, not the picture.

## 3. Structure

| File | Change |
|---|---|
| `textures.py` | `DEFAULT_RUG_TEXTURE` is the Met carpet; new `fit_to_rug(image, aspect, max_side)` |
| `renderer.py` | `solid_mesh_layout(rows, cols)` maps one image over the rug; `ClothRenderer(rows, cols, texture)`; new `set_texture`; clamped edges |
| `rug_widget.py` | `RUG_ASPECT`; `set_rug_image(path or None)`; the parked image is uploaded in `paintGL` |
| `settings.py` (new) | `saved_rug_image()`, `save_rug_image(path or None)` |
| `tray.py` | Choose rug image… (file dialog; a bad file shows a warning and is logged), Use default rug |
| `__main__.py` | restores the saved image at start; an unusable saved file is forgotten and logged |
| `tools/make_rug_texture.py` (new) | turns the Met's original photo into the bundled texture |
| `tools/make_icon.py` | draws the icon from the new carpet |
| `assets/` | `met_452309_carpet.jpg` (2048 x 1250) replaces `carpet006_color.jpg` |

Flow: tray → `RugWidget.set_rug_image(path)` → `load_texture` →
`fit_to_rug` → parked → `paintGL` → `ClothRenderer.set_texture` → GPU.

## 4. Design decisions

| Choice | Rejected | Why |
|---|---|---|
| One image over the whole rug | keep tiling | The maintainer chose it; a medallion carpet repeated looks wrong |
| Crop user pictures to the rug's shape | stretch, or letterbox | Stretching distorts; empty bands look like a hole in the rug |
| Stretch (about 9%) only the bundled carpet | crop it too | Cropping would cut off its border on two sides; the slight stretch is not visible |
| A Met Open Access photo | texture sites (ambientCG, Poly Haven) | They had no single-piece patterned rug; museum photos of real carpets are flat, top-down, and CC0 |
| Art Institute of Chicago images | — | Also CC0, but their image server refused scripted downloads |
| Park the image until `paintGL` | `makeCurrent()` in `set_rug_image` | One code path for shown and hidden rugs; no context juggling |
| QSettings | a JSON file | Built into Qt; nothing to parse or locate |
| Redraw the icon from the new carpet | keep the blue check icon | The maintainer asked for it; the old texture is gone from the package |

## 5. Caveats

- A picture with a background (a photo of a rug on a floor) shows that
  background on the rug: only the shape is fitted, nothing is cut out.
- The saved path can go stale (file moved or deleted). Start-up then falls
  back to the default and forgets it.
- `MAX_TEXTURE_SIDE = 4096` is a guess at a safe size for all GPUs.
- Shading still comes from the lamp only; the photo's own lighting (from the
  museum's studio) is baked in and does not change with folds.
- Untested so far: `fit_to_rug`, the new UVs, and the saved-path fallback.
  The maintainer designs those test cases.
