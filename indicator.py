import math
import tkinter as tk

import theme
from playback import PlaybackState
from theme import IndicatorStyle

SIZE = 34
FRAME_MS = 50
BAR_COUNT = 4
BAR_WIDTH = 4
BAR_GAP = 3
STILL_BAR_RATIO = 0.3
SPINNER_INSET = 5
SPINNER_WIDTH = 3
DISC_INSET = 3
DISC_GROOVE_RADII = (0.82, 0.66, 0.5)
DISC_LABEL_RADIUS = 0.3
DISC_HOLE_RADIUS = 0.06
DISC_SHEEN_RADIUS = 0.74
DISC_SHEEN_EXTENT = 36
DISC_SHEEN_REST_START = 40
DISC_SPIN_DEGREES = 14
FULL_TURN = 360
ANIMATED_STATES = {PlaybackState.LOADING, PlaybackState.PLAYING}
STATE_COLOR_ROLES = {PlaybackState.PLAYING: "accent", PlaybackState.FAILED: "danger"}


class PlaybackIndicator(tk.Canvas):
    def __init__(self, parent: tk.Misc, size: int = SIZE) -> None:
        super().__init__(parent, width=size, height=size, highlightthickness=0)
        theme.bind(self, bg="background")
        self._size = size
        self._state = PlaybackState.IDLE
        self._frame = 0
        self._job: str | None = None
        self._visible = True
        self._draw()
        theme.observe(self)

    def apply_theme(self, _theme: theme.Theme) -> None:
        self._redraw()

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if visible:
            self._draw()

    def set_size(self, size: int) -> None:
        if size == self._size:
            return
        self._size = size
        self.configure(width=size, height=size)
        self._redraw()

    def set_state(self, state: PlaybackState) -> None:
        if state is self._state:
            return
        self._state = state
        self._redraw()

    def _redraw(self) -> None:
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        if self._state is PlaybackState.LOADING:
            self._draw_spinner()
        elif theme.current().indicator_style is IndicatorStyle.DISC:
            self._draw_disc()
        else:
            self._draw_bars()
        if self._visible and self._state in ANIMATED_STATES:
            self._frame += 1
            self._job = self.after(FRAME_MS, self._draw)

    def _draw_spinner(self) -> None:
        palette = theme.current()
        inset = SPINNER_INSET * self._scale
        width = max(2, round(SPINNER_WIDTH * self._scale))
        box = (inset, inset, self._size - inset, self._size - inset)
        self.create_oval(*box, outline=palette.surface, width=width)
        start = (-self._frame * 18) % 360
        extent = 90 + 60 * math.sin(self._frame / 5)
        self.create_arc(*box, start=start, extent=extent, style="arc", outline=palette.accent, width=width)

    def _draw_bars(self) -> None:
        color = theme.color(STATE_COLOR_ROLES.get(self._state, "muted"))
        bar_width = BAR_WIDTH * self._scale
        step = bar_width + BAR_GAP * self._scale
        left = (self._size - (BAR_COUNT * bar_width + (BAR_COUNT - 1) * BAR_GAP * self._scale)) / 2
        bottom = self._size - 7 * self._scale
        max_height = self._size - 14 * self._scale
        for index in range(BAR_COUNT):
            ratio = self._bar_ratio(index)
            x = left + index * step
            self.create_rectangle(x, bottom - max_height * ratio, x + bar_width, bottom, fill=color, width=0)

    def _draw_disc(self) -> None:
        palette = theme.current()
        center = self._size / 2
        radius = center - DISC_INSET * self._scale
        self._circle(center, radius, fill=palette.surface_hover)
        for ratio in DISC_GROOVE_RADII:
            self._circle(center, radius * ratio, outline=palette.surface)
        sheen_box = self._box(center, radius * DISC_SHEEN_RADIUS)
        sheen_start = (-self._frame * DISC_SPIN_DEGREES) % FULL_TURN if self._state is PlaybackState.PLAYING else DISC_SHEEN_REST_START
        self.create_arc(*sheen_box, start=sheen_start, extent=DISC_SHEEN_EXTENT, style="arc", outline=palette.muted, width=max(1, round(self._scale)))
        self._circle(center, radius * DISC_LABEL_RADIUS, fill=theme.color(STATE_COLOR_ROLES.get(self._state, "muted")))
        self._circle(center, radius * DISC_HOLE_RADIUS, fill=palette.background)

    def _box(self, center: float, radius: float) -> tuple[float, float, float, float]:
        return center - radius, center - radius, center + radius, center + radius

    def _circle(self, center: float, radius: float, fill: str = "", outline: str = "") -> None:
        self.create_oval(*self._box(center, radius), fill=fill, outline=outline, width=1 if outline else 0)

    @property
    def _scale(self) -> float:
        return self._size / SIZE

    def _bar_ratio(self, index: int) -> float:
        if self._state is not PlaybackState.PLAYING:
            return STILL_BAR_RATIO
        return 0.25 + 0.75 * abs(math.sin(self._frame * 0.17 + index * 1.3))
