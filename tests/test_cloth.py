"""Tests for ``rug_window.cloth``.

The cases come from the worked examples in the explainer's learning notes.
"""

from itertools import pairwise

import numpy as np
import pytest

from rug_window.cloth import (
    ClothSimulation,
    relax_pairs,
    structural_pairs,
    verlet_step,
)


def test_grid_size_counts_gaps_not_particles() -> None:
    # Fencepost: n particles have n - 1 gaps between them.
    cloth = ClothSimulation(rows=40, cols=30, spacing=0.1, drop_height=1.0)
    positions = cloth.positions

    assert positions.shape == (40, 30, 3)
    assert positions.shape[0] * positions.shape[1] == 1200
    width = positions[..., 0].max() - positions[..., 0].min()
    height = positions[..., 1].max() - positions[..., 1].min()
    assert width == pytest.approx(2.9, abs=1e-5)
    assert height == pytest.approx(3.9, abs=1e-5)


def test_structural_pair_count_for_3_by_4_grid() -> None:
    a_index, b_index = structural_pairs(rows=3, cols=4)

    # Horizontal 3 rows x 3 gaps = 9, vertical 4 columns x 2 gaps = 8.
    assert len(a_index) == len(b_index) == 17


def test_verlet_step_matches_worked_heights() -> None:
    # No damping, gravity term -0.01 per step (acceleration -1, dt 0.1).
    previous, current = 5.0, 4.9
    heights = []
    for _ in range(3):
        nxt = float(verlet_step(current, previous, -1.0, 0.1, 1.0))
        previous, current = current, nxt
        heights.append(nxt)

    assert heights == pytest.approx([4.79, 4.67, 4.54])


def test_step_drops_cloth_further_each_step() -> None:
    cloth = ClothSimulation(rows=3, cols=3, spacing=0.1, drop_height=10.0)
    heights = [float(cloth.positions[..., 2].mean())]
    for _ in range(3):
        cloth.step(1 / 60)
        heights.append(float(cloth.positions[..., 2].mean()))

    drops = [before - after for before, after in pairwise(heights)]
    assert all(drop > 0 for drop in drops)
    assert drops[0] < drops[1] < drops[2]


def test_relax_pairs_moves_both_ends_half_way() -> None:
    positions = np.array([[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]])

    relax_pairs(positions, np.array([0]), np.array([1]), rest_length=1.0, stiffness=1.0)

    assert positions[0, 0] == pytest.approx(0.2)
    assert positions[1, 0] == pytest.approx(1.2)
