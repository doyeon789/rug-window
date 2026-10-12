"""Transparent desktop widget that ties simulation, rendering, and input."""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPen,
    QTransform,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from rug_window.renderer import ClothRenderer
from rug_window.textures import DEFAULT_RUG_TEXTURE, load_texture

WINDOW_SIZE = (640, 420)
# Transparent border around the rug, so we can check that clicks pass through
# empty areas to the desktop icons underneath.
PLACEHOLDER_MARGIN = 40
PLACEHOLDER_EDGE = QColor(10, 25, 45, 230)
# The 1024 px carpet texture is drawn at a quarter size, so one 256 px tile
# shows a few checker squares and the rug shows several rows of them.
TEXTURE_SCALE = 0.25


class RugWidget(QOpenGLWidget):
    """Frameless, translucent window showing the cloth rug.

    A timer advances the simulation and repaints about 60 times per second.
    Dragging with the left mouse button moves the whole window.
    """

    def __init__(self) -> None:
        """Configure the window and center it on the primary screen.

        The window is frameless, translucent, and a ``Qt.Tool`` window so it
        has no taskbar button. It is shown without taking focus, because an
        activated window jumps to the front. OpenGL resources are not created
        here because no context exists yet; see ``initializeGL``. The Win32
        helpers in ``desktop`` are not called here either: they need the
        native window, which exists only after the widget is shown, so
        ``main`` calls them.

        The frame timer is added together with the cloth simulation; until
        then nothing moves, so nothing needs repainting.

        Raises:
            FileNotFoundError: If the bundled rug texture is missing.
            ValueError: If the bundled rug texture cannot be decoded.
        """
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(*WINDOW_SIZE)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

        self._texture = load_texture(DEFAULT_RUG_TEXTURE)
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

        Not wired up yet: ``ClothRenderer`` is implemented in a later step, so
        ``self._renderer`` stays ``None`` and ``paintGL`` draws a placeholder.
        """

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

        Until the renderer exists (``self._renderer`` is ``None``), draws a
        temporary flat placeholder rug, tiled with the carpet texture,
        instead. The placeholder goes away once
        ``ClothRenderer`` is wired up.
        """
        if self._renderer is None:
            self._paint_placeholder()

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

    def _paint_placeholder(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Start from fully transparent pixels; the default clear may be opaque.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rug = QRectF(self.rect()).adjusted(
            PLACEHOLDER_MARGIN,
            PLACEHOLDER_MARGIN,
            -PLACEHOLDER_MARGIN,
            -PLACEHOLDER_MARGIN,
        )
        brush = QBrush(self._texture)
        brush.setTransform(QTransform.fromScale(TEXTURE_SCALE, TEXTURE_SCALE))
        # Start the tiling at the rug's corner instead of the window's.
        painter.setBrushOrigin(rug.topLeft())
        painter.setPen(QPen(PLACEHOLDER_EDGE, 6))
        painter.setBrush(brush)
        painter.drawRoundedRect(rug, 24, 24)
        painter.end()
