"""OpenGL renderer that draws the cloth grid as a lit, patterned mesh.

Must only be used while an OpenGL context is current (inside
``QOpenGLWidget.initializeGL`` / ``paintGL``).
"""

import numpy as np
from numpy.typing import NDArray


class ClothRenderer:
    """Turns a particle grid into a shaded triangle mesh on screen."""

    def __init__(self, rows: int, cols: int) -> None:
        """Compile shaders and allocate GPU buffers for a fixed-size grid.

        Args:
            rows: Number of particles along y.
            cols: Number of particles along x.
        """
        raise NotImplementedError

    def resize(self, width: int, height: int) -> None:
        """Update the viewport and projection after the widget is resized.

        Args:
            width: Viewport width in device pixels (logical size times
                ``devicePixelRatio()``).
            height: Viewport height in device pixels.
        """
        raise NotImplementedError

    def draw(self, positions: NDArray[np.float32]) -> None:
        """Upload positions, recompute normals, and draw one frame.

        Args:
            positions: Particle positions, shape ``(rows, cols, 3)``.
        """
        raise NotImplementedError
