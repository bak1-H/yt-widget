import tkinter as tk
from tkinter import ttk

import theme
from components import thin_scrollbar_style

WHEEL_UNIT_PIXELS = 30


class ScrollArea(tk.Frame):
    def __init__(self, parent: tk.Misc, height: int, canvas_role: str = "surface", body_role: str = "surface") -> None:
        super().__init__(parent)
        theme.bind(self, bg="surface")
        self._canvas = tk.Canvas(self, width=1, height=height, highlightthickness=0, yscrollincrement=WHEEL_UNIT_PIXELS)
        theme.bind(self._canvas, bg=canvas_role)
        scrollbar = ttk.Scrollbar(self, orient="vertical", style=thin_scrollbar_style(), command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self._canvas)
        theme.bind(self.body, bg=body_role)
        window = self._canvas.create_window(0, 0, window=self.body, anchor="nw")
        self._canvas.bind("<Configure>", lambda event: self._canvas.itemconfigure(window, width=event.width))
        self.body.bind("<Configure>", lambda _event: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self.forward_wheel(self._canvas, self.body)
        theme.observe(self)

    def apply_theme(self, _theme: theme.Theme) -> None:
        thin_scrollbar_style()

    def forward_wheel(self, *widgets: tk.Misc) -> None:
        for widget in widgets:
            widget.bind("<MouseWheel>", self._wheel, add="+")

    def scroll_offset(self) -> int:
        return int(self._canvas.canvasy(0))

    def restore_offset(self, offset: int) -> None:
        self.update_idletasks()
        self._canvas.yview_moveto(offset / max(self.body.winfo_reqheight(), 1))

    def see(self, widget: tk.Misc) -> None:
        self.update_idletasks()
        total = max(self.body.winfo_reqheight(), 1)
        top, bottom = widget.winfo_y(), widget.winfo_y() + widget.winfo_height()
        view_top, view_height = self._canvas.canvasy(0), self._canvas.winfo_height()
        if top < view_top:
            self._canvas.yview_moveto(top / total)
        elif bottom > view_top + view_height:
            self._canvas.yview_moveto((bottom - view_height) / total)

    def _wheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
