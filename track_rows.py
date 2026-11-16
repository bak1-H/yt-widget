import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Sequence

import texts
import theme
from components import IconButton, Tooltip, add_focus_ring
from media import shorten
from scroll_area import ScrollArea
from theme import Icon

ROW_HEIGHT = 32
VISIBLE_ROWS = 7
TITLE_LIMIT = 56
NUMBER_WIDTH_CHARS = 2


@dataclass(frozen=True)
class RowItem:
    title: str
    uri: str
    suggested: bool = False


@dataclass(frozen=True)
class RowHandlers:
    play: Callable[[int, str], None]
    open_menu: Callable[[int, str, int, int], None]
    remove: Callable[[int, str], None] | None = None


def locate(uris: Sequence[str], row: int, uri: str) -> int | None:
    if 0 <= row < len(uris) and uris[row] == uri:
        return row
    matches = [index for index, candidate in enumerate(uris) if candidate == uri]
    return min(matches, key=lambda index: abs(index - row)) if matches else None


class SongRow(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        index: int,
        item: RowItem,
        handlers: RowHandlers,
        focus_target: Callable[[int], None],
        on_focus: Callable[[int], None],
        last_index: Callable[[], int],
        is_downloaded: Callable[[str], bool],
        numbered: bool = False,
    ) -> None:
        super().__init__(parent, height=ROW_HEIGHT - theme.current().row_gap)
        theme.bind(self, bg="surface")
        add_focus_ring(self, "surface")
        self.configure(takefocus=False)
        self.pack_propagate(False)
        self.index = index
        self.item = item
        self._handlers = handlers
        self._is_downloaded = is_downloaded
        self._numbered = numbered
        self._hovered = False
        self._label = tk.Label(self, text=shorten(item.title, TITLE_LIMIT), anchor="w", font=theme.TEXT_FONT, cursor="hand2")
        theme.bind(self._label, bg="surface", fg="foreground")
        self._number = tk.Label(self, text=f"{index + 1:02d}", width=NUMBER_WIDTH_CHARS, anchor="w", font=theme.SMALL_FONT)
        theme.bind(self._number, bg="surface", fg="muted")
        Tooltip(self._label, lambda: self.item.title if len(self.item.title) > TITLE_LIMIT else "")
        self._button = IconButton(self, Icon.MORE, self._open_from_button, variant="row", tooltip=texts.SONG_OPTIONS)
        self._button.configure(takefocus=False)
        self._marker = tk.Label(self, font=theme.ICON_FONT_SMALL)
        theme.bind(self._marker, bg="surface", fg="downloaded")
        Tooltip(self._marker, lambda: texts.DOWNLOADED_TOOLTIP if self._marker.cget("text") else "")
        self._badge = tk.Label(self, text=texts.SUGGESTED, font=theme.SMALL_FONT)
        theme.bind(self._badge, bg="surface", fg="muted")
        Tooltip(self._badge, texts.SUGGESTED_TOOLTIP)
        self._button.pack(side="right", padx=(0, 2))
        self._marker.pack(side="right")
        self._label.pack(side="left", fill="x", expand=True, padx=(8, 0))
        for widget in (self, self._label, self._number, self._marker, self._badge):
            widget.bind("<Button-1>", lambda _event: self._activate(), add="+")
            widget.bind("<Button-3>", lambda event: self._handlers.open_menu(self.index, self.item.uri, event.x_root, event.y_root), add="+")
            widget.bind("<Enter>", lambda _event: self._paint(hovered=True), add="+")
            widget.bind("<Leave>", lambda _event: self._paint(hovered=False), add="+")
        self.bind("<FocusIn>", lambda _event: on_focus(self.index))
        self.bind("<Return>", lambda _event: self._handlers.play(self.index, self.item.uri))
        self.bind("<Up>", lambda _event: focus_target(self.index - 1))
        self.bind("<Down>", lambda _event: focus_target(self.index + 1))
        self.bind("<Home>", lambda _event: focus_target(0))
        self.bind("<End>", lambda _event: focus_target(last_index()))
        for sequence in ("<Shift-F10>", "<App>"):
            self.bind(sequence, lambda _event: self._open_from_button())
        if handlers.remove:
            self.bind("<Delete>", lambda _event: self._handlers.remove(self.index, self.item.uri))
        self.refresh_marker()
        self._sync_badge()
        self._sync_number()
        theme.observe(self)

    @property
    def widgets(self) -> tuple[tk.Misc, ...]:
        return (self, self._label, self._number, self._marker, self._badge, self._button)

    def apply_theme(self, palette: theme.Theme) -> None:
        self.configure(height=ROW_HEIGHT - palette.row_gap)
        self.pack_configure(pady=(0, palette.row_gap))
        self._sync_number()
        self._paint(hovered=False)

    def update_item(self, item: RowItem) -> None:
        if item == self.item:
            return
        self.item = item
        self._label.configure(text=shorten(item.title, TITLE_LIMIT))
        self.refresh_marker()
        self._sync_badge()

    def refresh_marker(self) -> None:
        downloaded = self._is_downloaded(self.item.uri)
        if bool(self._marker.cget("text")) != downloaded:
            self._marker.configure(text=Icon.DOWNLOADED if downloaded else "", padx=4 if downloaded else 0)
            self._paint(self._hovered)

    def _sync_badge(self) -> None:
        if self.item.suggested and not self._badge.winfo_manager():
            self._badge.pack(side="right", padx=(0, 4), before=self._label)
        elif not self.item.suggested and self._badge.winfo_manager():
            self._badge.pack_forget()

    def _activate(self) -> None:
        self.focus_set()
        self._handlers.play(self.index, self.item.uri)

    def _open_from_button(self) -> None:
        self._handlers.open_menu(self.index, self.item.uri, self.winfo_rootx() + self.winfo_width() - 40, self.winfo_rooty() + self.winfo_height())

    def _sync_number(self) -> None:
        shown = self._numbered and theme.current().numbered_rows
        if shown and not self._number.winfo_manager():
            self._number.pack(side="left", padx=(8, 0), before=self._label)
        elif not shown and self._number.winfo_manager():
            self._number.pack_forget()

    def _paint(self, hovered: bool) -> None:
        self._hovered = hovered
        role = "surface_hover" if hovered else "surface"
        for widget in (self, self._label, self._number, self._badge):
            theme.bind(widget, bg=role)
        downloaded = bool(self._marker.cget("text"))
        theme.bind(self._marker, bg="downloaded_background" if downloaded and theme.current().downloaded_background else role)


