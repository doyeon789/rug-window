"""OpenGL renderer that draws the cloth grid as a lit, textured, thick mesh.

The pure-numpy mesh helpers (``grid_triangle_indices``, ``grid_normals``,
``solidify``, ``solid_mesh_layout``) need no OpenGL and can be tested alone.
``ClothRenderer`` must only be used while an OpenGL context is current (inside
``QOpenGLWidget.initializeGL`` / ``paintGL``, or after ``makeCurrent()``).
"""

import math
from typing import Final

import numpy as np
from numpy.typing import NDArray
from OpenGL import GL
from OpenGL.GL import shaders
from PySide6.QtGui import QImage

from rug_window.cloth import RUG_THICKNESS
from rug_window.textures import DEFAULT_RUG_TEXTURE, load_texture

# Unit-less world-space vector (z up, same axes as ClothSimulation) pointing
# from the surface *toward* the light; normalized when used. Shading uses
# max(0, normal . LIGHT_DIRECTION), so flipping the sign would invert it.
# Tilted instead of straight up: an overhead light lights a flat rug evenly,
# so small wrinkles would not show.
LIGHT_DIRECTION: Final[tuple[float, float, float]] = (-0.4, 0.3, 1.0)
# Share of light that reaches every face regardless of its angle, so faces
# turned away from the light are dark but not black.
AMBIENT_LIGHT: Final = 0.35
# Degrees the camera leans from looking straight down toward looking from the
# front. Straight down (0) hides the rug's thickness.
CAMERA_TILT_DEG: Final = 30.0
# World box (metres) that always stays in view: the rug's footprint plus the
# height it is dropped from, so the fall fits in the window.
VIEW_X_RANGE: Final = (-0.05, 1.22)
VIEW_Y_RANGE: Final = (-0.05, 0.77)
VIEW_Z_RANGE: Final = (0.0, 0.8)
# How many grid cells one copy of the carpet texture spans. 18 cells match the
# checker size of the earlier flat placeholder.
TEXTURE_CELLS_PER_TILE: Final = 18.0

_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 normal;
layout(location = 2) in vec2 uv;
uniform mat4 mvp;
out vec3 v_normal;
out vec2 v_uv;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    v_normal = normal;
    v_uv = uv;
}
"""

_FRAGMENT_SHADER = """
#version 330 core
in vec3 v_normal;
in vec2 v_uv;
uniform sampler2D carpet;
uniform vec3 light_direction;
uniform float ambient;
out vec4 color;
void main() {
    float lambert = max(dot(normalize(v_normal), light_direction), 0.0);
    vec3 base = texture(carpet, v_uv).rgb;
    color = vec4(base * (ambient + (1.0 - ambient) * lambert), 1.0);
}
"""


def grid_triangle_indices(rows: int, cols: int) -> NDArray[np.uint32]:
    """Split every grid cell into two triangles.

    Particles are numbered row by row: ``(r, c)`` is ``r * cols + c``.

    Args:
        rows: Number of particle rows.
        cols: Number of particle columns.

    Returns:
        Vertex indices, shape ``(2 * (rows - 1) * (cols - 1), 3)``.
    """
    r, c = np.meshgrid(np.arange(rows - 1), np.arange(cols - 1), indexing="ij")
    top_left = (r * cols + c).ravel()
    top_right = top_left + 1
    bottom_left = top_left + cols
    bottom_right = bottom_left + 1
    first = np.stack([top_left, bottom_left, top_right], axis=1)
    second = np.stack([top_right, bottom_left, bottom_right], axis=1)
    return np.concatenate([first, second]).astype(np.uint32)


def grid_normals(positions: NDArray[np.floating]) -> NDArray[np.float32]:
    """Return a unit normal per particle of a ``(rows, cols, 3)`` grid.

    Takes the direction along the columns and along the rows at each particle
    (neighbor differences) and crosses them. A flat grid in the xy plane gets
    normals pointing up (+z).

    Args:
        positions: Particle positions, shape ``(rows, cols, 3)``.

    Returns:
        Unit normals, same shape, ``float32``.
    """
    along_cols = np.gradient(positions, axis=1)
    along_rows = np.gradient(positions, axis=0)
    normals = np.cross(along_cols, along_rows)
    length = np.linalg.norm(normals, axis=-1, keepdims=True)
    return (normals / np.maximum(length, 1e-12)).astype(np.float32)


def _boundary_ring(rows: int, cols: int) -> NDArray[np.intp]:
    """Return the grid's edge particles in order around the rim."""
    top = list(range(cols))
    right = [r * cols + cols - 1 for r in range(1, rows)]
    bottom = [(rows - 1) * cols + c for c in range(cols - 2, -1, -1)]
    left = [r * cols for r in range(rows - 2, 0, -1)]
    return np.array(top + right + bottom + left, dtype=np.intp)


