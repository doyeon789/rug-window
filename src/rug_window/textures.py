"""Loading images used as rug textures."""

from pathlib import Path

from PySide6.QtGui import QImage

ASSETS_DIR = Path(__file__).parent / "assets"
DEFAULT_RUG_TEXTURE = ASSETS_DIR / "carpet006_color.jpg"


def load_texture(path: Path) -> QImage:
    """Load an image file to use as a rug texture.

    Returns a ``QImage`` rather than a ``QPixmap`` because a ``QPixmap`` needs
    a running ``QGuiApplication``, which would make loading harder to test.
    ``QBrush`` accepts either.

    Args:
        path: Image file to load.

    Returns:
        The loaded image.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file exists but Qt cannot decode it as an image.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Texture file not found: {path}")
    image = QImage(str(path))
    if image.isNull():
        raise ValueError(f"Not a readable image: {path}")
    return image
