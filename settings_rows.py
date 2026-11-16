import tkinter as tk
from typing import Callable, Generic, TypeVar

import theme
from components import Tooltip, add_focus_ring

ValueT = TypeVar("ValueT")


class ChoiceMenu(tk.Menubutton, Generic[ValueT]):
    def __init__(self, parent: tk.Misc, labels: dict[ValueT, str], value: ValueT, on_select: Callable[[ValueT], None]) -> None:
        super().__init__(
            parent,
            relief="flat",
            bd=0,
            font=theme.TEXT_FONT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        theme.bind(self, bg="surface_hover", fg="foreground", activebackground="surface_hover", activeforeground="foreground", disabledforeground="muted")
        add_focus_ring(self, "surface")
        self._labels = labels
        menu = tk.Menu(self, tearoff=False, font=theme.TEXT_FONT)
        theme.bind_menu(menu)
        self.configure(menu=menu)
        for option, label in labels.items():
            menu.add_command(label=label, command=lambda chosen=option: self._choose(chosen, on_select))
        for key in ("<Return>", "<space>", "<Down>"):
            self.bind(key, lambda _event: menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height()))
        self.show(value)

    def show(self, value: ValueT) -> None:
        self.configure(text=f"{self._labels[value]}  ▾")

    def set_enabled(self, enabled: bool) -> None:
        self.configure(state="normal" if enabled else "disabled", cursor="hand2" if enabled else "arrow")

    def _choose(self, value: ValueT, on_select: Callable[[ValueT], None]) -> None:
        self.show(value)
        on_select(value)


class RowBuilder:
    def __init__(self, body: tk.Misc) -> None:
        self._body = body

    def row(self, label: str | None = None) -> tk.Frame:
        row = tk.Frame(self._body, padx=8, pady=3)
        theme.bind(row, bg="surface")
        row.pack(fill="x")
        if label:
            caption = tk.Label(row, text=label, font=theme.TEXT_FONT)
            theme.bind(caption, bg="surface", fg="foreground")
            caption.pack(side="left")
        return row

    def toggle(self, label: str, value: bool, on_toggle: Callable[[bool], None], tooltip: str | None = None, row: tk.Frame | None = None) -> tk.BooleanVar:
        variable = tk.BooleanVar(value=value)
        check = tk.Checkbutton(
            row or self.row(),
            text=label,
            variable=variable,
            command=lambda: on_toggle(variable.get()),
            font=theme.TEXT_FONT,
            anchor="w",
            bd=0,
            cursor="hand2",
        )
        theme.bind(check, bg="surface", fg="foreground", activebackground="surface", activeforeground="foreground", selectcolor="surface_hover")
        add_focus_ring(check, "surface")
        if tooltip:
            Tooltip(check, tooltip)
        check.pack(side="left")
        return variable
