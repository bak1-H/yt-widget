import tkinter as tk
from typing import Callable

import texts
import theme
from components import IconButton, SearchEntry, StatusLine
from media import to_media_uri
from theme import Icon


class SearchBar(tk.Frame):
    def __init__(self, parent: tk.Misc, on_play: Callable[[str], bool], on_enqueue: Callable[[str], bool]) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._on_play = on_play
        self._on_enqueue = on_enqueue
        row = tk.Frame(self)
        theme.bind(row, bg="background")
        row.pack(fill="x", pady=(10, 0))
        self._search = SearchEntry(row, placeholder=texts.SEARCH_PLACEHOLDER)
        self._search.pack(side="left", fill="x", expand=True)
        self._search.bind_key("<Return>", self._play)
        self._search.bind_key("<Shift-Return>", self._enqueue)
        IconButton(row, Icon.PLAY, self._play, tooltip=texts.PLAY_NOW_TOOLTIP).pack(side="left", padx=(6, 0), fill="y")
        IconButton(row, Icon.ADD, self._enqueue, tooltip=texts.ENQUEUE_TOOLTIP).pack(side="left", padx=(4, 0), fill="y")
        self.status = StatusLine(self)
        self.status.pack(fill="x", pady=(4, 0))

    def focus_input(self) -> None:
        self._search.focus_input()

    def _play(self) -> None:
        self._submit(self._on_play)

    def _enqueue(self) -> None:
        self._submit(self._on_enqueue)

    def _submit(self, handler: Callable[[str], bool]) -> None:
        uri = self._query_uri()
        if uri and handler(uri):
            self._search.clear()

    def _query_uri(self) -> str | None:
        try:
            return to_media_uri(self._search.query)
        except ValueError:
            self._search.focus_input()
            return None
