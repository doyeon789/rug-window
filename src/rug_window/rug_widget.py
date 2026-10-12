"""Full-screen transparent stage where the rug lies on the desktop."""

import logging

import numpy as np
from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QMouseEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from rug_window import desktop
from rug_window.cloth import RUG_THICKNESS, ClothSimulation
from rug_window.renderer import PX_PER_METRE, ClothRenderer, screen_to_world

# 2 cm grid: about 1.18 x 0.72 m, 2,220 particles.
RUG_ROWS, RUG_COLS, RUG_SPACING = 37, 60, 0.02
# Lower than the cloth's default grip so a pulled rug slides along the floor
# and bunches up, instead of only folding where it is held.
RUG_FLOOR_FRICTION = 0.65
FRAME_MS = 16
FRAME_DT = 1 / 60
# A grabbed point is lifted this high, so the held corner peels off the floor.
GRAB_LIFT = 0.03
# Weight: each frame the held point covers only this fraction of the way to
# the cursor, so a heavy rug lags a beat behind the hand instead of snapping
# to it. 1 would follow instantly (light); smaller feels heavier.
GRAB_FOLLOW = 0.25
# The cursor counts as "on the rug" within this distance of a particle. One
# grid spacing covers every point inside the rug.
RUG_HIT_RADIUS = RUG_SPACING
ICON_REFRESH_MS = 2000
# Once nothing has moved more than this (metres per frame) for this many
# frames, the rug is settled and the simulation sleeps until it is touched.
SETTLED_DISPLACEMENT = 2e-5
IDLE_FRAMES_BEFORE_SLEEP = 30

logger = logging.getLogger(__name__)


