import tkinter as tk

import theme
from components import Tooltip

BAR_HEIGHT = 8


class StorageBar(tk.Canvas):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, height=BAR_HEIGHT, highlightthickness=0, takefocus=False)
        theme.bind(self, bg="surface")
        theme.observe(self)
        self._ratio = 0.0
        self._low_space = False
        self._description = ""
        Tooltip(self, lambda: self._description)
        self.bind("<Configure>", lambda _event: self._draw())

    def apply_theme(self, _theme: theme.Theme) -> None:
        self._draw()

    def show(self, ratio: float, description: str, low_space: bool = False) -> None:
        self._ratio = ratio
        self._low_space = low_space
        self._description = description
        self._draw()

    def _draw(self) -> None:
        width = self.winfo_width()
        palette = theme.current()
        self.delete("all")
        self.create_rectangle(0, 0, width, BAR_HEIGHT, fill=palette.meter_track, width=0)
        color = palette.bar_alert if self._low_space else palette.bar_fill
        self.create_rectangle(0, 0, width * self._ratio, BAR_HEIGHT, fill=color, width=0)
