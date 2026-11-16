import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Callable

from callbacks import run_each
from media import SEARCH_PREFIX
from processes import TrackedProcesses
from track import ResolvedTrack

RESOLVE_TIMEOUT_SECONDS = 60
WORKERS = 2
OUTPUT_TEMPLATES = ("%(title)s", "%(webpage_url)s", "%(url)s")

OnResolved = Callable[[ResolvedTrack | None], None]


class ResolveError(RuntimeError):
    pass


def resolve_target(uri: str) -> str:
    if uri.startswith(SEARCH_PREFIX):
        return f"ytsearch1:{uri[len(SEARCH_PREFIX):]}"
    return uri


class YtDlpResolver:
    def __init__(self, executable: Path, processes: TrackedProcesses) -> None:
        self._executable = executable
        self._processes = processes

    def resolve(self, uri: str) -> ResolvedTrack:
        prints = [argument for template in OUTPUT_TEMPLATES for argument in ("--print", template)]
        command = [str(self._executable), "-f", "bestaudio/best", "--no-playlist", "--no-warnings", *prints, "--", resolve_target(uri)]
        try:
            output = self._processes.run(command, RESOLVE_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError) as error:
            raise ResolveError(f"Could not resolve {uri}") from error
        lines = output.splitlines()
        if len(lines) != len(OUTPUT_TEMPLATES):
            raise ResolveError(f"Unexpected yt-dlp output for {uri}")
        return ResolvedTrack(*lines)


def _notify(future: Future[ResolvedTrack], on_resolved: OnResolved) -> None:
    on_resolved(None if future.exception() else future.result())


class BackgroundResolver:
    def __init__(self, resolve: Callable[[str], ResolvedTrack], workers: int = WORKERS) -> None:
        self._resolve = resolve
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="resolver")
        self._pending: list[tuple[Future[ResolvedTrack], OnResolved]] = []

    def submit(self, uri: str, on_resolved: OnResolved) -> None:
        self._pending.append((self._executor.submit(self._resolve, uri), on_resolved))

    def deliver(self) -> None:
        finished = [entry for entry in self._pending if entry[0].done()]
        self._pending = [entry for entry in self._pending if entry not in finished]
        run_each(partial(_notify, future, on_resolved) for future, on_resolved in finished)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