class RugWidget(QOpenGLWidget):
    """Frameless, translucent window covering the screen, showing the rug.

    A timer advances the simulation and repaints about 60 times per second.
    Pressing the left button on the rug grabs the nearest point of the cloth;
    dragging pulls it along, and releasing lets go. Clicks anywhere off the
    rug pass through to the desktop.
    """

    def __init__(self) -> None:
        """Cover the primary screen and lay the rug flat in its centre.

        The window is frameless, translucent, and a ``Qt.Tool`` window so it
        has no taskbar button. It is shown without taking focus, because an
        activated window jumps to the front. OpenGL resources are not created
        here because no context exists yet; see ``initializeGL``. The Win32
        helpers that place the window are called by ``main`` after ``show()``;
        click-through is toggled here every frame once the window exists.
        """
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.availableGeometry())

        world_w = self.width() / PX_PER_METRE
        world_h = self.height() / PX_PER_METRE
        rug_w = (RUG_COLS - 1) * RUG_SPACING
        rug_h = (RUG_ROWS - 1) * RUG_SPACING
        self._cloth = ClothSimulation(
            RUG_ROWS,
            RUG_COLS,
            RUG_SPACING,
            drop_height=RUG_THICKNESS / 2,
            tilt=0.0,
            floor_friction=RUG_FLOOR_FRICTION,
            origin=((world_w - rug_w) / 2, (world_h - rug_h) / 2),
        )
        # The screen edges are walls: no part of the rug may leave the screen.
        self._bounds = (0.0, 0.0, world_w, world_h)
        self._cloth.set_bounds(self._bounds)
        # Resolution, DPI, or taskbar changes move the walls with the screen.
        screen.availableGeometryChanged.connect(self._fit_to_screen)
        self._renderer: ClothRenderer | None = None
        self._idle_frames = 0
        self._is_grabbing = False
        # Where the cursor wants the held point, and where it actually is.
        self._grab_goal = np.zeros(3)
        self._grab_held = np.zeros(3)
        self._click_through: bool | None = None
        self._obstacles = np.zeros((0, 4))
        self._last_icon_error: str | None = None

        # Coarse timers can fire at ~31 ms on Windows; FRAME_DT assumes 16.
        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._frame_timer.timeout.connect(self._tick)
        self._frame_timer.start(FRAME_MS)
        self._icon_timer = QTimer(self)
        self._icon_timer.timeout.connect(self._refresh_obstacles)
        self._icon_timer.start(ICON_REFRESH_MS)
        self._refresh_obstacles()

    def initializeGL(self) -> None:  # noqa: N802 - Qt override
        """Create the renderer once the OpenGL context exists.

        Stores it in ``self._renderer``, which is ``None`` until this runs.

        Also connects the context's ``aboutToBeDestroyed`` signal to a slot
        that calls ``makeCurrent()``, ``self._renderer.release()``, then
        ``doneCurrent()``. GPU objects can only be freed while the context is
        current, and nothing else frees them. The slot does nothing if
        ``self._renderer`` is ``None``.
        """
        self._renderer = ClothRenderer(RUG_ROWS, RUG_COLS)
        self.context().aboutToBeDestroyed.connect(self._release_renderer)

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 - Qt override
        """Forward the new size to the renderer in logical pixels.

        Qt passes device pixels here. The renderer's screen scale is defined
        in logical pixels, so the widget's own (logical) size is forwarded
        instead.

        Args:
            width: New width in device pixels (unused).
            height: New height in device pixels (unused).
        """
        if self._renderer is None:
            return
        self._renderer.resize(self.width(), self.height())

    def paintGL(self) -> None:  # noqa: N802 - Qt override
        """Draw the current cloth state.

        Does nothing while ``self._renderer`` is ``None``.
        """
        if self._renderer is None:
            return
        self._renderer.draw(self._cloth.positions)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Grab the rug at the cursor on a left-button press.

        The nearest particle within ``RUG_HIT_RADIUS`` is held at the cursor,
        lifted by ``GRAB_LIFT``. Presses off the rug are ignored.

        Args:
            event: The press event. Accepted when it grabs the rug.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        x, y = self._to_world(event.position())
        index = self._cloth.nearest_particle(x, y, RUG_HIT_RADIUS)
        if index is None:
            event.ignore()
            return
        # Start from the particle itself so the grab does not jump.
        px, py, _ = self._cloth.positions.reshape(-1, 3)[index]
        self._grab_held[:] = (px, py, RUG_THICKNESS / 2 + GRAB_LIFT)
        self._grab_goal[:] = (x, y, RUG_THICKNESS / 2 + GRAB_LIFT)
        self._cloth.grab(index, self._held_point())
        self._idle_frames = 0
        self._is_grabbing = True
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Set where the held point of the rug should be pulled to.

        The point itself moves there over the next frames (``GRAB_FOLLOW``),
        which gives the rug its weight.

        Args:
            event: The move event. Accepted while holding the rug.
        """
        if not self._is_grabbing:
            event.ignore()
            return
        x, y = self._clamp_to_bounds(*self._to_world(event.position()))
        self._grab_goal[:] = (x, y, RUG_THICKNESS / 2 + GRAB_LIFT)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        """Let go of the rug when the left button is released.

        Needed now (unlike plain window dragging): the cloth keeps holding the
        point until it is told to let go.

        Args:
            event: The release event.
        """
        if event.button() == Qt.MouseButton.LeftButton and self._is_grabbing:
            self._cloth.release()
            self._is_grabbing = False
            event.accept()
        else:
            event.ignore()

    def _tick(self) -> None:
        # A lost release event (e.g. the button let go outside the window)
        # must not leave the rug held forever.
        left_down = QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton
        if self._is_grabbing and not left_down:
            self._cloth.release()
            self._is_grabbing = False
        if self._is_grabbing:
            self._idle_frames = 0
            self._grab_held += (self._grab_goal - self._grab_held) * GRAB_FOLLOW
            self._cloth.move_grab(self._held_point())
        # A settled rug needs no simulation or repaint; only watch the cursor.
        if self._idle_frames >= IDLE_FRAMES_BEFORE_SLEEP:
            self._update_click_through()
            return
        self._cloth.step(FRAME_DT)
        if self._cloth.max_displacement() < SETTLED_DISPLACEMENT:
            self._idle_frames += 1
        else:
            self._idle_frames = 0
        self._update_click_through()
        self.update()

    def _update_click_through(self) -> None:
        """Receive clicks only while the cursor is over the rug (or holding it)."""
        cursor = QPointF(self.mapFromGlobal(QCursor.pos()))
        x, y = self._to_world(cursor)
        over_rug = self._cloth.nearest_particle(x, y, RUG_HIT_RADIUS) is not None
        click_through = not (over_rug or self._is_grabbing)
        if click_through != self._click_through:
            # Record the state even if the call fails, so a failing call is
            # logged once instead of retried every frame.
            self._click_through = click_through
            try:
                desktop.set_click_through(int(self.winId()), click_through)
            except OSError:
                logger.exception("Could not change click-through")

    def _refresh_obstacles(self) -> None:
        """Turn the desktop icons into hills under the rug.

        Wakes the simulation only when the icons actually changed, so a
        settled rug can keep sleeping. If Explorer cannot be read, the last
        known icons are kept and the error is logged once.
        """
        try:
            icon_rects = desktop.desktop_icon_rects()
        except OSError as exc:
            if str(exc) != self._last_icon_error:
                logger.warning("Could not read desktop icons: %s", exc)
                self._last_icon_error = str(exc)
            return
        self._last_icon_error = None
        ratio = self.devicePixelRatio()
        rects: list[tuple[float, float, float, float]] = []
        for left, top, right, bottom in icon_rects:
            # Physical screen pixels -> logical -> this window -> world metres.
            top_left = self.mapFromGlobal(QPointF(left / ratio, top / ratio))
            bottom_right = self.mapFromGlobal(QPointF(right / ratio, bottom / ratio))
            x0, y_top = self._to_world(top_left)
            x1, y_bottom = self._to_world(bottom_right)
            rects.append((x0, y_bottom, x1, y_top))
        obstacles = np.array(rects, dtype=np.float64).reshape(-1, 4)
        if np.array_equal(obstacles, self._obstacles):
            return
        self._obstacles = obstacles
        self._cloth.set_obstacles(obstacles)
        # Icons moved under the rug: let it settle again.
        self._idle_frames = 0

    def _fit_to_screen(self, available: QRect) -> None:
        """Follow a change of the screen's usable area and move the walls."""
        self.setGeometry(available)
        self._bounds = (
            0.0,
            0.0,
            self.width() / PX_PER_METRE,
            self.height() / PX_PER_METRE,
        )
        self._cloth.set_bounds(self._bounds)
        self._idle_frames = 0

    def _held_point(self) -> tuple[float, float, float]:
        x, y, z = (float(v) for v in self._grab_held)
        return x, y, z

    def _clamp_to_bounds(self, x: float, y: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self._bounds
        return min(max(x, x0), x1), min(max(y, y0), y1)

    def _to_world(self, point: QPointF) -> tuple[float, float]:
        return screen_to_world(point.x(), point.y(), self.height())

    def _release_renderer(self) -> None:
        if self._renderer is None:
            return
        self.makeCurrent()
        try:
            self._renderer.release()
        finally:
            self.doneCurrent()
