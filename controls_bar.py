import tkinter as tk
from dataclasses import dataclass
from typing import Callable

import texts
import theme
from components import IconButton, SliderBar, Tooltip, enable_dragging
from repeat import RepeatMode
from shape_button import Shape, ShapeButton, ShapeColors
from theme import Icon, PlayShape

VOLUME_SLIDER_LENGTH = 90
SKIP_BUTTON_SIZE = 34
REPEAT_ICONS = {RepeatMode.OFF: Icon.REPEAT_OFF, RepeatMode.QUEUE: Icon.REPEAT_ALL, RepeatMode.SONG: Icon.REPEAT_ONE}
PLAY_COLORS = ShapeColors(fill="accent", hover="accent_hover", foreground="on_accent")
SKIP_COLORS = ShapeColors(fill=None, hover="surface_hover", foreground="muted", outline="muted")


@dataclass(frozen=True)
class ControlActions:
    previous: Callable[[], None]
    toggle: Callable[[], None]
    next: Callable[[], None]
    cycle_repeat: Callable[[], None]
    toggle_panel: Callable[[], None]
    set_volume: Callable[[int], None]


class ControlsBar(tk.Frame):
    def __init__(self, parent: tk.Tk, initial_volume: int, initial_repeat: RepeatMode, actions: ControlActions) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._actions = actions
        self._repeat = initial_repeat
        self._playing = False
        self._transport = tk.Frame(self)
        theme.bind(self._transport, bg="background")
        self._transport.pack(side="left")
        self._build_transport()
        self._repeat_button = IconButton(self, Icon.REPEAT_ALL, actions.cycle_repeat, variant="ghost", tooltip=lambda: texts.REPEAT_TOOLTIPS[self._repeat])
        self._repeat_button.pack(side="left")
        self.set_repeat(initial_repeat)
        volume_icon = tk.Label(self, text=Icon.VOLUME, font=theme.ICON_FONT)
        theme.bind(volume_icon, bg="background", fg="muted")
        volume = SliderBar(self, on_change=lambda ratio: actions.set_volume(round(ratio * 100)), width=VOLUME_SLIDER_LENGTH, show_knob=True, wheel=True)
        volume.set_ratio(initial_volume / 100)
        Tooltip(volume, texts.VOLUME_TOOLTIP)
        panel_button = IconButton(self, Icon.LIST, actions.toggle_panel, variant="ghost", tooltip=texts.PANEL_TOOLTIP)
        panel_button.pack(side="right", padx=(8, 0))
        volume.pack(side="right")
        volume_icon.pack(side="right", padx=(0, 6))
        enable_dragging(parent, self)
        theme.observe(self)

    def apply_theme(self, _theme: theme.Theme) -> None:
        for child in self._transport.winfo_children():
            child.destroy()
        self._build_transport()

    def set_repeat(self, mode: RepeatMode) -> None:
        self._repeat = mode
        self._repeat_button.set_icon(REPEAT_ICONS[mode])
        self._repeat_button.set_foreground("muted" if mode is RepeatMode.OFF else "accent")

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self._show_playing()

    def _build_transport(self) -> None:
        self._skip_button(Icon.PREVIOUS, self._actions.previous, texts.PREVIOUS_TOOLTIP).pack(side="left")
        self._toggle = self._play_button()
        self._toggle.pack(side="left", padx=6)
        self._skip_button(Icon.NEXT, self._actions.next, texts.NEXT_TOOLTIP).pack(side="left")
        self._show_playing()

    def _skip_button(self, icon: str, action: Callable[[], None], tooltip: str) -> tk.Widget:
        if not theme.current().outlined_skips:
            return IconButton(self._transport, icon, action, variant="ghost", tooltip=tooltip)
        return ShapeButton(
            self._transport, action, tooltip=tooltip, shape=Shape.CIRCLE, colors=SKIP_COLORS, size=SKIP_BUTTON_SIZE, icon=icon, icon_font=theme.ICON_FONT
        )

    def _play_button(self) -> tk.Widget:
        palette = theme.current()
        if palette.play_shape is PlayShape.SQUARE:
            return IconButton(self._transport, Icon.PLAY, self._actions.toggle, variant="primary", large=True, tooltip=texts.PLAY_PAUSE_TOOLTIP)
        shape = Shape.CIRCLE if palette.play_shape is PlayShape.CIRCLE else Shape.PILL
        icon_font = theme.ICON_FONT_LARGE if shape is Shape.CIRCLE else theme.ICON_FONT
        return ShapeButton(
            self._transport, self._actions.toggle, tooltip=texts.PLAY_PAUSE_TOOLTIP, shape=shape, colors=PLAY_COLORS, size=palette.play_size, icon=Icon.PLAY, icon_font=icon_font
        )

    def _show_playing(self) -> None:
        icon = Icon.PAUSE if self._playing else Icon.PLAY
        if isinstance(self._toggle, ShapeButton):
            label = texts.PAUSE_LABEL if self._playing else texts.PLAY_LABEL
            self._toggle.set_content(icon, label if theme.current().play_shape is PlayShape.PILL else "")
        else:
            self._toggle.set_icon(icon)
