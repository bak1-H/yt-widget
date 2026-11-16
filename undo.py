import time
from typing import Callable

UNDO_WINDOW_SECONDS = 30.0


class UndoSlot:
    def __init__(self, clock: Callable[[], float] = time.monotonic, window: float = UNDO_WINDOW_SECONDS) -> None:
        self._clock = clock
        self._window = window
        self._action: Callable[[], None] | None = None
        self._expires_at = 0.0

    def keep(self, action: Callable[[], None]) -> None:
        self._action = action
        self._expires_at = self._clock() + self._window

    def available(self) -> bool:
        return self._action is not None and self._clock() < self._expires_at

    def remaining(self) -> float:
        return max(self._expires_at - self._clock(), 0.0) if self._action else 0.0

    def discard(self) -> None:
        self._action = None

    def take(self) -> Callable[[], None] | None:
        action = self._action if self.available() else None
        self._action = None
        return action
