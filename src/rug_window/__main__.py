"""Entry point: ``python -m rug_window`` or the ``rug-window`` launcher."""

import logging
import os
import signal
import sys
from pathlib import Path
from types import TracebackType

import win32api
import win32event
import winerror
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtWidgets import QApplication

from rug_window import desktop
from rug_window.rug_widget import RugWidget
from rug_window.textures import ASSETS_DIR
from rug_window.tray import RugTray

APP_ICON = ASSETS_DIR / "rug.ico"
# One named mutex per user session: a second launch finds it and exits.
_SINGLE_INSTANCE_MUTEX = "Local\\RugWindowSingleInstance"

logger = logging.getLogger(__name__)


def default_surface_format() -> QSurfaceFormat:
    """Return the OpenGL surface format the rug needs.

    OpenGL 3.3 Core for the renderer's shaders, an 8-bit alpha buffer so the
    translucent window is not black, and 4x multisampling to smooth the rug's
    edges.

    Returns:
        The format to pass to ``QSurfaceFormat.setDefaultFormat``.
    """
    surface_format = QSurfaceFormat()
    surface_format.setVersion(3, 3)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface_format.setAlphaBufferSize(8)
    # The renderer depth-tests; ask for the depth buffer explicitly.
    surface_format.setDepthBufferSize(24)
    surface_format.setSamples(4)
    return surface_format


def log_path() -> Path:
    """Return where the app writes its log (there is no console to print to)."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "rug-window" / "rug-window.log"


def _configure_logging() -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def log_uncaught(
        kind: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logger.critical("Uncaught exception", exc_info=(kind, value, traceback))
        sys.__excepthook__(kind, value, traceback)

    sys.excepthook = log_uncaught


def main() -> int:
    """Start the rug in the background with a tray icon to control it.

    Order matters:

    1. Exit at once if another copy is already running (named mutex), so
       double-clicking the shortcut twice does not stack two rugs.
    2. Log to a file and restore the default ``SIGINT`` handler (Ctrl+C still
       ends the process when started from a terminal).
    3. Set a default ``QSurfaceFormat`` with an alpha buffer before creating
       ``QApplication``, so the translucent OpenGL window is not black.
    4. Create ``QApplication`` (kept alive with no visible window, since the
       rug can be hidden from the tray) and ``RugWidget``, then ``show()`` it.
    5. Pass ``int(rug.winId())`` to ``desktop.place_above_desktop`` and
       ``desktop.disable_activation``. This happens here because the native
       window exists only after ``show()``.
    6. Add the tray icon, then run ``app.exec()``.

    Returns:
        The process exit code.
    """
    # None = default security; pywin32 accepts it though the stubs do not.
    mutex = win32event.CreateMutex(None, False, _SINGLE_INSTANCE_MUTEX)  # type: ignore[arg-type]
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return 0

    _configure_logging()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    QSurfaceFormat.setDefaultFormat(default_surface_format())

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon = QIcon(str(APP_ICON))
    app.setWindowIcon(icon)
    rug = RugWidget()
    rug.show()

    # Let OSError propagate: a rug that cannot sit on the desktop is broken,
    # and the log says why.
    hwnd = int(rug.winId())
    desktop.place_above_desktop(hwnd)
    desktop.disable_activation(hwnd)

    tray = RugTray(icon, rug, app)
    logger.info("Rug Window started")
    code = app.exec()
    tray.hide()
    del mutex
    return code


if __name__ == "__main__":
    raise SystemExit(main())
