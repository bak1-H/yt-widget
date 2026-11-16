import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from tkinter import font as tkfont
from typing import Callable

import theme
from components import FOCUS_RING_THICKNESS, Tooltip, TooltipText
from shape_render import RoundPhotos, RoundSpec

CONTENT_GAP = 6
PILL_PADDING = 16
PRESS_SHRINK = 2
FOCUS_GAP = 2
OUTLINE_WIDTH = 2


class Shape(Enum):
    CIRCLE = "circle"
    PILL = "pill"
    RECT = "rect"


@dataclass(frozen=True)
class ShapeColors:
    fill: str | None
    hover: str
    foreground: str
    outline: str | None = None


class ShapeButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        action: Callable[[], None],
        *,
        tooltip: TooltipText,
        shape: Shape,
        colors: ShapeColors,
        size: int,
        icon: str = "",
        label: str = "",
        icon_font: tuple = theme.ICON_FONT_LARGE,
        label_font: tuple = theme.TITLE_FONT,
        margin: int = FOCUS_RING_THICKNESS + FOCUS_GAP,
    ) -> None:
        super().__init__(parent, highlightthickness=0, cursor="hand2", takefocus=True)
        theme.bind(self, bg=theme.role_of(parent))
        self._action = action
        self._shape = shape
        self._colors = colors
        self._size = size
        self._icon_font = tkfont.Font(font=icon_font)
        self._label_font = tkfont.Font(font=label_font)
        self._icon_font_spec = icon_font
        self._label_font_spec = label_font
        self._margin = margin
        self._icon = icon
        self._label = label
        self._photos = RoundPhotos(self)
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._fit()
        self._bind_events()
        Tooltip(self, tooltip)
        theme.observe(self)

    def set_content(self, icon: str, label: str = "") -> None:
        if (icon, label) == (self._icon, self._label):
            return
        self._icon, self._label = icon, label
        self._fit()

    def set_colors(self, colors: ShapeColors) -> None:
        if colors != self._colors:
            self._colors = colors
            self._draw()

    def apply_theme(self, _theme: theme.Theme) -> None:
        self._draw()

    def invoke(self) -> None:
        self._action()

    def _bind_events(self) -> None:
        self.bind("<Enter>", lambda _event: self._set_state(hovered=True))
        self.bind("<Leave>", lambda _event: self._set_state(hovered=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda _event: self._set_state(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda _event: self._set_state(focused=True))
        self.bind("<FocusOut>", lambda _event: self._set_state(focused=False))
        for sequence in ("<Return>", "<space>"):
            self.bind(sequence, lambda _event: self.invoke())

    def _release(self, _event: tk.Event) -> None:
        was_pressed = self._pressed
        self._set_state(pressed=False)
        if was_pressed and self._hovered:
            self.invoke()

    def _set_state(self, *, hovered: bool | None = None, pressed: bool | None = None, focused: bool | None = None) -> None:
        self._hovered = self._hovered if hovered is None else hovered
        self._pressed = self._pressed if pressed is None else pressed
        self._focused = self._focused if focused is None else focused
        self._draw()

    def _content_width(self) -> int:
        icon_width = self._icon_font.measure(self._icon) if self._icon else 0
        label_width = self._label_font.measure(self._label) if self._label else 0
        gap = CONTENT_GAP if self._icon and self._label else 0
        return icon_width + gap + label_width

    def _body_width(self) -> int:
        if self._shape is Shape.CIRCLE:
            return self._size
        return self._content_width() + 2 * PILL_PADDING

    def _fit(self) -> None:
        self.configure(width=self._body_width() + 2 * self._margin, height=self._size + 2 * self._margin)
        self._draw()

    def _draw(self) -> None:
        palette = theme.current()
        self.delete("all")
        width, height = self._body_width() + 2 * self._margin, self._size + 2 * self._margin
        inset = self._margin + (PRESS_SHRINK if self._pressed else 0)
        box = (inset, inset, width - inset, height - inset)
        active = self._hovered or self._pressed
        fill_role = self._colors.hover if active else self._colors.fill
        fill = getattr(palette, fill_role) if fill_role else ""
        outline = getattr(palette, self._colors.outline) if self._colors.outline else ""
        if self._shape is Shape.RECT:
            self._draw_rectangle(box, fill, outline)
        else:
            ring = palette.accent if self._focused else ""
            spec = RoundSpec(width, height, box, fill, outline, OUTLINE_WIDTH if outline else 0, ring, FOCUS_RING_THICKNESS if ring else 0)
            self.create_image(0, 0, anchor="nw", image=self._photos.get(spec))
        self._draw_content(width, height, getattr(palette, self._colors.foreground))
        if self._focused and self._shape is Shape.RECT:
            half = FOCUS_RING_THICKNESS / 2
            self.create_rectangle(half, half, width - half, height - half, outline=palette.accent, width=FOCUS_RING_THICKNESS)

    def _draw_content(self, width: int, height: int, color: str) -> None:
        left = (width - self._content_width()) / 2
        if self._icon:
            self.create_text(left, height / 2, text=self._icon, font=self._icon_font_spec, fill=color, anchor="w")
            left += self._icon_font.measure(self._icon) + CONTENT_GAP
        if self._label:
            self.create_text(left, height / 2, text=self._label, font=self._label_font_spec, fill=color, anchor="w")

    def _draw_rectangle(self, box: tuple[float, float, float, float], fill: str, outline: str) -> None:
        left, top, right, bottom = box
        self.create_rectangle(left, top, right, bottom, fill=fill, outline=outline, width=OUTLINE_WIDTH if outline else 0)
