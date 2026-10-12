"""Transparent desktop widget that ties simulation, rendering, and input."""

from PySide6.QtGui import QMouseEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class RugWidget(QOpenGLWidget):
    """Frameless, translucent window showing the cloth rug.

    A timer advances the simulation and repaints about 60 times per second.
    Dragging with the left mouse button moves the whole window.
    """

    def __init__(self) -> None:
        """Configure the window and start the frame timer.

        The window is frameless, translucent, and a ``Qt.Tool`` window so it
        has no taskbar button. OpenGL resources are not created here because
        no context exists yet; see ``initializeGL``. The Win32 helpers in
        ``desktop`` are not called here either: they need the native window,
        which exists only after the widget is shown, so ``main`` calls them.
        """
        raise NotImplementedError

    def initializeGL(self) -> None:  # noqa: N802 - Qt override
        """Create the renderer once the OpenGL context exists.

        Also connects the context's ``aboutToBeDestroyed`` signal to a slot
        that calls ``makeCurrent()``, ``renderer.release()``, then
        ``doneCurrent()``. GPU objects can only be freed while the context is
        current, and nothing else frees them.
        """
        raise NotImplementedError

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 - Qt override
        """Forward the new size to the renderer in device pixels.

        Qt passes the size in logical pixels. It is multiplied by
        ``devicePixelRatio()`` before it is forwarded, because the renderer
        works in device pixels.

        Args:
            width: New width in logical pixels.
            height: New height in logical pixels.
        """
        raise NotImplementedError

    def paintGL(self) -> None:  # noqa: N802 - Qt override
        """Draw the current cloth state."""
        raise NotImplementedError

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Start dragging the window on a left-button press.

        Stores the drag offset, ``event.globalPosition()`` minus the window's
        top-left corner, so the grabbed point stays under the cursor.

        Args:
            event: The press event. Accepted, so the click is not passed on.
        """
        raise NotImplementedError

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
        raise NotImplementedError
