"""Verlet cloth simulation on a rectangular particle grid.

Pure numpy, no Qt or OpenGL, so it can be tested in isolation. Units are
metres: x/y span the floor plane and z points up, with the floor at ``z = 0``.
"""

import numpy as np
import numpy.typing as npt
from numpy.typing import NDArray

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
    of the same call; ``ClothSimulation`` guarantees this by splitting each
    constraint direction into odd and even batches.

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
        current[..., 0] = xs * spacing
        current[..., 1] = ys * spacing
        current[..., 2] = drop_height + current[..., 0] * tilt
        self._current = current
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
            (a, b, rest, stiffness)
            for (dr, dc), rest, stiffness in families
            for a, b in _pair_batches(rows, cols, dr, dc)
        ]
        self._grabbed: int | None = None
        self._grab_target = np.zeros(3, dtype=np.float32)

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
        self.move_grab(target)

    def move_grab(self, target: tuple[float, float, float]) -> None:
        """Move the held particle's target. Does nothing if nothing is held.

        Args:
            target: New world point to hold the particle at.
        """
        self._grab_target[:] = target

    def release(self) -> None:
        """Let go of the held particle. The wrinkles it made stay."""
        self._grabbed = None

    def step(self, dt: float) -> None:
        """Advance the simulation by one time step.

        Integrates gravity, relaxes all constraints ``CONSTRAINT_ITERATIONS``
        times, then pushes particles that fell through the floor back onto it
        and cancels part of their horizontal movement (floor friction). A
        grabbed particle is held at its target throughout.

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
        self._pin_grabbed(flat)
        for _ in range(CONSTRAINT_ITERATIONS):
            for a, b, rest, stiffness in self._batches:
                relax_pairs(flat, a, b, rest, stiffness)
            # The held particle acts as if infinitely heavy: undo whatever the
            # constraints did to it.
            self._pin_grabbed(flat)

        self._collide_with_floor()
        self._pin_grabbed(flat)

    def _pin_grabbed(self, flat: NDArray[np.float32]) -> None:
        if self._grabbed is not None:
            flat[self._grabbed] = self._grab_target

    def _collide_with_floor(self) -> None:
        floor = RUG_THICKNESS / 2
        current = self._current.reshape(-1, 3)
        previous = self._previous.reshape(-1, 3)
        touching = current[:, 2] <= floor
        current[touching, 2] = floor
        # Undo part of this step's horizontal movement. Cancelling the position
        # change (not just the velocity) also undoes sliding caused by the
        # constraint passes, which is what lets the landed part hold still.
        current[touching, :2] += (
            previous[touching, :2] - current[touching, :2]
        ) * self._floor_friction
