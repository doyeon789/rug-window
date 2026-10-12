"""Development tool: build the Windows release zip with PyInstaller.

Run from the repository root (close the running rug first):

    uv run python tools/build_release.py

Produces ``dist/RugWindow/`` (``RugWindow.exe`` plus its ``_internal``
folder) and ``dist/RugWindow-v<version>-windows.zip``, ready to attach to a
GitHub release. Users unzip it and double-click ``RugWindow.exe``; no Python
needed.
"""

import shutil
import tomllib
from pathlib import Path

import PyInstaller.__main__

REPO = Path(__file__).resolve().parent.parent
BUILD = REPO / "build"
DIST = REPO / "dist"
ASSETS = REPO / "src" / "rug_window" / "assets"
NAME = "RugWindow"


def version() -> str:
    """Read the version from ``pyproject.toml``."""
    with (REPO / "pyproject.toml").open("rb") as file:
        return str(tomllib.load(file)["project"]["version"])


def main() -> None:
    """Build the app folder, add license files, and zip it."""
    entry = BUILD / "entry.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    # PyInstaller needs a script; this one just runs the package's main().
    entry.write_text(
        "from rug_window.__main__ import main\n\nraise SystemExit(main())\n",
        encoding="utf-8",
    )
    PyInstaller.__main__.run(
        [
            str(entry),
            "--name",
            NAME,
            "--noconfirm",
            "--clean",
            "--onedir",
            # No console window, like the gui-script launcher.
            "--windowed",
            "--icon",
            str(ASSETS / "rug.ico"),
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD / "pyinstaller"),
            "--specpath",
            str(BUILD),
            # textures.py finds the texture next to the rug_window package.
            "--add-data",
            f"{ASSETS}{';'}rug_window/assets",
            # PyOpenGL picks its platform and array handlers at run time.
            "--collect-submodules",
            "OpenGL",
            "--exclude-module",
            "tkinter",
        ]
    )
    app_dir = DIST / NAME
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy2(REPO / name, app_dir / name)
    archive = shutil.make_archive(
        str(DIST / f"{NAME}-v{version()}-windows"), "zip", DIST, NAME
    )
    print(f"built {archive}")


if __name__ == "__main__":
    main()