class TrackRows(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        empty_text: str,
        handlers: RowHandlers,
        is_downloaded: Callable[[str], bool],
        rows: int = VISIBLE_ROWS,
        numbered: bool = False,
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._numbered = numbered
        self._empty_text = empty_text
        self._handlers = handlers
        self._is_downloaded = is_downloaded
        self._items: list[RowItem] | None = None
        self._wanted: list[RowItem] | None = None
        self._keep_view = True
        self._rows: list[SongRow] = []
        self._empty_label: tk.Label | None = None
        self._tab_stop = 0
        self._area = ScrollArea(self, height=rows * ROW_HEIGHT, canvas_role="row_area_color", body_role="row_gap_color")
        self._area.pack(fill="x")
        self.bind("<Map>", lambda _event: self._on_map())

    def show(self, items: list[RowItem], *, keep_view: bool = True) -> None:
        self._wanted = items
        self._keep_view = keep_view
        if self.winfo_ismapped():
            self._apply()

    def refresh_markers(self) -> None:
        if self.winfo_ismapped():
            for row in self._rows:
                row.refresh_marker()

    def _on_map(self) -> None:
        self._apply()
        self.refresh_markers()

    def reveal(self, index: int) -> None:
        self._apply()
        if 0 <= index < len(self._rows):
            self._area.see(self._rows[index])

    def focus_row(self, index: int) -> None:
        if self._rows:
            row = self._rows[min(max(index, 0), len(self._rows) - 1)]
            row.focus_set()
            self._area.see(row)

    def _apply(self) -> None:
        items = self._wanted
        if items is None or items == self._items:
            return
        focused = self._focused()
        offset = self._area.scroll_offset() if self._keep_view else 0
        resized = self._items is None or len(items) != len(self._items)
        self._items = items
        self._sync_rows(items)
        self._sync_empty_label(items)
        if resized or not self._keep_view:
            self._area.restore_offset(offset)
        self._tab_stop = min(self._tab_stop, max(len(self._rows) - 1, 0))
        self._sync_tab_stop()
        if focused:
            self._refocus(*focused)

    def _sync_rows(self, items: list[RowItem]) -> None:
        for index, item in enumerate(items):
            if index < len(self._rows):
                self._rows[index].update_item(item)
                continue
            row = SongRow(self._area.body, index, item, self._handlers, self.focus_row, self._set_tab_stop, lambda: len(self._rows) - 1, self._is_downloaded, self._numbered)
            row.pack(fill="x", pady=(0, theme.current().row_gap))
            self._area.forward_wheel(*row.widgets)
            self._rows.append(row)
        for surplus in self._rows[len(items):]:
            surplus.destroy()
        del self._rows[len(items):]

    def _sync_empty_label(self, items: list[RowItem]) -> None:
        if items and self._empty_label:
            self._empty_label.destroy()
            self._empty_label = None
        elif not items and not self._empty_label:
            self._empty_label = tk.Label(self._area.body, text=self._empty_text, anchor="w", font=theme.TEXT_FONT, padx=8, pady=6)
            theme.bind(self._empty_label, bg="surface", fg="muted")
            self._empty_label.pack(fill="x")
            self._area.forward_wheel(self._empty_label)

    def _refocus(self, index: int, uri: str) -> None:
        target = locate([row.item.uri for row in self._rows], index, uri)
        self.focus_row(index if target is None else target)

    def _set_tab_stop(self, index: int) -> None:
        self._tab_stop = index
        self._sync_tab_stop()

    def _sync_tab_stop(self) -> None:
        for index, row in enumerate(self._rows):
            row.configure(takefocus=index == self._tab_stop)

    def _focused(self) -> tuple[int, str] | None:
        try:
            focused = self.focus_get()
        except KeyError:
            return None
        return next(((row.index, row.item.uri) for row in self._rows if focused is row), None)
