"""Tests for the pure-numpy mesh helpers in ``rug_window.renderer``.

The case comes from the worked example in the explainer's learning notes.
"""

from rug_window.renderer import grid_triangle_indices


def test_triangle_count_uses_cells_not_particles() -> None:
    # 3 x 4 particles -> 2 x 3 = 6 cells -> 12 triangles (not 12 particles x 2).
    triangles = grid_triangle_indices(rows=3, cols=4)

    assert triangles.shape == (12, 3)
