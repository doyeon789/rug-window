"""OpenGL renderer that draws the cloth grid as a lit, textured, thick mesh.

The pure-numpy mesh helpers (``grid_triangle_indices``, ``grid_normals``,
``solidify``, ``solid_mesh_layout``) need no OpenGL and can be tested alone.
``ClothRenderer`` must only be used while an OpenGL context is current (inside
``QOpenGLWidget.initializeGL`` / ``paintGL``, or after ``makeCurrent()``).
"""

from functools import lru_cache
from typing import Final

import numpy as np
from numpy.typing import NDArray
from OpenGL import GL
from OpenGL.GL import shaders
from PySide6.QtGui import QImage

from rug_window.cloth import RUG_THICKNESS
from rug_window.textures import DEFAULT_RUG_TEXTURE, load_texture

# One lamp hangs this high (metres) above the centre of the screen. Faces
# turned toward it are bright, faces turned away are darker, which is what
# shows the folds when seen from straight above.
LIGHT_HEIGHT: Final = 4.0
# Share of light that reaches every face regardless of its angle, so faces
# turned away from the light are dark but not black.
AMBIENT_LIGHT: Final = 0.35
# Screen scale: logical pixels per metre. The camera looks straight down, so
# world x/y map to screen x/y by this factor (world y grows upward, screen y
# downward).
PX_PER_METRE: Final = 600.0
# Drop shadow: each point of the rug projected from the lamp onto the floor,
# drawn as translucent black underneath. Projection pushes the shadow away
# from the screen centre by ``height / (LIGHT_HEIGHT - height)`` of the
# point's distance from it, so raised parts (folds, a held corner) cast a
# longer shadow. A flat rug is treated as raised by SHADOW_BASE_HEIGHT so it
# still casts a thin rim of shadow.
SHADOW_BASE_HEIGHT: Final = 0.08
SHADOW_OPACITY: Final = 0.35
# Toward-camera depth range (metres) kept by the depth buffer.
_DEPTH_RANGE = 2.0
# The simulation grid is drawn this many times finer: smooth curves are
# fitted through the particles (Catmull-Rom) and the mesh is built from the
# fitted points. Physics stays at the coarse grid; only drawing gets finer, so
# triangle edges and saw-toothed folds no longer show.
RENDER_SUBDIVISIONS: Final = 3
# How many grid cells one copy of the carpet texture spans. 27 cells of 2 cm
# match the checker size of the earlier flat placeholder.
TEXTURE_CELLS_PER_TILE: Final = 27.0

_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 normal;
layout(location = 2) in vec2 uv;
uniform mat4 mvp;
out vec3 v_position;
out vec3 v_normal;
out vec2 v_uv;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    v_position = position;
    v_normal = normal;
    v_uv = uv;
}
"""

_FRAGMENT_SHADER = """
#version 330 core
in vec3 v_position;
in vec3 v_normal;
in vec2 v_uv;
uniform sampler2D carpet;
uniform vec3 light_position;
uniform float ambient;
out vec4 color;
void main() {
    vec3 to_light = normalize(light_position - v_position);
    float lambert = max(dot(normalize(v_normal), to_light), 0.0);
    vec3 base = texture(carpet, v_uv).rgb;
    color = vec4(base * (ambient + (1.0 - ambient) * lambert), 1.0);
}
"""

_SHADOW_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 position;
uniform mat4 mvp;
uniform vec3 light_position;
uniform float base_height;
void main() {
    // Project from the lamp onto the floor (similar triangles).
    float height = min(position.z + base_height, light_position.z * 0.9);
    float stretch = height / (light_position.z - height);
    vec2 shifted = position.xy + (position.xy - light_position.xy) * stretch;
    gl_Position = mvp * vec4(shifted, 0.0, 1.0);
}
"""

