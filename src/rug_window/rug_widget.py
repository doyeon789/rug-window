"""Transparent desktop widget that ties simulation, rendering, and input."""

from PySide6.QtGui import QMouseEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class RugWidget(QOpenGLWidget):
    """Frameless, translucent window showing the cloth rug.

    A timer advances the simulation and repaints about 60 times per second.
    Dragging with the left mouse button moves the whole window.
    """

    def __init__(self) -> None:
        """Configure window flags, transparency, and the frame timer."""
        raise NotImplementedError

    def initializeGL(self) -> None:  # noqa: N802 - Qt override
        """Create the renderer once the OpenGL context exists."""
        raise NotImplementedError

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 - Qt override
        """Forward the new size to the renderer."""
        raise NotImplementedError

    def paintGL(self) -> None:  # noqa: N802 - Qt override
        """Draw the current cloth state."""
        raise NotImplementedError

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Start dragging the window."""
        raise NotImplementedError

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Move the window with the cursor while dragging."""
        raise NotImplementedError
