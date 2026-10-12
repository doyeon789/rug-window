"""Tests for ``rug_window.textures``."""

from pathlib import Path

import pytest

from rug_window.textures import load_texture


def test_load_texture_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_texture(tmp_path / "missing.jpg")
