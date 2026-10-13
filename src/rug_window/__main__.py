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
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

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
    translucent window is not black, and 2x multisampling to smooth the rug's
    edges. Each extra sample multiplies the memory of the screen-sized
    buffers, so 2x is the chosen trade-off between smooth edges and memory
    (measurements in ``docs/explainers/reduce-memory.md``).

    Returns:
        The format to pass to ``QSurfaceFormat.setDefaultFormat``.
    """
    surface_format = QSurfaceFormat()
    surface_format.setVersion(3, 3)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface_format.setAlphaBufferSize(8)
    # The renderer depth-tests; ask for the depth buffer explicitly.
    surface_format.setDepthBufferSize(24)
    surface_format.setSamples(2)
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
        encoding="utf-8",
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

    1. Log to a file first (there is no console), so even later startup
       failures are recorded.
    2. Exit at once if another copy is already running (named mutex), so
       double-clicking the shortcut twice does not stack two rugs.
    3. Restore the default ``SIGINT`` handler (Ctrl+C still ends the process
       when started from a terminal).
    4. Set a default ``QSurfaceFormat`` with an alpha buffer before creating
       ``QApplication``, so the translucent OpenGL window is not black.
    5. Create ``QApplication`` (kept alive with no visible window, since the
       rug can be hidden from the tray). Give up if there is no system tray:
       the tray is the only way to quit.
    6. Create ``RugWidget``, ``show()`` it, then ``attach_to_desktop()``
       (needs the native window, which exists only after ``show()``).
    7. Add the tray icon and run ``app.exec()``. Afterwards shut the rug
       down while the application still exists, so its GPU resources are
       released with a live context.

    Returns:
        The process exit code.
    """
    _configure_logging()
    # None = default security; pywin32 accepts it though the stubs do not.
    mutex = win32event.CreateMutex(None, False, _SINGLE_INSTANCE_MUTEX)  # type: ignore[arg-type]
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        logger.info("Rug Window is already running; exiting")
        return 0

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    QSurfaceFormat.setDefaultFormat(default_surface_format())

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon = QIcon(str(APP_ICON))
    app.setWindowIcon(icon)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("No system tray: the rug could not be turned off, not starting")
        return 1
    rug = RugWidget()
    rug.show()
    # Let OSError propagate: a rug that cannot sit on the desktop is broken,
    # and the log says why.
    rug.attach_to_desktop()

    tray = RugTray(icon, rug, app)
    logger.info("Rug Window started")
    code = app.exec()

    # Free the rug's GPU resources while ``app`` and the GL context still
    # exist (see ``RugWidget.shutdown``).
    tray.hide()
    rug.shutdown()
    logger.info("Rug Window stopped")
    # Keep the single-instance mutex until here.
    mutex.Close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
