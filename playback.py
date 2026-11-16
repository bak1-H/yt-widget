from dataclasses import dataclass
from enum import Enum, auto

from player import PlaybackStatus, QueueItem

LOAD_GRACE_SECONDS = 3.0


class PlaybackState(Enum):
    IDLE = auto()
    LOADING = auto()
    PLAYING = auto()
    PAUSED = auto()
    FAILED = auto()


SETTLED_STATES = {PlaybackState.PLAYING, PlaybackState.PAUSED}


def resolve_state(status: PlaybackStatus) -> PlaybackState:
    if status.idle:
        return PlaybackState.IDLE
    if status.paused:
        return PlaybackState.PAUSED
    if status.buffering:
        return PlaybackState.LOADING
    return PlaybackState.PLAYING


def upcoming(queue: list[QueueItem], wrap: bool = False) -> list[tuple[int, QueueItem]]:
    current = next((index for index, item in enumerate(queue) if item.current), None)
    if current is None:
        return []
    after = [(index, item) for index, item in enumerate(queue) if index > current]
    before = [(index, item) for index, item in enumerate(queue) if index < current] if wrap else []
    return after + before


def reinsert_index(original: int, current: int | None, length: int) -> int:
    first_allowed = 0 if current is None else current + 1
    return min(max(original, first_allowed), length)


@dataclass(frozen=True)
class QueueSnapshot:
    uris: tuple[str, ...]
    index: int
    position: float | None
    playlist: str | None


EMPTY_SNAPSHOT = QueueSnapshot((), 0, None, None)


def take_snapshot(queue: list[QueueItem], position: float | None, playlist: str | None) -> QueueSnapshot:
    current = next((index for index, item in enumerate(queue) if item.current), 0)
    return QueueSnapshot(tuple(item.uri for item in queue), current, position, playlist)


class LoadTracker:
    def __init__(self, grace_seconds: float = LOAD_GRACE_SECONDS) -> None:
        self._grace_seconds = grace_seconds
        self._requested_at: float | None = None
        self._failed = False

    def request(self, now: float) -> None:
        self._requested_at = now
        self._failed = False

    def state(self, status: PlaybackStatus, now: float) -> PlaybackState:
        state = resolve_state(status)
        if state in SETTLED_STATES:
            self._requested_at = None
            self._failed = False
            return state
        if state is PlaybackState.LOADING:
            return state
        if self._requested_at is not None:
            if now - self._requested_at < self._grace_seconds:
                return PlaybackState.LOADING
            self._requested_at = None
            self._failed = True
        return PlaybackState.FAILED if self._failed else PlaybackState.IDLE