def solid_mesh_layout(
    rows: int, cols: int
) -> tuple[NDArray[np.float32], NDArray[np.uint32]]:
    """Return the parts of the thick mesh that never change: UVs and indices.

    Vertex order matches ``solidify``: top face, bottom face, then the rim's
    top and bottom copies for the side band.

    Args:
        rows: Number of particle rows.
        cols: Number of particle columns.

    Returns:
        ``(uvs, indices)``: texture coordinates ``(n, 2)`` and a flat triangle
        index list.
    """
    count = rows * cols
    r, c = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    grid_uv = np.stack([c, r], axis=-1).reshape(-1, 2) / TEXTURE_CELLS_PER_TILE
    ring = _boundary_ring(rows, cols)
    uvs = np.concatenate([grid_uv, grid_uv, grid_uv[ring], grid_uv[ring]])

    faces = grid_triangle_indices(rows, cols)
    side_top = 2 * count + np.arange(len(ring))
    side_bottom = side_top + len(ring)
    next_top, next_bottom = np.roll(side_top, -1), np.roll(side_bottom, -1)
    side = np.concatenate(
        [
            np.stack([side_top, side_bottom, next_top], axis=1),
            np.stack([next_top, side_bottom, next_bottom], axis=1),
        ]
    )
    indices = np.concatenate([faces, faces + count, side]).astype(np.uint32)
    return uvs.astype(np.float32), indices.ravel()


