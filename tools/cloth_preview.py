"""Development tool: watch ClothSimulation drop and compare floor/drop options.

Run from the repository root:

    uv run python tools/cloth_preview.py

Left: side view (x vs height). Right: top view height
map, brighter means higher. Keys:

    f   floor friction: "grip" (FLOOR_FRICTION) <-> "slide" (0)
    t   drop pose: "tilted" (DROP_TILT) <-> "flat" (0)
    r   drop again

Starts with the app's defaults (grip + tilted). Tune FLOOR_FRICTION and
DROP_TILT in ``cloth.py`` and watch the result here.
"""

import tkinter as tk

import numpy as np

from rug_window import cloth
from rug_window.cloth import ClothSimulation

ROWS, COLS, SPACING, DROP_HEIGHT = 25, 40, 0.03, 0.3
DT = 1 / 60
FRAME_MS = 16

SIDE_W, SIDE_H, TOP_CELL = 520, 360, 12
PX_PER_M = 400
HEIGHT_EXAGGERATION = 1.0
GROUND_Y = SIDE_H - 40


def make_cloth(grip: bool, tilted: bool) -> ClothSimulation:
    """Create a cloth with the chosen friction mode and starting pose."""
    return ClothSimulation(
        ROWS,
        COLS,
        SPACING,
        DROP_HEIGHT,
        tilt=cloth.DROP_TILT if tilted else 0.0,
        floor_friction=cloth.FLOOR_FRICTION if grip else 0.0,
    )


def height_color(z: float, z_max: float) -> str:
    """Map a height to a blue-to-white color string."""
    t = min(max(z / z_max, 0.0), 1.0)
    r, g, b = int(20 + 235 * t), int(40 + 215 * t), int(80 + 175 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    """Open the preview window and run the simulation loop."""
    root = tk.Tk()
    root.title("Cloth preview")
    top_w, top_h = COLS * TOP_CELL, ROWS * TOP_CELL
    canvas = tk.Canvas(
        root, width=SIDE_W + top_w + 60, height=max(SIDE_H, top_h + 80), bg="#10141c"
    )
    canvas.pack()

    state = {"grip": True, "tilted": True}
    sim = make_cloth(**state)

    canvas.create_line(0, GROUND_Y, SIDE_W, GROUND_Y, fill="#555555")
    side_lines = [
        canvas.create_line(0, 0, 0, 0, fill="#6fa8dc", width=1) for _ in range(ROWS)
    ]
    left = SIDE_W + 30
    cells = [
        [
            canvas.create_rectangle(
                left + c * TOP_CELL,
                50 + r * TOP_CELL,
                left + (c + 1) * TOP_CELL,
                50 + (r + 1) * TOP_CELL,
                width=0,
            )
            for c in range(COLS)
        ]
        for r in range(ROWS)
    ]
    status = canvas.create_text(12, 12, anchor="nw", fill="#d9d9d9")
    canvas.create_text(
        12,
        SIDE_H - 12,
        anchor="sw",
        fill="#8a8a8a",
        text="f: friction   t: drop pose   r: drop again",
    )
    canvas.create_text(
        left, 30, anchor="w", fill="#8a8a8a", text="top view (bright = high)"
    )

    def on_key(event: tk.Event) -> None:
        nonlocal sim
        if event.char == "f":
            state["grip"] = not state["grip"]
        elif event.char == "t":
            state["tilted"] = not state["tilted"]
        elif event.char != "r":
            return
        sim = make_cloth(**state)

    def frame() -> None:
        sim.step(DT)
        p = sim.positions
        x0 = (SIDE_W - (COLS - 1) * SPACING * PX_PER_M) / 2
        for r, line in enumerate(side_lines):
            xs = x0 + p[r, :, 0] * PX_PER_M
            ys = GROUND_Y - p[r, :, 2] * PX_PER_M * HEIGHT_EXAGGERATION
            canvas.coords(line, *np.column_stack([xs, ys]).ravel().tolist())
        z = p[..., 2] - cloth.RUG_THICKNESS / 2
        z_max = max(float(z.max()), 0.02)
        for r in range(ROWS):
            for c in range(COLS):
                canvas.itemconfigure(cells[r][c], fill=height_color(z[r, c], z_max))
        footprint = np.ptp(p[..., 0]), np.ptp(p[..., 1])
        canvas.itemconfigure(
            status,
            text=(
                f"friction: {'grip' if state['grip'] else 'slide'}   "
                f"pose: {'tilted' if state['tilted'] else 'flat'}\n"
                f"highest point above floor: {z.max() * 100:.1f} cm   "
                f"footprint: {footprint[0]:.2f} x {footprint[1]:.2f} m "
                f"(flat {(COLS - 1) * SPACING:.2f} x {(ROWS - 1) * SPACING:.2f})"
            ),
        )
        root.after(FRAME_MS, frame)

    root.bind("<Key>", on_key)
    frame()
    root.mainloop()


if __name__ == "__main__":
    main()
