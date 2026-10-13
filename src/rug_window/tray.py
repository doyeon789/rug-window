"""Notification-area (system tray) icon: the only control the rug app has.

The app runs without a console or a taskbar button, so the tray icon is how
the user finds it again: clicking it opens a small menu to hide or show the
rug and to quit.
"""

from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from rug_window.rug_widget import RugWidget

TOOLTIP = "Rug Window"
HIDE_TEXT = "Hide rug"
SHOW_TEXT = "Show rug"
QUIT_TEXT = "Quit"


class RugTray(QSystemTrayIcon):
    """Tray icon whose menu hides/shows the rug and quits the app."""

    def __init__(self, icon: QIcon, rug: RugWidget, app: QApplication) -> None:
        """Build the menu and show the icon in the notification area.

        Args:
            icon: Icon shown in the tray.
            rug: The rug window to hide and show.
            app: The application to quit.
        """
        super().__init__(icon)
        self._rug = rug
        self.setToolTip(TOOLTIP)

        self._menu = QMenu()
        self._toggle_action = QAction(HIDE_TEXT, self._menu)
        self._toggle_action.triggered.connect(self._toggle_rug)
        quit_action = QAction(QUIT_TEXT, self._menu)
        quit_action.triggered.connect(app.quit)
        self._menu.addAction(self._toggle_action)
        self._menu.addSeparator()
        self._menu.addAction(quit_action)
        self.setContextMenu(self._menu)

        # Right-click opens the menu by itself; open it on a left click too.
        self.activated.connect(self._on_activated)
        self.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._menu.popup(QCursor.pos())

    def _toggle_rug(self) -> None:
        if self._rug.isVisible():
            self._rug.hide()
            self._toggle_action.setText(SHOW_TEXT)
            return
        self._rug.show()
        # Showing may put the window back in the normal Z-order or re-apply
        # its styles; restore both.
        self._rug.attach_to_desktop()
        self._toggle_action.setText(HIDE_TEXT)
