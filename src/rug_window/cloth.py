"""Verlet cloth simulation on a rectangular particle grid.

Pure numpy, no Qt or OpenGL, so it can be tested in isolation. Coordinates
are in rug units: x/y span the floor plane and z points up, with the floor at
``z = 0``.
"""

import numpy as np
from numpy.typing import NDArray

# Fraction of velocity kept each step; acts like air resistance so the cloth
# settles instead of rippling forever.
DAMPING = 0.99
GRAVITY = -9.8
# More passes make the cloth stiffer but slower; too few make it stretchy.
CONSTRAINT_ITERATIONS = 8


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
    ) -> None:
        """Lay the cloth out flat at ``drop_height`` above the floor.

        Args:
            rows: Number of particles along y.
            cols: Number of particles along x.
            spacing: Rest distance between neighboring particles.
            drop_height: Initial z of every particle.
        """
        raise NotImplementedError

    @property
    def positions(self) -> NDArray[np.float32]:
        """Current particle positions, shape ``(rows, cols, 3)``."""
        raise NotImplementedError

    def step(self, dt: float) -> None:
        """Advance the simulation by one time step.

        Integrates gravity, relaxes all constraints ``CONSTRAINT_ITERATIONS``
        times, then pushes particles that fell through the floor back onto it.

        Args:
            dt: Time step in seconds. Pass the same value every call (e.g.
                1/60): Verlet reuses the previous step's displacement as
                velocity, so a varying ``dt`` makes it slow down or explode.
        """
        raise NotImplementedError