def solidify(
    positions: NDArray[np.floating],
    normals: NDArray[np.floating],
    thickness: float,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Turn one simulated sheet into a thick slab for drawing.

    The top face sits ``thickness / 2`` along each normal and the bottom face
    the same distance against it. A side band joins the two along the rim, so
    the rug's edge shows its thickness.

    Args:
        positions: Sheet positions, shape ``(rows, cols, 3)``.
        normals: Unit normals from ``grid_normals``, same shape.
        thickness: Full thickness of the slab.

    Returns:
        ``(vertices, vertex_normals)``, each ``(n, 3)`` ``float32``, in the
        vertex order that ``solid_mesh_layout`` indexes.
    """
    rows, cols, _ = positions.shape
    flat_pos = positions.reshape(-1, 3)
    flat_n = normals.reshape(-1, 3)
    offset = flat_n * (thickness / 2)
    top, bottom = flat_pos + offset, flat_pos - offset

    ring = _boundary_ring(rows, cols)
    rim = flat_pos[ring]
    tangent = np.roll(rim, -1, axis=0) - np.roll(rim, 1, axis=0)
    outward = np.cross(tangent, flat_n[ring])
    # Flip any that point inward, judged against the sheet's centre.
    inward = np.einsum("ij,ij->i", outward, rim - flat_pos.mean(axis=0)) < 0
    outward[inward] *= -1
    outward /= np.maximum(np.linalg.norm(outward, axis=1, keepdims=True), 1e-12)

    vertices = np.concatenate([top, bottom, top[ring], bottom[ring]])
    vertex_normals = np.concatenate([flat_n, -flat_n, outward, outward])
    return vertices.astype(np.float32), vertex_normals.astype(np.float32)


def _view_projection(width: int, height: int) -> NDArray[np.float32]:
    """Return the tilted orthographic camera matrix (row-major)."""
    tilt = math.radians(CAMERA_TILT_DEG)
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    # Screen up mixes depth (y) and height (z); toward-camera depth is the
    # opposite mix. At tilt 0 this is a straight top-down view.
    view = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, cos_t, sin_t, 0.0],
            [0.0, -sin_t, cos_t, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    left, right = VIEW_X_RANGE
    y0, y1 = VIEW_Y_RANGE
    z0, z1 = VIEW_Z_RANGE
    bottom = y0 * cos_t + z0 * sin_t
    top = y1 * cos_t + z1 * sin_t
    # Grow one side of the box so the world keeps its proportions.
    box_aspect = (right - left) / (top - bottom)
    window_aspect = width / height
    if window_aspect > box_aspect:
        grow = ((top - bottom) * window_aspect - (right - left)) / 2
        left, right = left - grow, right + grow
    else:
        grow = ((right - left) / window_aspect - (top - bottom)) / 2
        bottom, top = bottom - grow, top + grow
    depth = 4.0
    ortho = np.array(
        [
            [2 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
            [0.0, 2 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
            # Larger toward-camera depth -> smaller NDC z -> drawn in front.
            [0.0, 0.0, -1 / depth, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    return (ortho @ view).astype(np.float32)


class ClothRenderer:
    """Turns a particle grid into a shaded, textured, thick mesh on screen.

    Each grid cell is split into two triangles. The triangle index list and
    texture coordinates depend only on the grid size, so they are uploaded
    once in ``__init__``. Positions and normals change every frame and are
    re-uploaded in ``draw``.

    Lifecycle, all with the OpenGL context current:

    1. ``__init__``: compile shaders, allocate GPU buffers, upload indices.
    2. ``resize`` / ``draw``: use them.
    3. ``release``: free them. Python garbage collection does not free GPU
       objects, so the owner must call this before the context is destroyed.

    Attributes:
        rows: Grid rows given at construction; ``draw`` checks against it.
        cols: Grid columns given at construction; ``draw`` checks against it.
    """

    def __init__(self, rows: int, cols: int) -> None:
        """Compile shaders and allocate GPU buffers for a fixed-size grid.

        Args:
            rows: Number of particles along y.
            cols: Number of particles along x.

        Raises:
            ValueError: If ``rows`` or ``cols`` is less than 2, since at least
                one cell is needed to form a triangle. ``ClothSimulation``
                requires 3 for its bending constraints, so it is always the
                stricter of the two.
        """
        if rows < 2 or cols < 2:
            raise ValueError(f"Need at least a 2 x 2 grid, got {rows} x {cols}")
        self.rows = rows
        self.cols = cols
        self._released = False
        self._mvp = _view_projection(1, 1)

        # Core profile needs a bound vertex array before a program can be
        # validated, so create it first.
        self._vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self._vao)
        self._program = shaders.compileProgram(
            shaders.compileShader(_VERTEX_SHADER, GL.GL_VERTEX_SHADER),
            shaders.compileShader(_FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER),
        )
        self._position_vbo, self._normal_vbo, self._uv_vbo, self._index_buffer = (
            GL.glGenBuffers(4)
        )
        uvs, indices = solid_mesh_layout(rows, cols)
        self._index_count = len(indices)
        self._bind_attribute(self._position_vbo, 0, 3)
        self._bind_attribute(self._normal_vbo, 1, 3)
        self._bind_attribute(self._uv_vbo, 2, 2)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL.GL_STATIC_DRAW)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self._index_buffer)
        GL.glBufferData(
            GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW
        )
        GL.glBindVertexArray(0)

        self._texture = self._upload_texture(load_texture(DEFAULT_RUG_TEXTURE))
        self._mvp_location = GL.glGetUniformLocation(self._program, "mvp")
        GL.glUseProgram(self._program)
        light = np.array(LIGHT_DIRECTION, dtype=np.float32)
        GL.glUniform3fv(
            GL.glGetUniformLocation(self._program, "light_direction"),
            1,
            light / np.linalg.norm(light),
        )
        GL.glUniform1f(GL.glGetUniformLocation(self._program, "ambient"), AMBIENT_LIGHT)
        GL.glUniform1i(GL.glGetUniformLocation(self._program, "carpet"), 0)
        GL.glUseProgram(0)

    def resize(self, width: int, height: int) -> None:
        """Update the viewport and projection after the widget is resized.

        A width or height of 0 (e.g. a minimized window) is ignored, so the
        projection never divides by zero.

        Args:
            width: Viewport width in device pixels (logical size times
                ``devicePixelRatio()``).
            height: Viewport height in device pixels.

        Raises:
            RuntimeError: If called after ``release``.
        """
        self._require_alive()
        if width <= 0 or height <= 0:
            return
        self._mvp = _view_projection(width, height)

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
            RuntimeError: If called after ``release``.
        """
        self._require_alive()
        if positions.shape != (self.rows, self.cols, 3):
            raise ValueError(
                f"Expected shape {(self.rows, self.cols, 3)}, got {positions.shape}"
            )
        if positions.dtype != np.float32:
            raise ValueError(f"Expected float32, got {positions.dtype}")
        if not positions.flags.c_contiguous:
            raise ValueError("Positions must be C-contiguous")

        vertices, normals = solidify(positions, grid_normals(positions), RUG_THICKNESS)

        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glUseProgram(self._program)
        GL.glUniformMatrix4fv(self._mvp_location, 1, GL.GL_TRUE, self._mvp)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
        GL.glBindVertexArray(self._vao)
        for buffer, data in (
            (self._position_vbo, vertices),
            (self._normal_vbo, normals),
        ):
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buffer)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_DYNAMIC_DRAW)
        GL.glDrawElements(GL.GL_TRIANGLES, self._index_count, GL.GL_UNSIGNED_INT, None)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)

    def release(self) -> None:
        """Free the shaders and GPU buffers.

        The first call needs the owning context to be current. Later calls do
        nothing and need no context. Afterwards ``draw`` and ``resize`` raise
        ``RuntimeError``.
        """
        if self._released:
            return
        self._released = True
        GL.glDeleteTextures([self._texture])
        GL.glDeleteBuffers(
            4,
            [self._position_vbo, self._normal_vbo, self._uv_vbo, self._index_buffer],
        )
        GL.glDeleteVertexArrays(1, [self._vao])
        GL.glDeleteProgram(self._program)

    def _require_alive(self) -> None:
        if self._released:
            raise RuntimeError("ClothRenderer used after release()")

    @staticmethod
    def _bind_attribute(buffer: int, location: int, size: int) -> None:
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buffer)
        GL.glEnableVertexAttribArray(location)
        GL.glVertexAttribPointer(location, size, GL.GL_FLOAT, GL.GL_FALSE, 0, None)

    @staticmethod
    def _upload_texture(image: QImage) -> int:
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        pixels = np.frombuffer(rgba.constBits(), dtype=np.uint8)
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGBA8,
            rgba.width(),
            rgba.height(),
            0,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            pixels,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        for name, value in (
            (GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT),
            (GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT),
            (GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR),
            (GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
        ):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, name, value)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        return int(texture)
