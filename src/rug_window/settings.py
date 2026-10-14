"""Choices that persist between runs (stored with ``QSettings``).

On Windows ``QSettings`` keeps them in the registry, under
HKEY_CURRENT_USER, Software, pizza-playground, rug-window.
"""

from pathlib import Path

from PySide6.QtCore import QSettings

_ORGANIZATION = "pizza-playground"
_APPLICATION = "rug-window"
_RUG_IMAGE_KEY = "rug/image"


def _settings() -> QSettings:
    return QSettings(_ORGANIZATION, _APPLICATION)


def saved_rug_image() -> Path | None:
    """Return the rug image the user chose last time, or ``None`` for the default.

    The path is returned as stored; the file may have been moved or deleted
    since, so the caller must handle it failing to load.
    """
    value = _settings().value(_RUG_IMAGE_KEY, "")
    return Path(str(value)) if value else None


def save_rug_image(path: Path | None) -> None:
    """Remember the chosen rug image for the next run (``None``: the default).

    Args:
        path: Image file the user chose, or ``None`` to forget it.
    """
    settings = _settings()
    if path is None:
        settings.remove(_RUG_IMAGE_KEY)
    else:
        settings.setValue(_RUG_IMAGE_KEY, str(path))
    settings.sync()
