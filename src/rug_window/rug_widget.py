"""Transparent desktop widget that ties simulation, rendering, and input."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from rug_window.cloth import ClothSimulation
from rug_window.renderer import ClothRenderer

# Fits the renderer's view box (rug footprint plus drop height) at about
# 450 px per metre.
WINDOW_SIZE = (580, 470)
RUG_ROWS, RUG_COLS, RUG_SPACING = 25, 40, 0.03
DROP_HEIGHT = 0.3
FRAME_DT = 1 / 60
# Simulated before the first frame so the rug starts already settled. The
# live fall is added together with the frame timer.
SETTLE_STEPS = 240


class RugWidget(QOpenGLWidget):
    """Frameless, translucent window showing the cloth rug.

    A timer advances the simulation and repaints about 60 times per second.
    Dragging with the left mouse button moves the whole window.
    """

    def __init__(self) -> None:
        """Configure the window, center it, and settle the cloth.

        The window is frameless, translucent, and a ``Qt.Tool`` window so it
        has no taskbar button. It is shown without taking focus, because an
        activated window jumps to the front. OpenGL resources are not created
        here because no context exists yet; see ``initializeGL``. The Win32
        helpers in ``desktop`` are not called here either: they need the
        native window, which exists only after the widget is shown, so
        ``main`` calls them.

        The frame timer is not added yet: the cloth is dropped and settled
        here, off screen, and drawn standing still.
        """
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(*WINDOW_SIZE)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

        self._cloth = ClothSimulation(RUG_ROWS, RUG_COLS, RUG_SPACING, DROP_HEIGHT)
        for _ in range(SETTLE_STEPS):
            self._cloth.step(FRAME_DT)
        self._renderer: ClothRenderer | None = None
        self._drag_offset: QPoint | None = None

    def initializeGL(self) -> None:  # noqa: N802 - Qt override
        """Create the renderer once the OpenGL context exists.

        Stores it in ``self._renderer``, which is ``None`` until this runs.

        Also connects the context's ``aboutToBeDestroyed`` signal to a slot
        that calls ``makeCurrent()``, ``self._renderer.release()``, then
        ``doneCurrent()``. GPU objects can only be freed while the context is
        current, and nothing else frees them. The slot does nothing if
        ``self._renderer`` is ``None``.
        """
        self._renderer = ClothRenderer(RUG_ROWS, RUG_COLS)
        self.context().aboutToBeDestroyed.connect(self._release_renderer)

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 - Qt override
        """Forward the new size to the renderer in device pixels.

        Qt passes the size in logical pixels. It is multiplied by
        ``devicePixelRatio()`` and rounded with ``round()`` before it is
        forwarded, because the renderer works in device pixels and the ratio
        can be fractional (e.g. 1.25). ``int()`` would truncate it.

        Args:
            width: New width in logical pixels.
            height: New height in logical pixels.
        """
        if self._renderer is None:
            return
        ratio = self.devicePixelRatio()
        self._renderer.resize(round(width * ratio), round(height * ratio))

    def paintGL(self) -> None:  # noqa: N802 - Qt override
        """Draw the current cloth state.

        Does nothing while ``self._renderer`` is ``None``.
        """
        if self._renderer is None:
            return
        self._renderer.draw(self._cloth.positions)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Start dragging the window on a left-button press.

        Stores the drag offset, ``event.globalPosition()`` minus the window's
        top-left corner, so the grabbed point stays under the cursor.

        Args:
            event: The press event. Accepted, so the click is not passed on.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        cursor = event.globalPosition().toPoint()
        self._drag_offset = cursor - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Move the window with the cursor while the left button is held.

        Moves only if ``event.buttons()`` includes ``Qt.LeftButton``, so a
        right-button drag does nothing. The new top-left corner is
        ``event.globalPosition()`` minus the stored drag offset. No
        ``mouseReleaseEvent`` is needed: with mouse tracking off (the default),
        Qt sends move events only while a button is held.

        Args:
            event: The move event. Accepted while dragging.
        """
        is_left_held = bool(event.buttons() & Qt.MouseButton.LeftButton)
        if not is_left_held or self._drag_offset is None:
            event.ignore()
            return
        self.move(event.globalPosition().toPoint() - self._drag_offset)
        event.accept()

    def _release_renderer(self) -> None:
        if self._renderer is None:
            return
        self.makeCurrent()
        try:
            self._renderer.release()
        finally:
            self.doneCurrent()
