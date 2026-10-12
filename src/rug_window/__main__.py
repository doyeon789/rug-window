"""Entry point: ``python -m rug_window``."""

import signal
import sys

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from rug_window import desktop
from rug_window.rug_widget import RugWidget


def main() -> int:
    """Create the Qt application, show the rug, and run the event loop.

    Order matters:

    1. Restore the default ``SIGINT`` handler so Ctrl+C in the terminal ends
       the process. Qt's C++ event loop never hands control back to Python's
       handler.
    2. Set a default ``QSurfaceFormat`` with an alpha buffer before creating
       ``QApplication``, so the translucent OpenGL window is not black.
    3. Create ``QApplication`` and ``RugWidget``, then ``show()`` the widget.
    4. Pass ``int(rug.winId())`` to ``desktop.place_above_desktop`` and
       ``desktop.disable_activation``. This happens here because the native
       window exists only after ``show()``.
    5. Run ``app.exec()``.

    Returns:
        The process exit code.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    surface_format = QSurfaceFormat()
    surface_format.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(surface_format)

    app = QApplication(sys.argv)
    rug = RugWidget()
    rug.show()

    # Let OSError propagate: a rug that cannot sit on the desktop is broken,
    # and a traceback says why faster than a rug floating over other apps.
    hwnd = int(rug.winId())
    desktop.place_above_desktop(hwnd)
    desktop.disable_activation(hwnd)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
