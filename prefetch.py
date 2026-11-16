import time
from typing import Callable

from media import is_resolvable
from playback import upcoming
from player import NO_LOCAL_SONGS, LocalSongs, Player, QueueItem
from resolver import BackgroundResolver
from settings import DEFAULT_PREFETCH
from track import ResolvedTrack

RETRY_AFTER_SECONDS = 30.0


class Prefetcher:
    def __init__(
        self,
        player: Player,
        resolver: BackgroundResolver,
        depth: int = DEFAULT_PREFETCH,
        local_songs: LocalSongs = NO_LOCAL_SONGS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._player = player
        self._local_songs = local_songs
        self._resolver = resolver
        self._clock = clock
        self._requested: set[str] = set()
        self._failed: dict[str, float] = {}
        self.depth = depth

    def update(self, queue: list[QueueItem], wrap: bool = False) -> None:
        window = [item.uri for _, item in upcoming(queue, wrap)[: self.depth]]
        self._requested.intersection_update(window)
        self._failed = {uri: at for uri, at in self._failed.items() if uri in window}
        for uri in window:
            self._request(uri)

    def reset(self) -> None:
        self._requested.clear()
        self._failed.clear()

    def _request(self, uri: str) -> None:
        if uri in self._requested or not is_resolvable(uri) or self._cooling_down(uri):
            return
        self._requested.add(uri)
        local = self._local_songs.find(uri)
        if local:
            self._player.attach_local(uri, local)
            return
        self._resolver.submit(uri, lambda resolved: self._attach(uri, resolved))

    def _cooling_down(self, uri: str) -> bool:
        failed_at = self._failed.get(uri)
        return failed_at is not None and self._clock() - failed_at < RETRY_AFTER_SECONDS

    def _attach(self, uri: str, resolved: ResolvedTrack | None) -> None:
        if resolved is None:
            self._requested.discard(uri)
            self._failed[uri] = self._clock()
            return
        self._requested.add(resolved.page_url)
        self._player.attach_stream(uri, resolved)
