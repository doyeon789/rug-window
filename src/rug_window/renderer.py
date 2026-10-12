"""OpenGL renderer that draws the cloth grid as a lit, patterned mesh.

Must only be used while an OpenGL context is current (inside
``QOpenGLWidget.initializeGL`` / ``paintGL``, or after ``makeCurrent()``).
"""

import numpy as np
from numpy.typing import NDArray

# Direction the light comes from (normalized when used). Tilted instead of
# straight down: a light directly overhead lights a flat rug evenly, so small
# wrinkles would not show.
LIGHT_DIRECTION = (-0.4, 0.3, 1.0)


class ClothRenderer:
    """Turns a particle grid into a shaded triangle mesh on screen.

    Each grid cell is split into two triangles. The triangle index list
    depends only on the grid size, so it is uploaded once in ``__init__``.
    Positions and normals change every frame and are re-uploaded in ``draw``.

    Lifecycle, all with the OpenGL context current:

    1. ``__init__``: compile shaders, allocate GPU buffers, upload indices.
    2. ``resize`` / ``draw``: use them.
    3. ``release``: free them. Python garbage collection does not free GPU
       objects, so the owner must call this before the context is destroyed.
    """

    def __init__(self, rows: int, cols: int) -> None:
        """Compile shaders and allocate GPU buffers for a fixed-size grid.

        Args:
            rows: Number of particles along y.
            cols: Number of particles along x.

        Raises:
            ValueError: If ``rows`` or ``cols`` is less than 2, since at least
                one cell is needed to form a triangle.
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

        The array is copied byte for byte into a buffer sized at construction,
        so a wrong shape or dtype would draw garbage instead of failing. It is
        validated first.

        Args:
            positions: Particle positions, shape ``(rows, cols, 3)``,
                ``float32``, C-contiguous.

        Raises:
            ValueError: If the shape does not match the grid, the dtype is not
                ``float32``, or the array is not C-contiguous.
        """
        raise NotImplementedError

    def release(self) -> None:
        """Free the shaders and GPU buffers.

        Safe to call more than once. The renderer must not be used afterwards.
        """
        raise NotImplementedError
