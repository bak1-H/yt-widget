from typing import Callable

import texts
from components import StatusLine
from media import shorten
from player import Player
from playlists import PlaylistLibrary
from track import Track

NAME_PREVIEW_LENGTH = 24

PlaylistChanged = Callable[[str, Track | None], None]


class SongActions:
    def __init__(
        self,
        player: Player,
        library: PlaylistLibrary,
        status: StatusLine,
        begin_playback: Callable[[Callable[[], None]], bool],
        start_loading: Callable[[Callable[[], None]], bool],
        run: Callable[[Callable[[], None]], bool],
        playlist_changed: PlaylistChanged,
        request_new_playlist: Callable[[Track], None],
    ) -> None:
        self._player = player
        self._library = library
        self._status = status
        self._begin_playback = begin_playback
        self._start_loading = start_loading
        self._run = run
        self._playlist_changed = playlist_changed
        self.new_playlist = request_new_playlist

    def play_now(self, track: Track) -> None:
        self._begin_playback(lambda: self._player.load(track.uri))

    def play_next(self, track: Track) -> None:
        if self._run(lambda: self._player.play_next(track.uri)):
            self._status.show(texts.PLAYS_NEXT)

    def enqueue(self, track: Track) -> None:
        if self._start_loading(lambda: self._player.enqueue(track.uri)):
            self._status.show(texts.ADDED_TO_QUEUE)

    def set_membership(self, name: str, track: Track, member: bool) -> None:
        if member:
            self._add(name, track)
        else:
            self._remove(name, track)

    def _add(self, name: str, track: Track) -> None:
        try:
            self._library.add(name, track)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self._playlist_changed(name, track)
        self._status.show(texts.added_to(shorten(name, NAME_PREVIEW_LENGTH)))

    def _remove(self, name: str, track: Track) -> None:
        index = self._library.index_of(name, track.uri)
        if index is None:
            return
        try:
            self._library.remove(name, index)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self._playlist_changed(name, None)
        self._status.show_undoable(texts.removed_from(shorten(name, NAME_PREVIEW_LENGTH)), lambda: self._restore(name, index, track))

    def _restore(self, name: str, index: int, track: Track) -> None:
        if name not in self._library.names():
            self._status.show(texts.no_longer_exists(shorten(name, NAME_PREVIEW_LENGTH)), "error")
            return
        try:
            self._library.insert(name, index, track)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self._playlist_changed(name, None)
