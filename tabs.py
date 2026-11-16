import tkinter as tk
from typing import Callable

import theme
from components import add_focus_ring
from shape_button import Shape, ShapeButton, ShapeColors
from theme import TabStyle

STRIP_ROLES = {TabStyle.FILLED: "background", TabStyle.UNDERLINE: "background", TabStyle.SEGMENTED: "tab_track", TabStyle.PILL: "tab_track"}
STRIP_PADDING = {TabStyle.FILLED: 0, TabStyle.UNDERLINE: 0, TabStyle.SEGMENTED: 2, TabStyle.PILL: 2}
TAB_GAPS = {TabStyle.FILLED: 4, TabStyle.UNDERLINE: 4, TabStyle.SEGMENTED: 0, TabStyle.PILL: 2}
BUTTON_COLORS = {
    TabStyle.FILLED: (("surface", "accent"), ("background", "muted")),
    TabStyle.SEGMENTED: (("surface", "accent"), ("tab_track", "muted")),
    TabStyle.UNDERLINE: (("background", "foreground"), ("background", "muted")),
}
PILL_SELECTED = ShapeColors(fill="surface", hover="surface_hover", foreground="accent")
PILL_IDLE = ShapeColors(fill=None, hover="surface_hover", foreground="muted")
PILL_HEIGHT = 24
PILL_MARGIN = 2
UNDERLINE_HEIGHT = 2


class Tabs(tk.Frame):
    def __init__(self, parent: tk.Misc, on_change: Callable[[str], None]) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._on_change = on_change
        self._bar = tk.Frame(self)
        theme.bind(self._bar, bg="background")
        self._bar.pack(fill="x", pady=(0, 8))
        self._strip = tk.Frame(self._bar)
        self._strip.pack(side="left")
        self._tabs: dict[str, tk.Button | ShapeButton] = {}
        self._underlines: dict[str, tk.Frame] = {}
        self._pages: dict[str, tk.Widget] = {}
        self._current: str | None = None
        self._style_strip()
        theme.observe(self)

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def names(self) -> list[str]:
        return list(self._pages)

    def add(self, name: str, build_page: Callable[[tk.Misc], tk.Widget]) -> None:
        self._pages[name] = build_page(self)
        self._build_tab(name)
        self._style(name, selected=False)

    def select(self, name: str) -> None:
        if self._current:
            self._pages[self._current].pack_forget()
            self._style(self._current, selected=False)
        self._current = name
        self._pages[name].pack(fill="x")
        self._style(name, selected=True)
        self._on_change(name)

    def apply_theme(self, _theme: theme.Theme) -> None:
        for holder in self._strip.winfo_children():
            holder.destroy()
        self._tabs.clear()
        self._underlines.clear()
        self._style_strip()
        for name in self._pages:
            self._build_tab(name)
            self._style(name, selected=name == self._current)

    def _style_strip(self) -> None:
        style = theme.current().tab_style
        padding = STRIP_PADDING[style]
        self._strip.configure(padx=padding, pady=padding)
        theme.bind(self._strip, bg=STRIP_ROLES[style])

    def _build_tab(self, name: str) -> None:
        style = theme.current().tab_style
        gap = TAB_GAPS[style]
        if style is TabStyle.PILL:
            tab = ShapeButton(
                self._strip,
                lambda: self.select(name),
                tooltip="",
                shape=Shape.PILL,
                colors=PILL_IDLE,
                size=PILL_HEIGHT,
                label=name,
                label_font=theme.HEADING_FONT,
                margin=PILL_MARGIN,
            )
            tab.pack(side="left", padx=(0, gap))
        else:
            tab = self._build_button(name, style, gap)
        self._tabs[name] = tab

    def _build_button(self, name: str, style: TabStyle, gap: int) -> tk.Button:
        strip_role = STRIP_ROLES[style]
        holder = tk.Frame(self._strip)
        theme.bind(holder, bg=strip_role)
        button = tk.Button(
            holder,
            text=name,
            command=lambda: self.select(name),
            relief="flat",
            bd=0,
            font=theme.HEADING_FONT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        theme.bind(button, activebackground="surface_hover", activeforeground="foreground")
        add_focus_ring(button, strip_role)
        button.bind("<Return>", lambda _event: button.invoke())
        button.pack()
        if style is TabStyle.UNDERLINE:
            underline = tk.Frame(holder, height=UNDERLINE_HEIGHT)
            underline.pack(fill="x")
            self._underlines[name] = underline
        holder.pack(side="left", padx=(0, gap))
        return button

    def _style(self, name: str, selected: bool) -> None:
        style = theme.current().tab_style
        tab = self._tabs[name]
        if isinstance(tab, ShapeButton):
            tab.set_colors(PILL_SELECTED if selected else PILL_IDLE)
            return
        selected_roles, idle_roles = BUTTON_COLORS[style]
        background, foreground = selected_roles if selected else idle_roles
        theme.bind(tab, bg=background, fg=foreground)
        if name in self._underlines:
            theme.bind(self._underlines[name], bg="accent" if selected else "background")
