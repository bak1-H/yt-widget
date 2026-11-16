from dataclasses import dataclass
from typing import Mapping, Protocol

from repeat import RepeatMode
from track import LocalSong, ResolvedTrack


class PlayerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlaybackStatus:
    title: str | None
    path: str | None
    position: float | None
    duration: float | None
    paused: bool
    idle: bool
    buffering: bool
    local_file: str | None = None


@dataclass(frozen=True)
class QueueItem:
    title: str | None
    uri: str
    current: bool


@dataclass(frozen=True)
class Observation:
    status: PlaybackStatus
    queue: list[QueueItem]


class LocalSongs(Protocol):
    def find(self, uri: str) -> LocalSong | None: ...


class NoLocalSongs:
    def find(self, uri: str) -> LocalSong | None:
        return None


NO_LOCAL_SONGS = NoLocalSongs()


class Player(Protocol):
    def load(self, uri: str) -> None: ...

    def enqueue(self, uri: str) -> None: ...

    def play_next(self, uri: str) -> None: ...

    def remove(self, index: int) -> None: ...

    def insert(self, uri: str, index: int) -> None: ...

    def play_all(self, uris: list[str], start: int = 0) -> None: ...

    def attach_stream(self, uri: str, resolved: ResolvedTrack) -> None: ...

    def attach_local(self, uri: str, local: LocalSong) -> None: ...

    def play_at(self, index: int) -> None: ...

    def toggle_pause(self) -> None: ...

    def next(self) -> None: ...

    def previous(self) -> None: ...

    def seek(self, seconds: float) -> None: ...

    def set_volume(self, volume: int) -> None: ...

    def set_repeat(self, mode: RepeatMode) -> None: ...

    def relocate_local(self, changes: Mapping[str, str | None]) -> None: ...

    def observe(self) -> Observation: ...

    def restart(self) -> None: ...

    def close(self) -> None: ...
