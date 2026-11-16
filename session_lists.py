import tkinter as tk
from typing import Callable

import texts
import theme
from components import StatusLine
from history import History
from media import shorten
from playback import reinsert_index
from player import Player
from song_menu import MenuContext, SongMenu
from track import Track
from track_rows import RowHandlers, RowItem, TrackRows, locate

TITLE_PREVIEW_LENGTH = 28


class QueueList(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        player: Player,
        song_menu: SongMenu,
        status: StatusLine,
        begin_playback: Callable[[Callable[[], None]], bool],
        run: Callable[[Callable[[], None]], bool],
        is_downloaded: Callable[[str], bool],
        is_suggested: Callable[[str], bool],
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._is_suggested = is_suggested
        self._player = player
        self._song_menu = song_menu
        self._status = status
        self._begin_playback = begin_playback
        self._run = run
        self._items: list[tuple[int, Track]] = []
        self._rows = TrackRows(self, texts.QUEUE_EMPTY, RowHandlers(self._play, self._open_menu, self._remove), is_downloaded, numbered=True)
        self._rows.pack(fill="x")

    def show(self, items: list[tuple[int, Track]]) -> None:
        self._items = items
        self._rows.show([RowItem(track.title, track.uri, self._is_suggested(track.uri)) for _, track in items])

    def refresh_markers(self) -> None:
        self._rows.refresh_markers()

    def _position(self, row: int, uri: str) -> int | None:
        position = locate([track.uri for _, track in self._items], row, uri)
        if position is None:
            self._status.show(texts.SONG_NOT_IN_LIST)
        return position

    def _play(self, row: int, uri: str) -> None:
        position = self._position(row, uri)
        if position is not None:
            index = self._items[position][0]
            self._begin_playback(lambda: self._player.play_at(index))

    def _open_menu(self, row: int, uri: str, x: int, y: int) -> None:
        position = self._position(row, uri)
        if position is not None:
            context = MenuContext(remove=lambda: self._remove(row, uri), play_now=lambda: self._play(row, uri), queue_entry=True)
            self._song_menu.open(x, y, self._items[position][1], context)

    def _remove(self, row: int, uri: str) -> None:
        position = self._position(row, uri)
        if position is None:
            return
        index, track = self._items[position]
        if not self._run(lambda: self._player.remove(index)):
            return
        self.show([(other - 1 if other > index else other, item) for other, item in self._items if other != index])
        title = shorten(track.title, TITLE_PREVIEW_LENGTH)
        self._status.show_undoable(texts.removed_from_queue(title), lambda: self._restore(track.uri, index))

    def _restore(self, uri: str, index: int) -> None:
        if not self._run(lambda: self._reinsert(uri, index)):
            self._status.show(texts.UNDO_FAILED, "error")

    def _reinsert(self, uri: str, index: int) -> None:
        queue = self._player.observe().queue
        current = next((position for position, item in enumerate(queue) if item.current), None)
        self._player.insert(uri, reinsert_index(index, current, len(queue)))


class HistoryList(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        history: History,
        song_menu: SongMenu,
        status: StatusLine,
        play_now: Callable[[Track], None],
        is_downloaded: Callable[[str], bool],
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._history = history
        self._song_menu = song_menu
        self._status = status
        self._play_now = play_now
        self._rows = TrackRows(self, texts.HISTORY_EMPTY, RowHandlers(self._play, self._open_menu, self._remove), is_downloaded)
        self._rows.pack(fill="x")

    def refresh(self) -> None:
        self._rows.show([RowItem(entry.title, entry.uri) for entry in self._history.entries])

    def refresh_markers(self) -> None:
        self._rows.refresh_markers()

    def _position(self, row: int, uri: str) -> int | None:
        position = locate([entry.uri for entry in self._history.entries], row, uri)
        if position is None:
            self._status.show(texts.SONG_NOT_IN_LIST)
        return position

    def _play(self, row: int, uri: str) -> None:
        position = self._position(row, uri)
        if position is not None:
            self._play_now(self._history.entries[position])

    def _open_menu(self, row: int, uri: str, x: int, y: int) -> None:
        position = self._position(row, uri)
        if position is not None:
            self._song_menu.open(x, y, self._history.entries[position], MenuContext(remove=lambda: self._remove(row, uri)))

    def _remove(self, row: int, uri: str) -> None:
        position = self._position(row, uri)
        if position is None:
            return
        track = self._history.entries[position]
        try:
            self._history.remove(position)
        except OSError:
            self._status.show(texts.HISTORY_SAVE_FAILED, "error")
            return
        self.refresh()
        title = shorten(track.title, TITLE_PREVIEW_LENGTH)
        self._status.show_undoable(texts.removed_from_history(title), lambda: self._restore(position, track))

    def _restore(self, row: int, track: Track) -> None:
        try:
            self._history.insert(row, track)
        except OSError:
            self._status.show(texts.HISTORY_SAVE_FAILED, "error")
            return
        self.refresh()
