"""Development tool: make the default rug texture from The Met's carpet photo.

Download the original photo of "Carpet", ca. 1550, Egypt (The Met, object
452309, public domain), then run from the repository root:

    curl -o carpet.jpg https://images.metmuseum.org/CRDImages/is/original/DT5456.jpg
    uv run python tools/make_rug_texture.py carpet.jpg

Writes ``src/rug_window/assets/met_452309_carpet.jpg``: the rug cut out of the
grey studio background, turned to lie landscape, and resized to exactly the
rug's proportions. Unlike ``fit_to_rug`` (used for the user's own images),
this stretches slightly instead of cropping, so the carpet's border stays
visible on all four sides.
"""

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QTransform

from rug_window.rug_widget import RUG_ASPECT
from rug_window.textures import DEFAULT_RUG_TEXTURE, load_texture

WIDTH = 2048
# The studio background is neutral grey; wool is coloured. A row or column
# belongs to the rug when this share of its pixels is saturated, which also
# drops the pale fringe at the two ends.
SATURATION_THRESHOLD = 40
RUG_SHARE = 0.85
# Extra margin cut inside the detected edge (fraction of the size), because
# the old carpet's edges are not perfectly straight.
INSET = 0.004


def rug_bounds(image: QImage) -> QRect:
    """Return the rectangle of ``image`` that is covered by the carpet."""
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = rgb.width(), rgb.height()
    rows = np.frombuffer(rgb.constBits(), np.uint8).reshape(height, rgb.bytesPerLine())
    pixels = rows[:, : width * 3].reshape(height, width, 3).astype(np.int16)
    saturated = pixels.max(axis=2) - pixels.min(axis=2) > SATURATION_THRESHOLD
    xs = np.flatnonzero(saturated.mean(axis=0) > RUG_SHARE)
    ys = np.flatnonzero(saturated.mean(axis=1) > RUG_SHARE)
    dx, dy = round(width * INSET), round(height * INSET)
    left, right = xs[0] + dx, xs[-1] - dx
    top, bottom = ys[0] + dy, ys[-1] - dy
    return QRect(int(left), int(top), int(right - left + 1), int(bottom - top + 1))


def main() -> None:
    """Cut, turn, and resize the photo given on the command line."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_rug_texture.py <original photo>")
    photo = load_texture(Path(sys.argv[1]))
    carpet = photo.copy(rug_bounds(photo))
    if carpet.height() > carpet.width():
        carpet = carpet.transformed(QTransform().rotate(90))
    texture = carpet.scaled(
        WIDTH,
        round(WIDTH / RUG_ASPECT),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not texture.save(str(DEFAULT_RUG_TEXTURE), "JPG", 90):
        raise OSError(f"Could not write {DEFAULT_RUG_TEXTURE}")
    print(f"wrote {DEFAULT_RUG_TEXTURE} ({texture.width()} x {texture.height()})")


if __name__ == "__main__":
    main()
