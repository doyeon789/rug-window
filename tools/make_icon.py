"""Development tool: draw the app icon (a small rug) from the carpet texture.

Run from the repository root:

    uv run python tools/make_icon.py

Writes ``src/rug_window/assets/rug.ico``. The icon is derived from the
public-domain carpet image bundled next to it (``DEFAULT_RUG_TEXTURE``).
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from rug_window.textures import (
    ASSETS_DIR,
    DEFAULT_RUG_TEXTURE,
    fit_to_rug,
    load_texture,
)

SIZE = 256


def main() -> None:
    """Paint the rug icon and save it as an ICO file."""
    app = QGuiApplication([])  # QPainter text/brush helpers need an app
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rug = QRectF(40, 60, SIZE - 80, SIZE - 120)
    # Fringe: short threads on the left and right ends.
    fringe = QPen(QColor(225, 215, 190), 4)
    fringe.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(fringe)
    for i in range(9):
        y = rug.top() + 8 + i * (rug.height() - 16) / 8
        painter.drawLine(int(rug.left()) - 18, int(y), int(rug.left()), int(y))
        painter.drawLine(int(rug.right()), int(y), int(rug.right()) + 18, int(y))
    # Soft shadow, then the whole carpet image (it has its own border).
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 70))
    painter.drawRoundedRect(rug.translated(6, 8), 8, 8)
    carpet = fit_to_rug(load_texture(DEFAULT_RUG_TEXTURE), rug.width() / rug.height())
    clip = QPainterPath()
    clip.addRoundedRect(rug, 8, 8)
    painter.setClipPath(clip)
    painter.drawImage(rug, carpet)
    painter.end()

    out = ASSETS_DIR / "rug.ico"
    if not image.save(str(out), "ICO"):
        raise OSError(f"Could not write {out}")
    print(f"wrote {out}")
    del app


if __name__ == "__main__":
    main()
