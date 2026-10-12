"""Development tool: draw the app icon (a small rug) from the carpet texture.

Run from the repository root:

    uv run python tools/make_icon.py

Writes ``src/rug_window/assets/rug.ico``. The icon is derived from the CC0
carpet texture bundled next to it.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
    QTransform,
)

from rug_window.textures import ASSETS_DIR, DEFAULT_RUG_TEXTURE, load_texture

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
    # Soft shadow, then the carpet with a light border band.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 70))
    painter.drawRoundedRect(rug.translated(6, 8), 10, 10)
    brush = QBrush(load_texture(DEFAULT_RUG_TEXTURE))
    brush.setTransform(QTransform.fromScale(0.35, 0.35))
    painter.setBrushOrigin(rug.topLeft())
    painter.setBrush(brush)
    painter.setPen(QPen(QColor(200, 175, 120), 8))
    painter.drawRoundedRect(rug, 10, 10)
    painter.end()

    out = ASSETS_DIR / "rug.ico"
    if not image.save(str(out), "ICO"):
        raise OSError(f"Could not write {out}")
    print(f"wrote {out}")
    del app


if __name__ == "__main__":
    main()
