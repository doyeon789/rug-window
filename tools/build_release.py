"""Development tool: build the Windows release zip with PyInstaller.

Run from the repository root (close the running rug first):

    uv run python tools/build_release.py

Produces ``dist/RugWindow/`` (``RugWindow.exe`` plus its ``_internal``
folder) and ``dist/RugWindow-v<version>-windows.zip``, ready to attach to a
GitHub release. Users unzip it and double-click ``RugWindow.exe``; no Python
needed. Windows only.
"""

import shutil
import sys
import tomllib
from importlib.metadata import distribution
from pathlib import Path

import PyInstaller.__main__

REPO = Path(__file__).resolve().parent.parent
BUILD = REPO / "build"
DIST = REPO / "dist"
ASSETS = REPO / "src" / "rug_window" / "assets"
NAME = "RugWindow"
# Bundled packages whose license files must ship with the binaries.
LICENSED_PACKAGES = (
    "numpy",
    "scipy",
    "PyOpenGL",
    "PySide6-Essentials",
    "shiboken6",
    "pywin32",
)
_LICENSE_MARKERS = ("LICENSE", "COPYING", "NOTICE")


def version() -> str:
    """Read the version from ``pyproject.toml``."""
    with (REPO / "pyproject.toml").open("rb") as file:
        return str(tomllib.load(file)["project"]["version"])


def copy_licenses(target: Path) -> None:
    """Copy every bundled component's license texts into ``target``.

    PyInstaller does not keep the packages' ``.dist-info`` folders, so the
    BSD, PSF, and LGPL texts that must accompany the binaries are copied
    here explicitly: each package's own license files, Python's
    ``LICENSE.txt``, and the texts kept in the repository's ``licenses/``
    folder for components whose packages do not carry them: LGPL-3.0 and
    GPL-3.0 (the PySide6 wheel only has its commercial-license reference),
    Apache-2.0 (OpenSSL), and MIT (libffi).
    """
    if target.exists():
        shutil.rmtree(target)
    for name in LICENSED_PACKAGES:
        dist = distribution(name)
        for file in dist.files or []:
            if not any(marker in file.name.upper() for marker in _LICENSE_MARKERS):
                continue
            source = Path(str(dist.locate_file(file)))
            # Flatten the package-relative path into one file name.
            flat = str(file).replace("/", "__").replace("\\", "__")
            out = target / f"{name}-{dist.version}" / flat
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, out)
    python_dir = target / f"python-{sys.version.split()[0]}"
    python_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", python_dir / "LICENSE.txt")
    for text in (REPO / "licenses").glob("*.txt"):
        shutil.copy2(text, target / text.name)


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
            # ";" is PyInstaller's source/destination separator on Windows.
            "--add-data",
            f"{ASSETS};rug_window/assets",
            # PyOpenGL picks its platform and array handlers at run time.
            "--collect-submodules",
            "OpenGL",
            # Not used. (OpenSSL still ships: Qt's TLS plugin loads it, so
            # excluding Python's ssl module would not remove it.)
            "--exclude-module",
            "tkinter",
        ]
    )
    app_dir = DIST / NAME
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy2(REPO / name, app_dir / name)
    copy_licenses(app_dir / "licenses")
    archive = shutil.make_archive(
        str(DIST / f"{NAME}-v{version()}-windows"), "zip", DIST, NAME
    )
    print(f"built {archive}")


if __name__ == "__main__":
    main()
