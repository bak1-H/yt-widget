import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable

from callbacks import run_each
from media import video_id
from processes import TrackedProcesses
from settings import CacheQuality
from song_cache import SongCache

DOWNLOAD_TIMEOUT_SECONDS = 900
QUALITY_FORMATS = {
    CacheQuality.MAX: "251/bestaudio",
    CacheQuality.MEDIUM: "250/bestaudio[abr<=96]/bestaudio",
}

Download = Callable[[str, Path, CacheQuality], Path]


class DownloadError(RuntimeError):
    pass


class YtDlpDownloader:
    def __init__(self, executable: Path, processes: TrackedProcesses) -> None:
        self._executable = executable
        self._processes = processes

    def download(self, page_url: str, folder: Path, quality: CacheQuality) -> Path:
        song_id = video_id(page_url)
        template = str(folder / song_id).replace("%", "%%") + ".%(ext)s"
        command = [
            str(self._executable),
            "-f",
            QUALITY_FORMATS[quality],
            "--no-playlist",
            "--no-warnings",
            "--no-simulate",
            "--print",
            "after_move:filepath",
            "-o",
            template,
            "--",
            page_url,
        ]
        try:
            folder.mkdir(parents=True, exist_ok=True)
            lines = self._processes.run(command, DOWNLOAD_TIMEOUT_SECONDS).splitlines()
            file = Path(lines[-1]) if lines else None
            if file is None or not file.is_file():
                raise DownloadError(f"yt-dlp produced no file for {page_url}")
            return file
        except (OSError, subprocess.SubprocessError, DownloadError) as error:
            for leftover in folder.glob(f"{song_id}.*"):
                with suppress(OSError):
                    leftover.unlink()
            raise DownloadError(f"Could not download {page_url}") from error


@dataclass(frozen=True)
class _Job:
    song_id: str
    title: str
    folder: Path
    future: Future[Path]


class SongDownloads:
    def __init__(self, cache: SongCache, download: Download) -> None:
        self._cache = cache
        self._download = download
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="downloader")
        self._jobs: list[_Job] = []
        self._in_flight: set[str] = set()
        self._error_reported = False
        self.quality = CacheQuality.MAX

    def request(self, page_url: str, title: str) -> None:
        song_id = video_id(page_url)
        if not self._cache.enabled or song_id is None or song_id in self._in_flight or self._cache.contains(song_id):
            return
        folder = self._cache.folder
        self._in_flight.add(song_id)
        self._jobs.append(_Job(song_id, title, folder, self._executor.submit(self._download, page_url, folder, self.quality)))

    def deliver(self, on_error: Callable[[], None]) -> None:
        finished = [job for job in self._jobs if job.future.done()]
        self._jobs = [job for job in self._jobs if job not in finished]
        run_each(partial(self._finish, job, on_error) for job in finished)

    def _finish(self, job: _Job, on_error: Callable[[], None]) -> None:
        self._in_flight.discard(job.song_id)
        self._complete(job, on_error)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _complete(self, job: _Job, on_error: Callable[[], None]) -> None:
        if job.future.exception():
            self._fail(on_error)
            return
        file = job.future.result()
        try:
            stored = self._cache.enabled and job.folder == self._cache.folder and self._cache.add(job.song_id, file, job.title)
        except OSError:
            self._fail(on_error)
            return
        if not stored:
            with suppress(OSError):
                file.unlink()
            return
        self._error_reported = False

    def _fail(self, on_error: Callable[[], None]) -> None:
        if not self._error_reported:
            on_error()
        self._error_reported = True
