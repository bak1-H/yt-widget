import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Callable

from callbacks import run_each
from song_cache import CacheReport

CacheTask = Callable[[threading.Event], CacheReport]
OnFinished = Callable[[CacheReport | None], None]


def _notify(future: Future[CacheReport], on_finished: OnFinished) -> None:
    on_finished(None if future.exception() else future.result())


class CacheJobs:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cache-jobs")
        self._stop = threading.Event()
        self._pending: list[tuple[Future[CacheReport], OnFinished]] = []

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def submit(self, task: CacheTask, on_finished: OnFinished) -> None:
        self._pending.append((self._executor.submit(task, self._stop), on_finished))

    def deliver(self) -> None:
        finished = [entry for entry in self._pending if entry[0].done()]
        self._pending = [entry for entry in self._pending if entry not in finished]
        run_each(partial(_notify, future, on_finished) for future, on_finished in finished)

    def close(self) -> None:
        self._stop.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
