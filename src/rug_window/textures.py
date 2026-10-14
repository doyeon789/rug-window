"""Loading images used as rug textures, and fitting them to the rug."""

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QTransform

ASSETS_DIR = Path(__file__).parent / "assets"
# A 16th-century carpet from The Met's Open Access collection (public domain,
# CC0); prepared by tools/make_rug_texture.py. See assets/LICENSE.md.
DEFAULT_RUG_TEXTURE = ASSETS_DIR / "met_452309_carpet.jpg"
# Longer side of a texture after fitting. Large photos are scaled down to this:
# more pixels than the rug covers on screen only cost GPU memory, and some
# GPUs refuse textures above 8192 or 16384 pixels.
MAX_TEXTURE_SIDE = 4096


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


def fit_to_rug(
    image: QImage, aspect: float, max_side: int = MAX_TEXTURE_SIDE
) -> QImage:
    """Turn, crop, and shrink an image so it covers the whole rug once.

    1. If the image is portrait and the rug landscape (or the other way
       round), turn it a quarter turn: photos of rugs are usually taken
       standing up.
    2. Cut equal amounts off both sides of the too-long direction, so the
       image has the rug's width-to-height ratio without being stretched.
    3. Scale it down (never up) until its longer side is at most
       ``max_side``.

    Args:
        image: The image to fit. Not modified.
        aspect: The rug's width divided by its height.
        max_side: Largest allowed width or height, in pixels.

    Returns:
        A new image with ratio ``aspect`` (to the nearest pixel).

    Raises:
        ValueError: If the image is empty, or ``aspect`` or ``max_side`` is
            not positive.
    """
    if image.isNull() or image.width() == 0 or image.height() == 0:
        raise ValueError("Cannot fit an empty image")
    if aspect <= 0 or max_side <= 0:
        raise ValueError(f"aspect and max_side must be positive: {aspect}, {max_side}")
    if (image.width() >= image.height()) != (aspect >= 1):
        image = image.transformed(QTransform().rotate(90))
    width, height = image.width(), image.height()
    if width / height > aspect:
        crop_width, crop_height = max(1, round(height * aspect)), height
    else:
        crop_width, crop_height = width, max(1, round(width / aspect))
    cropped = image.copy(
        QRect(
            (width - crop_width) // 2,
            (height - crop_height) // 2,
            crop_width,
            crop_height,
        )
    )
    scale = min(1.0, max_side / max(crop_width, crop_height))
    if scale == 1.0:
        return cropped
    return cropped.scaled(
        max(1, round(crop_width * scale)),
        max(1, round(crop_height * scale)),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
