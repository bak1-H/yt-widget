import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Protocol

from media import is_video_id, watch_url
from playback import PlaybackState
from processes import TrackedProcesses
from repeat import RepeatMode
from track import Track

MIX_ENTRIES = 25
MIX_TIMEOUT_SECONDS = 60
RECOMMENDATION_LIMIT = 5
FAILURE_COOLDOWN_SECONDS = 60.0
MAX_UPCOMING_BEFORE_REQUEST = 1
UNUSABLE_TITLES = {"NA", "[Private video]", "[Deleted video]"}
FIELD_SEPARATOR = "|"

OnReady = Callable[[str, list["Recommendation"]], None]


class RecommendationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Recommendation:
    video_id: str
    title: str

    @property
    def track(self) -> Track:
        return Track(self.title, watch_url(self.video_id))


class RecommendationSource(Protocol):
    def fetch(self, seed_id: str) -> list[Recommendation]: ...


def mix_command(executable: Path, seed_id: str) -> list[str]:
    mix_url = f"{watch_url(seed_id)}&list=RD{seed_id}"
    return [
        str(executable),
        "--flat-playlist",
        "--no-warnings",
        "--playlist-end",
        str(MIX_ENTRIES),
        "--print",
        f"%(id)s{FIELD_SEPARATOR}%(title)s",
        "--",
        mix_url,
    ]


def parse_mix(output: str) -> list[Recommendation]:
    found: list[Recommendation] = []
    for line in output.split("\n"):
        song_id, _, title = line.rstrip("\r").partition(FIELD_SEPARATOR)
        title = title.strip()
        if is_video_id(song_id) and title and title not in UNUSABLE_TITLES:
            found.append(Recommendation(song_id, title))
    return found


class YtDlpMixSource:
    def __init__(self, executable: Path, processes: TrackedProcesses) -> None:
        self._executable = executable
        self._processes = processes

    def fetch(self, seed_id: str) -> list[Recommendation]:
        try:
            output = self._processes.run(mix_command(self._executable, seed_id), MIX_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError) as error:
            raise RecommendationError(f"Could not fetch recommendations for {seed_id}") from error
        return parse_mix(output)


def pick_recommendations(
    candidates: Iterable[Recommendation], seed_id: str, excluded_ids: Iterable[str], limit: int = RECOMMENDATION_LIMIT
) -> list[Recommendation]:
    taken = {seed_id, *excluded_ids}
    picked: list[Recommendation] = []
    for candidate in candidates:
        if len(picked) == limit:
            break
        if candidate.video_id not in taken:
            taken.add(candidate.video_id)
            picked.append(candidate)
    return picked


def queue_ended(*, was_ended: bool, previous: PlaybackState, state: PlaybackState, user_acted: bool) -> bool:
    if user_acted or state is not PlaybackState.IDLE:
        return False
    return was_ended or previous is PlaybackState.PLAYING


def should_request(
    *,
    enabled: bool,
    repeat_mode: RepeatMode,
    state: PlaybackState,
    upcoming_count: int,
    ended: bool,
    seed: str | None,
    used_seeds: set[str],
    in_flight: bool,
    now: float,
    retry_at: float,
) -> bool:
    if not enabled or repeat_mode is not RepeatMode.OFF or in_flight or now < retry_at:
        return False
    if seed is None or seed in used_seeds:
        return False
    if state is PlaybackState.PLAYING:
        return upcoming_count <= MAX_UPCOMING_BEFORE_REQUEST
    return state is PlaybackState.IDLE and upcoming_count == 0 and ended


class Autoplay:
    def __init__(self, source: RecommendationSource, clock: Callable[[], float] = time.monotonic) -> None:
        self._source = source
        self._clock = clock
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recommender")
        self._pending: tuple[str, Future[list[Recommendation]]] | None = None
        self._used_seeds: set[str] = set()
        self._suggested: dict[str, str] = {}
        self._retry_at = 0.0
        self._error_reported = False

    @property
    def titles(self) -> dict[str, str]:
        return dict(self._suggested)

    def wants(self, enabled: bool, repeat_mode: RepeatMode, state: PlaybackState, upcoming_count: int, ended: bool, seed: str | None) -> bool:
        return should_request(
            enabled=enabled,
            repeat_mode=repeat_mode,
            state=state,
            upcoming_count=upcoming_count,
            ended=ended,
            seed=seed,
            used_seeds=self._used_seeds,
            in_flight=self._pending is not None,
            now=self._clock(),
            retry_at=self._retry_at,
        )

    def request(self, seed_id: str) -> None:
        self._used_seeds.add(seed_id)
        self._pending = (seed_id, self._executor.submit(self._source.fetch, seed_id))

    def follow(self, seed: str | None) -> None:
        if seed is None or self._pending is None or self._pending[0] == seed:
            return
        stale_seed, future = self._pending
        future.cancel()
        self._pending = None
        self._used_seeds.discard(stale_seed)

    def deliver(self, on_ready: OnReady, on_error: Callable[[], None]) -> None:
        if self._pending is None or not self._pending[1].done():
            return
        seed_id, future = self._pending
        self._pending = None
        if future.exception():
            self._used_seeds.discard(seed_id)
            self._retry_at = self._clock() + FAILURE_COOLDOWN_SECONDS
            self._report_once(on_error)
            return
        self._error_reported = False
        on_ready(seed_id, future.result())

    def remember(self, tracks: Iterable[Track]) -> None:
        self._suggested.update((track.uri, track.title) for track in tracks)

    def is_suggested(self, uri: str) -> bool:
        return uri in self._suggested

    def played(self, uri: str) -> None:
        self._suggested.pop(uri, None)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _report_once(self, on_error: Callable[[], None]) -> None:
        if not self._error_reported:
            self._error_reported = True
            on_error()