_SHADOW_FRAGMENT_SHADER = """
#version 330 core
uniform float opacity;
out vec4 color;
void main() {
    color = vec4(0.0, 0.0, 0.0, opacity);
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
    rows: int, cols: int, cells_per_tile: float = TEXTURE_CELLS_PER_TILE
) -> tuple[NDArray[np.float32], NDArray[np.uint32]]:
    """Return the parts of the thick mesh that never change: UVs and indices.

    Vertex order matches ``solidify``: top face, bottom face, then the rim's
    top and bottom copies for the side band.

    Args:
        rows: Number of particle rows.
        cols: Number of particle columns.
        cells_per_tile: Grid cells covered by one copy of the texture.

    Returns:
        ``(uvs, indices)``: texture coordinates ``(n, 2)`` and a flat triangle
        index list.
    """
    count = rows * cols
    r, c = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    grid_uv = np.stack([c, r], axis=-1).reshape(-1, 2) / cells_per_tile
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


def screen_to_world(x: float, y: float, height: float) -> tuple[float, float]:
    """Convert a point in the window to world coordinates on the floor.

    The camera looks straight down, so this is just the screen scale plus a
    flip: screen y grows downward, world y grows upward.

    Args:
        x: Logical pixels from the window's left edge.
        y: Logical pixels from the window's top edge.
        height: Window height in logical pixels.

    Returns:
        ``(world_x, world_y)`` in metres.
    """
    return x / PX_PER_METRE, (height - y) / PX_PER_METRE


@lru_cache
def _catmull_rom_matrix(count: int, factor: int) -> NDArray[np.float32]:
    """Return the matrix that turns ``count`` points into a finer curve.

    Row ``j`` holds the Catmull-Rom weights of the four coarse points around
    fine point ``j``. The curve passes exactly through every coarse point.
    Ends repeat their edge point. Cached: it depends only on the sizes.
    """
    fine = (count - 1) * factor + 1
    t = np.arange(fine) / factor
    start = np.minimum(t.astype(int), count - 2)
    u = (t - start)[:, None]
    weights = np.hstack(
        [
            (-(u**3) + 2 * u**2 - u) / 2,
            (3 * u**3 - 5 * u**2 + 2) / 2,
            (-3 * u**3 + 4 * u**2 + u) / 2,
            (u**3 - u**2) / 2,
        ]
    )
    matrix = np.zeros((fine, count))
    for k in range(4):
        neighbor = np.clip(start - 1 + k, 0, count - 1)
        np.add.at(matrix, (np.arange(fine), neighbor), weights[:, k])
    return matrix.astype(np.float32)


def subdivide_grid(positions: NDArray[np.floating], factor: int) -> NDArray[np.float32]:
    """Fit smooth curves through a particle grid and sample them more finely.

    Catmull-Rom curves pass through every particle, so a ``(rows, cols, 3)``
    grid becomes ``((rows - 1) * factor + 1, (cols - 1) * factor + 1, 3)``
    with the original particles still on it. The weights are a fixed matrix
    per grid size, so each frame is just two small matrix products.

    Args:
        positions: Particle positions, shape ``(rows, cols, 3)``.
        factor: How many fine cells replace one coarse cell along each side.

    Returns:
        The finer grid, ``float32``.
    """
    rows, cols, _ = positions.shape
    along_rows = _catmull_rom_matrix(rows, factor)
    along_cols = _catmull_rom_matrix(cols, factor)
    # Rows first: (fine_rows, rows) @ (rows, cols * 3).
    fine = (along_rows @ positions.reshape(rows, -1)).reshape(-1, cols, 3)
    # Then columns: (fine_rows, 3, cols) @ (cols, fine_cols).
    fine = (fine.transpose(0, 2, 1) @ along_cols.T).transpose(0, 2, 1)
    return np.ascontiguousarray(fine, dtype=np.float32)


def _view_projection(width: float, height: float) -> NDArray[np.float32]:
    """Return the top-down orthographic camera matrix (row-major).

    The visible world box is the whole window: ``width / PX_PER_METRE`` by
    ``height / PX_PER_METRE`` metres, with the origin at the bottom-left.
    """
    world_w, world_h = width / PX_PER_METRE, height / PX_PER_METRE
    return np.array(
        [
            [2 / world_w, 0.0, 0.0, -1.0],
            [0.0, 2 / world_h, 0.0, -1.0],
            # Higher z is closer to the camera -> smaller NDC z -> in front.
            [0.0, 0.0, -1 / _DEPTH_RANGE, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


class ClothRenderer:
    """Turns a particle grid into a shaded, textured, thick mesh on screen.

    The grid is drawn ``RENDER_SUBDIVISIONS`` times finer (see
    ``subdivide_grid``), and each fine cell is split into two triangles. The
    triangle index list and texture coordinates depend only on the grid size,
    so they are uploaded
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
        self._light_position = np.array([0.0, 0.0, LIGHT_HEIGHT], dtype=np.float32)

        # Core profile needs a bound vertex array before a program can be
        # validated, so create it first.
        self._vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self._vao)
        self._program = shaders.compileProgram(
            shaders.compileShader(_VERTEX_SHADER, GL.GL_VERTEX_SHADER),
            shaders.compileShader(_FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER),
        )
        self._shadow_program = shaders.compileProgram(
            shaders.compileShader(_SHADOW_VERTEX_SHADER, GL.GL_VERTEX_SHADER),
            shaders.compileShader(_SHADOW_FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER),
        )
        self._position_vbo, self._normal_vbo, self._uv_vbo, self._index_buffer = (
            GL.glGenBuffers(4)
        )
        self._render_rows = (rows - 1) * RENDER_SUBDIVISIONS + 1
        self._render_cols = (cols - 1) * RENDER_SUBDIVISIONS + 1
        uvs, indices = solid_mesh_layout(
            self._render_rows,
            self._render_cols,
            TEXTURE_CELLS_PER_TILE * RENDER_SUBDIVISIONS,
        )
        self._index_count = len(indices)
        # The top face comes first in the index list; the shadow uses only it.
        self._top_index_count = (
            2 * (self._render_rows - 1) * (self._render_cols - 1) * 3
        )
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
        self._light_location = GL.glGetUniformLocation(self._program, "light_position")
        GL.glUseProgram(self._program)
        GL.glUniform1f(GL.glGetUniformLocation(self._program, "ambient"), AMBIENT_LIGHT)
        GL.glUniform1i(GL.glGetUniformLocation(self._program, "carpet"), 0)
        self._shadow_mvp_location = GL.glGetUniformLocation(self._shadow_program, "mvp")
        self._shadow_light_location = GL.glGetUniformLocation(
            self._shadow_program, "light_position"
        )
        GL.glUseProgram(self._shadow_program)
        GL.glUniform1f(
            GL.glGetUniformLocation(self._shadow_program, "base_height"),
            SHADOW_BASE_HEIGHT,
        )
        GL.glUniform1f(
            GL.glGetUniformLocation(self._shadow_program, "opacity"), SHADOW_OPACITY
        )
        GL.glUseProgram(0)

    def resize(self, width: float, height: float) -> None:
        """Update the projection after the widget is resized.

        Takes logical pixels, because the world-to-screen scale
        (``PX_PER_METRE``) is defined in logical pixels; Qt sets the device
        pixel viewport itself. A width or height of 0 (e.g. a minimized
        window) is ignored, so the projection never divides by zero.

        Args:
            width: Window width in logical pixels.
            height: Window height in logical pixels.

        Raises:
            RuntimeError: If called after ``release``.
        """
        self._require_alive()
        if width <= 0 or height <= 0:
            return
        self._mvp = _view_projection(width, height)
        # The lamp stays above the centre of the window.
        self._light_position[:2] = (
            width / 2 / PX_PER_METRE,
            height / 2 / PX_PER_METRE,
        )

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

        fine = subdivide_grid(positions, RENDER_SUBDIVISIONS)
        vertices, normals = solidify(fine, grid_normals(fine), RUG_THICKNESS)

        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glBindVertexArray(self._vao)
        for buffer, data in (
            (self._position_vbo, vertices),
            (self._normal_vbo, normals),
        ):
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buffer)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_DYNAMIC_DRAW)

        # Shadow first, flat on the floor, over the cleared (0, 0, 0, 0)
        # background. Where the rug folds, several triangles cast shadow on
        # the same pixel; ordinary blending would stack them into darker
        # patches. MAX blending keeps the darkest single layer instead: the
        # color stays black and alpha becomes max(opacity, what is there).
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendEquation(GL.GL_MAX)
        GL.glUseProgram(self._shadow_program)
        GL.glUniformMatrix4fv(self._shadow_mvp_location, 1, GL.GL_TRUE, self._mvp)
        GL.glUniform3fv(self._shadow_light_location, 1, self._light_position)
        GL.glDrawElements(
            GL.GL_TRIANGLES, self._top_index_count, GL.GL_UNSIGNED_INT, None
        )
        GL.glBlendEquation(GL.GL_FUNC_ADD)
        GL.glDisable(GL.GL_BLEND)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glUseProgram(self._program)
        GL.glUniformMatrix4fv(self._mvp_location, 1, GL.GL_TRUE, self._mvp)
        GL.glUniform3fv(self._light_location, 1, self._light_position)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
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
        GL.glDeleteProgram(self._shadow_program)

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
