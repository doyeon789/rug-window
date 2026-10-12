"""Development tool: put a "Rug Window" shortcut on the desktop.

Run from the repository root after ``uv sync``:

    uv run python tools/make_shortcut.py

The shortcut starts ``.venv/Scripts/rug-window.exe``, the windowless launcher
that ``uv sync`` creates from ``[project.gui-scripts]``, so no console opens.
"""

from pathlib import Path

import win32com.client

REPO = Path(__file__).resolve().parent.parent
LAUNCHER = REPO / ".venv" / "Scripts" / "rug-window.exe"
ICON = REPO / "src" / "rug_window" / "assets" / "rug.ico"


def main() -> None:
    """Create or update the desktop shortcut."""
    if not LAUNCHER.is_file():
        raise FileNotFoundError(f"{LAUNCHER} not found; run `uv sync` first")
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SpecialFolders("Desktop"))
    link_path = desktop / "Rug Window.lnk"
    link = shell.CreateShortcut(str(link_path))
    link.TargetPath = str(LAUNCHER)
    link.WorkingDirectory = str(REPO)
    link.IconLocation = f"{ICON},0"
    link.Description = "Sweep your messy desktop under a rug"
    link.Save()
    print(f"wrote {link_path}")


if __name__ == "__main__":
    main()
