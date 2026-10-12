"""Verlet cloth simulation on a rectangular particle grid.

Pure numpy, no Qt or OpenGL, so it can be tested in isolation. Units are
metres: x/y span the floor plane and z points up, with the floor at ``z = 0``.
"""

import numpy as np
import numpy.typing as npt
from numpy.typing import NDArray
from scipy.spatial import cKDTree

# Fraction of velocity kept each step; acts like air resistance so the cloth
# settles instead of rippling forever.
DAMPING = 0.99
# Metres per second squared along z (Earth gravity).
GRAVITY = -9.8
# More passes make the cloth stiffer but slower; too few make it stretchy.
CONSTRAINT_ITERATIONS = 8
# The cloth is simulated as one sheet; the renderer draws it this thick. The
# floor collision keeps the sheet half a thickness above the floor so the
# drawn bottom face rests on z = 0.
RUG_THICKNESS = 0.012
# Fraction of each bending correction applied (0..1). High for a thick rug:
# it folds into large, round wrinkles instead of sharp creases.
BENDING_STIFFNESS = 0.9
# How strongly the floor grips touching particles (0..1): the fraction of
# their horizontal movement in a step that is cancelled. At 1 they cannot
# slide at all, so the part of the rug that lands first stays put and the rest
# piles up into wrinkles. Lower values let the rug slide flat.
FLOOR_FRICTION = 1.0
# Default starting tilt: extra drop height per metre along x, so one side
# lands first. A rug dropped perfectly level lands perfectly flat.
DROP_TILT = 0.4

# While a point is held, no particle may get farther from it than it was in
# the flat rug, plus this fraction. Without these invisible tethers the cloth
# near the held point stretches like rubber when the mouse moves fast.
TETHER_SLACK = 0.02

# Self-collision: particles of different layers (a fold lying on the rug)
# are pushed apart until they are this many grid spacings apart, so a fold
# rests on top instead of sinking through. Pairs that were already this close
# in the flat rug (around a crease) are left alone.
SELF_COLLISION_SPACINGS = 1.0
SELF_COLLISION_IGNORE_REST_SPACINGS = 2.5
# Heights count for less than sideways distance when measuring "too close",
# so layers keep more vertical room. Without this, a particle above the gap
# between four particles below sits only about half a spacing higher, less
# than the drawn rug thickness, and the layers look like they pass through.
SELF_COLLISION_Z_SCALE = 0.7
# Pairs are searched once per step, within this multiple of the collision
# distance, then pushed apart in every constraint pass (searching is the slow
# part, pushing is cheap).
SELF_COLLISION_SEARCH_MARGIN = 1.5

# Desktop icons under the rug: each raises the floor into a flat-topped hill
# this high, sloping down to the plain floor over BUMP_FALLOFF around it.
BUMP_HEIGHT = 0.02
BUMP_FALLOFF = 0.03

_MIN_LENGTH = 1e-9

IndexPairs = tuple[NDArray[np.intp], NDArray[np.intp]]


def verlet_step(
    current: npt.ArrayLike,
    previous: npt.ArrayLike,
    acceleration: npt.ArrayLike,
    dt: float,
    damping: float,
) -> NDArray[np.floating]:
    """Predict the next position with Verlet integration.

    ``next = current + (current - previous) * damping + acceleration * dt**2``.
    The displacement since the previous step stands in for velocity.

    Args:
        current: Position now.
        previous: Position one step ago.
        acceleration: Acceleration applied during this step.
        dt: Time step in seconds.
        damping: Fraction of velocity kept (1 means no damping).

    Returns:
        The predicted position, with the broadcast shape of the inputs.
    """
    cur = np.asarray(current)
    velocity_term = (cur - np.asarray(previous)) * damping
    return cur + velocity_term + np.asarray(acceleration) * dt * dt


def relax_pairs(
    positions: NDArray[np.floating],
    a_index: NDArray[np.intp],
    b_index: NDArray[np.intp],
    rest_length: float,
    stiffness: float,
) -> None:
    """Move each particle pair toward its rest distance, in place.

    Each end moves half of the length error, scaled by ``stiffness``. Updates
    are applied to all pairs at once, so no particle may appear in two pairs
    of the same call.

    This is the reference version with index lists. ``ClothSimulation`` runs
    the same math on grid slices (``_relax_views``), which is faster; the two
    are checked to cover exactly the same pairs.

    Args:
        positions: Particle positions, shape ``(n, 3)``. Modified in place.
        a_index: First particle of each pair.
        b_index: Second particle of each pair.
        rest_length: Distance each pair should have.
        stiffness: Fraction of the correction to apply (0..1).
    """
    delta = positions[b_index] - positions[a_index]
    length = np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), _MIN_LENGTH)
    correction = delta * ((length - rest_length) / length * (0.5 * stiffness))
    positions[a_index] += correction
    positions[b_index] -= correction


