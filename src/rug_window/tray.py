"""Notification-area (system tray) icon: the only control the rug app has.

The app runs without a console or a taskbar button, so the tray icon is how
the user finds it again: clicking it opens a small menu to hide or show the
rug, change its image, and quit.
"""

import logging
from pathlib import Path

from PySide6.QtGui import QAction, QCursor, QIcon, QImageReader
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from rug_window import settings
from rug_window.rug_widget import RugWidget

TOOLTIP = "Rug Window"
HIDE_TEXT = "Hide rug"
SHOW_TEXT = "Show rug"
CHOOSE_IMAGE_TEXT = "Choose rug image…"
DEFAULT_IMAGE_TEXT = "Use default rug"
QUIT_TEXT = "Quit"

logger = logging.getLogger(__name__)


class RugTray(QSystemTrayIcon):
    """Tray icon whose menu hides/shows the rug, changes its image, and quits."""

    def __init__(self, icon: QIcon, rug: RugWidget, app: QApplication) -> None:
        """Build the menu and show the icon in the notification area.

        Args:
            icon: Icon shown in the tray.
            rug: The rug window to hide, show, and re-dress.
            app: The application to quit.
        """
        super().__init__(icon)
        self._rug = rug
        self.setToolTip(TOOLTIP)

        self._menu = QMenu()
        self._toggle_action = QAction(HIDE_TEXT, self._menu)
        self._toggle_action.triggered.connect(self._toggle_rug)
        choose_action = QAction(CHOOSE_IMAGE_TEXT, self._menu)
        choose_action.triggered.connect(self._choose_image)
        default_action = QAction(DEFAULT_IMAGE_TEXT, self._menu)
        default_action.triggered.connect(self._use_default_image)
        quit_action = QAction(QUIT_TEXT, self._menu)
        quit_action.triggered.connect(app.quit)
        self._menu.addAction(self._toggle_action)
        self._menu.addSeparator()
        self._menu.addAction(choose_action)
        self._menu.addAction(default_action)
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

    def _choose_image(self) -> None:
        """Let the user pick an image file and dress the rug in it."""
        patterns = " ".join(
            f"*.{bytes(fmt.data()).decode()}"
            for fmt in QImageReader.supportedImageFormats()
        )
        current = settings.saved_rug_image()
        start_dir = str(current.parent) if current is not None else str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            None, "Choose rug image", start_dir, f"Images ({patterns})"
        )
        if not chosen:
            return
        path = Path(chosen)
        try:
            self._rug.set_rug_image(path)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Could not use %s as the rug image: %s", path, exc)
            QMessageBox.warning(
                None, "Rug Window", f"This file could not be used as a rug:\n{path}"
            )
            return
        settings.save_rug_image(path)
        logger.info("Rug image set to %s", path)

    def _use_default_image(self) -> None:
        """Go back to the bundled carpet and forget the user's choice."""
        self._rug.set_rug_image(None)
        settings.save_rug_image(None)
        logger.info("Rug image reset to the default")
