import shutil
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LOW_SPACE_BYTES = 1024**3
LOW_SPACE_RATIO = 0.05
SPACE_CACHE_SECONDS = 30.0


@dataclass(frozen=True)
class DriveSpace:
    free_bytes: int
    total_bytes: int
    drive: str

    @property
    def is_low(self) -> bool:
        return self.free_bytes < LOW_SPACE_BYTES or self.free_bytes < self.total_bytes * LOW_SPACE_RATIO


def used_ratio(used: int, limit: int) -> float:
    if limit <= 0:
        return 1.0 if used > 0 else 0.0
    return min(max(used / limit, 0.0), 1.0)


def used_percent(ratio: float) -> int:
    return round(ratio * 100)


def drive_space(folder: Path) -> DriveSpace | None:
    probe = folder
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError:
        return None
    return DriveSpace(usage.free, usage.total, folder.drive)


class DriveSpaceReader:
    def __init__(
        self,
        measure: Callable[[Path], DriveSpace | None] = drive_space,
        max_age: float = SPACE_CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._measure = measure
        self._max_age = max_age
        self._clock = clock
        self._known: tuple[Path, DriveSpace | None, float] | None = None
        self._pending: tuple[Path, Future[DriveSpace | None]] | None = None

    def read(self, folder: Path) -> DriveSpace | None:
        self._collect()
        known = self._known
        matches = known is not None and known[0] == folder
        fresh = matches and self._clock() - known[2] < self._max_age
        if not fresh and self._pending is None:
            self._pending = (folder, self._start(folder))
        return known[1] if matches else None

    def _collect(self) -> None:
        if self._pending is None or not self._pending[1].done():
            return
        folder, future = self._pending
        self._pending = None
        self._known = (folder, None if future.exception() else future.result(), self._clock())

    def _start(self, folder: Path) -> Future[DriveSpace | None]:
        future: Future[DriveSpace | None] = Future()

        def work() -> None:
            try:
                future.set_result(self._measure(folder))
            except Exception as error:
                future.set_exception(error)

        threading.Thread(target=work, name="drive-space", daemon=True).start()
        return future