def structural_pairs(rows: int, cols: int) -> IndexPairs:
    """Return the horizontal and vertical neighbor pairs of a grid.

    Particles are numbered row by row: particle ``(r, c)`` is ``r * cols + c``.

    Args:
        rows: Number of particle rows.
        cols: Number of particle columns.

    Returns:
        ``(a_index, b_index)`` with one entry per structural constraint:
        ``rows * (cols - 1)`` horizontal plus ``cols * (rows - 1)`` vertical.
    """
    batches = _pair_batches(rows, cols, 0, 1) + _pair_batches(rows, cols, 1, 0)
    return (
        np.concatenate([a for a, _ in batches]),
        np.concatenate([b for _, b in batches]),
    )


def _pair_batches(rows: int, cols: int, dr: int, dc: int) -> list[IndexPairs]:
    """Return the pairs ``(r, c) - (r + dr, c + dc)`` split into two batches.

    Within a batch no particle appears twice, so ``relax_pairs`` can update the
    whole batch at once. Pairs are grouped by ``(r // dr) % 2`` (or by column
    when ``dr`` is 0), like pairing people in a line as 1-2, 3-4 first and
    2-3, 4-5 second.
    """
    r, c = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    r2, c2 = r + dr, c + dc
    valid = (r2 >= 0) & (r2 < rows) & (c2 >= 0) & (c2 < cols)
    group = (r // dr) % 2 if dr else (c // abs(dc)) % 2
    a, b = r * cols + c, r2 * cols + c2
    return [(a[valid & (group == g)], b[valid & (group == g)]) for g in (0, 1)]


GridSlice = tuple[slice, slice]


def _slice_batches(
    rows: int, cols: int, dr: int, dc: int
) -> list[list[tuple[GridSlice, GridSlice]]]:
    """Return the same two batches as ``_pair_batches``, as grid slices.

    Every batch is a regular stripe pattern on the grid (every other row,
    every other pair of columns, ...), so it can be written as plain slices.
    Slices give numpy views: the constraint solver then works in place on the
    grid instead of gathering and scattering particles by index list, which
    is several times faster.

    Returns:
        Two batches; each is a list of ``(a_slice, b_slice)`` pairs, where
        ``grid[a_slice]`` and ``grid[b_slice]`` line up particle by particle.
    """
    step = abs(dr) if dr else abs(dc)
    period = 2 * step
    batches = []
    for group in (0, 1):
        pairs = []
        for offset in range(group * step, group * step + step):
            if dr:
                rows_a = slice(offset, rows - dr, period)
                rows_b = slice(offset + dr, rows, period)
                if dc == 0:
                    cols_a = cols_b = slice(None)
                elif dc > 0:
                    cols_a, cols_b = slice(0, cols - dc), slice(dc, cols)
                else:
                    cols_a, cols_b = slice(-dc, cols), slice(0, cols + dc)
            else:
                rows_a = rows_b = slice(None)
                cols_a = slice(offset, cols - dc, period)
                cols_b = slice(offset + dc, cols, period)
            pairs.append(((rows_a, cols_a), (rows_b, cols_b)))
        batches.append(pairs)
    return batches


def _relax_views(
    a: NDArray[np.float32], b: NDArray[np.float32], rest_length: float, stiffness: float
) -> None:
    """``relax_pairs`` for two aligned grid views, updated in place."""
    delta = b - a
    length = np.sqrt(np.einsum("...i,...i->...", delta, delta))[..., None]
    np.maximum(length, _MIN_LENGTH, out=length)
    correction = delta * ((length - rest_length) / length * (0.5 * stiffness))
    a += correction
    b -= correction


def bump_heights(
    xy: NDArray[np.floating],
    rects: NDArray[np.floating],
    height: float = BUMP_HEIGHT,
    falloff: float = BUMP_FALLOFF,
) -> NDArray[np.float32]:
    """Return how far the floor is raised at each point by the obstacles.

    Each obstacle rectangle is a flat-topped hill: ``height`` inside the
    rectangle, easing down to 0 at ``falloff`` outside it. Where hills
    overlap, the higher one wins.

    Args:
        xy: Points on the floor, shape ``(n, 2)``.
        rects: Obstacles as ``(x0, y0, x1, y1)`` rows, shape ``(m, 4)``.
        height: Hill height.
        falloff: Distance outside a rectangle over which its hill slopes to 0.

    Returns:
        Floor height above the plain floor at each point, shape ``(n,)``.
    """
    if len(rects) == 0:
        return np.zeros(len(xy), dtype=np.float32)
    x = xy[:, 0:1]
    y = xy[:, 1:2]
    dx = np.maximum(np.maximum(rects[:, 0] - x, x - rects[:, 2]), 0.0)
    dy = np.maximum(np.maximum(rects[:, 1] - y, y - rects[:, 3]), 0.0)
    distance = np.hypot(dx, dy)
    hills = height * np.clip(1.0 - distance / falloff, 0.0, 1.0) ** 2
    return hills.max(axis=1).astype(np.float32)


class ClothSimulation:
    """A grid of particles held together by distance constraints.

    Three constraint families shape the cloth:

    - structural: horizontal/vertical neighbors, resist stretching
    - shear: diagonal neighbors, resist skewing
    - bending: neighbors two cells apart, resist folding (controls wrinkles)
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        spacing: float,
        drop_height: float,
        tilt: float = DROP_TILT,
        floor_friction: float = FLOOR_FRICTION,
        origin: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """Lay the cloth out, tilted, above the floor and at rest.

        x runs along columns from 0 to ``(cols - 1) * spacing`` and y along
        rows from 0 to ``(rows - 1) * spacing``. The ``x = 0`` edge starts at
        ``drop_height`` and the cloth rises by ``tilt`` metres per metre of x,
        so that edge lands first.

        Args:
            rows: Number of particles along y.
            cols: Number of particles along x.
            spacing: Rest distance between neighboring particles.
            drop_height: Initial z of the ``x = 0`` edge.
            tilt: Extra starting height per metre along x. 0 drops it level.
            floor_friction: Fraction (0..1) of horizontal movement cancelled
                for particles touching the floor. See ``FLOOR_FRICTION``.
            origin: World ``(x, y)`` of the first particle, so the cloth can
                start anywhere on the floor.

        Raises:
            ValueError: If ``rows`` or ``cols`` is less than 3 (bending
                constraints need neighbors two cells apart), ``spacing`` is
                not positive, or ``floor_friction`` is outside 0..1.
        """
        if rows < 3 or cols < 3:
            raise ValueError(f"Need at least a 3 x 3 grid, got {rows} x {cols}")
        if spacing <= 0:
            raise ValueError(f"spacing must be positive, got {spacing}")
        if not 0 <= floor_friction <= 1:
            raise ValueError(f"floor_friction must be in 0..1, got {floor_friction}")
        self._floor_friction = floor_friction

        ys, xs = np.mgrid[0:rows, 0:cols]
        current = np.empty((rows, cols, 3), dtype=np.float32)
        current[..., 0] = origin[0] + xs * spacing
        current[..., 1] = origin[1] + ys * spacing
        current[..., 2] = drop_height + current[..., 0] * tilt
        self._current = current
        # The flat layout, used to measure tether lengths when grabbing.
        self._rest = current.reshape(-1, 3).copy()
        # previous == current: every particle starts with zero velocity.
        self._previous = current.copy()
        self._readonly = current.view()
        self._readonly.setflags(write=False)
        self._gravity = np.array([0.0, 0.0, GRAVITY], dtype=np.float32)

        diagonal = spacing * float(np.sqrt(2.0))
        families = [
            ((0, 1), spacing, 1.0),
            ((1, 0), spacing, 1.0),
            ((1, 1), diagonal, 1.0),
            ((1, -1), diagonal, 1.0),
            ((0, 2), 2 * spacing, BENDING_STIFFNESS),
            ((2, 0), 2 * spacing, BENDING_STIFFNESS),
        ]
        self._batches = [
            (pairs, rest, stiffness)
            for (dr, dc), rest, stiffness in families
            for pairs in _slice_batches(rows, cols, dr, dc)
        ]
        self._obstacles = np.zeros((0, 4), dtype=np.float32)
        self._bounds: tuple[float, float, float, float] | None = None
        self._grabbed: int | None = None
        self._grab_target = np.zeros(3, dtype=np.float32)
        self._tether_lengths = np.zeros(len(self._rest), dtype=np.float32)
        self._collision_distance = SELF_COLLISION_SPACINGS * spacing
        self._ignore_rest_distance = SELF_COLLISION_IGNORE_REST_SPACINGS * spacing
        self._collision_scale = np.array(
            [1.0, 1.0, SELF_COLLISION_Z_SCALE], dtype=np.float32
        )

    @property
    def positions(self) -> NDArray[np.float32]:
        """Current particle positions, shape ``(rows, cols, 3)``.

        Returns a read-only, C-contiguous ``float32`` view of the internal
        array rather than a copy, so reading it every frame allocates nothing
        and ``ClothRenderer.draw`` can upload it as is. Writing to it raises
        ``ValueError``. The values change on the next ``step`` call; copy the
        array if you need to keep a snapshot.
        """
        return self._readonly

    def nearest_particle(self, x: float, y: float, max_distance: float) -> int | None:
        """Return the particle closest to ``(x, y)`` on the floor plane.

        Args:
            x: World x in metres.
            y: World y in metres.
            max_distance: Ignore particles farther than this (metres).

        Returns:
            The flat particle index (``r * cols + c``), or ``None`` if no
            particle is within ``max_distance``.
        """
        flat = self._current.reshape(-1, 3)
        distance = np.hypot(flat[:, 0] - x, flat[:, 1] - y)
        index = int(np.argmin(distance))
        return index if distance[index] <= max_distance else None

    def grab(self, index: int, target: tuple[float, float, float]) -> None:
        """Pin one particle to a world point, like holding the rug there.

        Until ``release``, every ``step`` keeps the particle at the target
        (see ``move_grab``) while the rest of the cloth follows through the
        constraints. Particles still gripped by the floor resist, so pulling
        piles the cloth into wrinkles.

        Args:
            index: Flat particle index (``r * cols + c``).
            target: World point to hold it at.

        Raises:
            IndexError: If ``index`` is not a particle of this grid.
        """
        if not 0 <= index < self._current.shape[0] * self._current.shape[1]:
            raise IndexError(f"No particle {index}")
        self._grabbed = index
        self._tether_lengths = np.linalg.norm(
            self._rest - self._rest[index], axis=1
        ) * (1 + TETHER_SLACK)
        self.move_grab(target)

    def move_grab(self, target: tuple[float, float, float]) -> None:
        """Set where the held particle should be. Only used while one is held.

        Args:
            target: New world point to hold the particle at.
        """
        self._grab_target[:] = target

    def set_obstacles(self, rects: NDArray[np.floating]) -> None:
        """Replace the obstacles lying on the floor under the cloth.

        Args:
            rects: ``(x0, y0, x1, y1)`` rows in world metres, shape ``(m, 4)``.
                See ``bump_heights`` for the shape of the hill each makes.
        """
        self._obstacles = np.asarray(rects, dtype=np.float32).reshape(-1, 4)

    def set_bounds(self, bounds: tuple[float, float, float, float] | None) -> None:
        """Keep every particle inside a rectangle on the floor, like walls.

        Args:
            bounds: ``(x0, y0, x1, y1)`` in world metres, or ``None`` for no
                walls.
        """
        self._bounds = bounds

    def release(self) -> None:
        """Let go of the held particle. The wrinkles it made stay."""
        self._grabbed = None

    def max_displacement(self) -> float:
        """Return how far the fastest particle moved in the last step (metres).

        Near zero means the cloth has settled.
        """
        return float(np.abs(self._current - self._previous).max())

    def step(self, dt: float) -> None:
        """Advance the simulation by one time step.

        Order matters: integrate gravity, then apply the floor (push particles
        out of it and cancel part of their horizontal movement), then relax
        all constraints ``CONSTRAINT_ITERATIONS`` times, so the constraints
        have the last word on the cloth's shape. Friction applied after the
        constraints would undo their pull and leave the cloth stretched. Each
        pass also pushes apart layers that came too close (self-collision,
        pairs found once per step) and puts a held particle back on its
        target. After the passes, all particles are tethered to the held one,
        and finally everything is kept
        above the floor (height only, no friction) and inside the walls set by
        ``set_bounds``.

        Args:
            dt: Time step in seconds. Pass the same value every call (e.g.
                1/60): Verlet reuses the previous step's displacement as
                velocity, so a varying ``dt`` makes it slow down or explode.

        Raises:
            ValueError: If ``dt`` is not positive.
        """
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")

        nxt = verlet_step(self._current, self._previous, self._gravity, dt, DAMPING)
        np.copyto(self._previous, self._current)
        np.copyto(self._current, nxt)

        flat = self._current.reshape(-1, 3)
        self._collide_with_floor()
        self._pin_grabbed(flat)
        grid = self._current
        close_pairs = self._find_close_layers(flat)
        for _ in range(CONSTRAINT_ITERATIONS):
            for pairs, rest, stiffness in self._batches:
                for a_slice, b_slice in pairs:
                    _relax_views(grid[a_slice], grid[b_slice], rest, stiffness)
            self._separate_layers(flat, close_pairs)
            # The held particle acts as if infinitely heavy: undo whatever the
            # constraints did to it.
            self._pin_grabbed(flat)
        self._apply_tethers(flat)
        np.maximum(flat[:, 2], self._floor_heights(flat), out=flat[:, 2])
        self._pin_grabbed(flat)
        self._keep_inside_bounds(flat)

    def _pin_grabbed(self, flat: NDArray[np.float32]) -> None:
        if self._grabbed is not None:
            flat[self._grabbed] = self._grab_target

    def _keep_inside_bounds(self, flat: NDArray[np.float32]) -> None:
        """Push particles that crossed a wall back onto it."""
        if self._bounds is None:
            return
        x0, y0, x1, y1 = self._bounds
        np.clip(flat[:, 0], x0, x1, out=flat[:, 0])
        np.clip(flat[:, 1], y0, y1, out=flat[:, 1])

    def _find_close_layers(self, flat: NDArray[np.float32]) -> IndexPairs:
        """Find particle pairs from different layers that may collide this step.

        A KD-tree finds the pairs without measuring every pair (2,000
        particles would be 2 million pairs). Distances use heights scaled by
        ``SELF_COLLISION_Z_SCALE``; see there.
        """
        scaled = flat * self._collision_scale
        pairs = cKDTree(scaled).query_pairs(
            self._collision_distance * SELF_COLLISION_SEARCH_MARGIN,
            output_type="ndarray",
        )
        if len(pairs) == 0:
            empty = np.zeros(0, dtype=np.intp)
            return empty, empty
        a, b = pairs[:, 0], pairs[:, 1]
        rest_gap = np.linalg.norm(self._rest[a] - self._rest[b], axis=1)
        far_in_rest = rest_gap > self._ignore_rest_distance
        return a[far_in_rest], b[far_in_rest]

    def _separate_layers(self, flat: NDArray[np.float32], pairs: IndexPairs) -> None:
        """Push apart the given pairs that are closer than the collision distance.

        Each pair moves half the overlap apart, like the distance constraints,
        but only pushes, never pulls.
        """
        a, b = pairs
        if len(a) == 0:
            return
        delta = (flat[b] - flat[a]) * self._collision_scale
        distance = np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), _MIN_LENGTH)
        overlap = np.maximum(self._collision_distance - distance, 0.0)
        # Measured in the scaled space; dividing by the scale turns the push
        # back into real metres (a scaled-down height needs a bigger real push).
        push = delta * (overlap / distance * 0.5) / self._collision_scale
        # A particle can be in several pairs; add every push it gets.
        np.subtract.at(flat, a, push)
        np.add.at(flat, b, push)

    def _apply_tethers(self, flat: NDArray[np.float32]) -> None:
        """Pull back particles that got farther from the held point than rest."""
        if self._grabbed is None:
            return
        offset = flat - self._grab_target
        distance = np.linalg.norm(offset, axis=1)
        too_far = distance > self._tether_lengths
        scale = self._tether_lengths[too_far] / distance[too_far]
        flat[too_far] = self._grab_target + offset[too_far] * scale[:, None]

    def _floor_heights(self, flat: NDArray[np.float32]) -> NDArray[np.float32]:
        return RUG_THICKNESS / 2 + bump_heights(flat[:, :2], self._obstacles)

    def _collide_with_floor(self) -> None:
        current = self._current.reshape(-1, 3)
        previous = self._previous.reshape(-1, 3)
        floor = self._floor_heights(current)
        touching = current[:, 2] <= floor
        current[touching, 2] = floor[touching]
        # Undo part of this step's horizontal movement. Cancelling the position
        # change (not just the velocity) also undoes sliding caused by the
        # constraint passes, which is what lets the landed part hold still.
        current[touching, :2] += (
            previous[touching, :2] - current[touching, :2]
        ) * self._floor_friction
