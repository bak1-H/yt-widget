import time
import unittest

from player import QueueItem
from prefetch import Prefetcher
from resolver import BackgroundResolver, ResolveError, resolve_target
from track import LocalSong, ResolvedTrack

SEARCH_URI = "ytdl://ytsearch:daft punk"
RESOLVED = ResolvedTrack("Around The World", "https://www.youtube.com/watch?v=x", "https://stream")


class FakePlayer:
    def __init__(self) -> None:
        self.attached: list[tuple[str, ResolvedTrack]] = []
        self.attached_local: list[tuple[str, LocalSong]] = []

    def attach_stream(self, uri: str, resolved: ResolvedTrack) -> None:
        self.attached.append((uri, resolved))

    def attach_local(self, uri: str, local: LocalSong) -> None:
        self.attached_local.append((uri, local))


def wait_and_deliver(resolver: BackgroundResolver) -> None:
    deadline = time.monotonic() + 2
    while resolver._pending and time.monotonic() < deadline:
        time.sleep(0.01)
        resolver.deliver()


class ResolveTargetTest(unittest.TestCase):
    def test_search_and_url(self) -> None:
        self.assertEqual(resolve_target(SEARCH_URI), "ytsearch1:daft punk")
        self.assertEqual(resolve_target(RESOLVED.page_url), RESOLVED.page_url)


class BackgroundResolverTest(unittest.TestCase):
    def test_delivers_result_and_failure(self) -> None:
        def resolve(uri: str) -> ResolvedTrack:
            if uri == "bad":
                raise ResolveError(uri)
            return RESOLVED

        resolver = BackgroundResolver(resolve)
        results: list[ResolvedTrack | None] = []
        resolver.submit("good", results.append)
        resolver.submit("bad", results.append)
        wait_and_deliver(resolver)
        resolver.close()
        self.assertCountEqual(results, [RESOLVED, None])


class PrefetcherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[str] = []
        self.player = FakePlayer()
        self.resolver = BackgroundResolver(lambda uri: self.calls.append(uri) or RESOLVED)
        self.prefetcher = Prefetcher(self.player, self.resolver)

    def tearDown(self) -> None:
        self.resolver.close()

    def test_resolves_next_item_once(self) -> None:
        queue = [QueueItem("Now", "https://now", True), QueueItem(None, SEARCH_URI, False)]
        self.prefetcher.update(queue)
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [SEARCH_URI])
        self.assertEqual(self.player.attached, [(SEARCH_URI, RESOLVED)])
        self.prefetcher.update([queue[0], QueueItem(RESOLVED.title, RESOLVED.page_url, False)])
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [SEARCH_URI])

    def test_ignores_non_youtube_and_empty_queue(self) -> None:
        self.prefetcher.update([])
        self.prefetcher.update([QueueItem("Now", "x", True), QueueItem(None, "https://example.com/a.mp3", False)])
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [])


    def test_looks_ahead_two_items_and_not_a_third(self) -> None:
        uris = [f"{SEARCH_URI} {number}" for number in range(3)]
        queue = [QueueItem("Now", "https://now", True), *(QueueItem(None, uri, False) for uri in uris)]
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.assertCountEqual(self.calls, uris[:2])

    def test_cached_song_is_attached_locally_without_resolving(self) -> None:
        local = LocalSong("C:/songs/x.webm", "Cached")

        class Cached:
            def find(self, uri: str) -> LocalSong | None:
                return local if uri == RESOLVED.page_url else None

        prefetcher = Prefetcher(self.player, self.resolver, local_songs=Cached())
        prefetcher.update([QueueItem("Now", "https://now", True), QueueItem(None, RESOLVED.page_url, False)])
        wait_and_deliver(self.resolver)
        self.assertEqual(self.player.attached_local, [(RESOLVED.page_url, local)])
        self.assertEqual((self.calls, self.player.attached), ([], []))

    def test_replaying_a_song_that_left_the_window_prefetches_it_again(self) -> None:
        queue = [QueueItem("Now", "https://now", True), QueueItem(None, SEARCH_URI, False)]
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.prefetcher.update([queue[0]])
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [SEARCH_URI, SEARCH_URI])

    def test_failed_resolve_is_retried_only_after_the_cooldown(self) -> None:
        now = [0.0]
        resolver = BackgroundResolver(lambda uri: (_ for _ in ()).throw(ResolveError(uri)))
        prefetcher = Prefetcher(self.player, resolver, clock=lambda: now[0])
        queue = [QueueItem("Now", "https://now", True), QueueItem(None, SEARCH_URI, False)]
        submitted: list[str] = []
        original = resolver.submit
        resolver.submit = lambda uri, callback: (submitted.append(uri), original(uri, callback))[1]
        prefetcher.update(queue)
        wait_and_deliver(resolver)
        prefetcher.update(queue)
        now[0] = 31.0
        prefetcher.update(queue)
        wait_and_deliver(resolver)
        resolver.close()
        self.assertEqual(submitted, [SEARCH_URI, SEARCH_URI])

    def test_reset_forgets_everything(self) -> None:
        queue = [QueueItem("Now", "https://now", True), QueueItem(None, SEARCH_URI, False)]
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.prefetcher.reset()
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [SEARCH_URI, SEARCH_URI])

    def test_a_failing_callback_does_not_drop_the_others(self) -> None:
        results: list[ResolvedTrack | None] = []

        def explode(_: ResolvedTrack | None) -> None:
            raise RuntimeError("boom")

        self.resolver.submit("a", explode)
        self.resolver.submit("b", results.append)
        deadline = time.monotonic() + 2
        while self.resolver._pending and time.monotonic() < deadline:
            time.sleep(0.01)
            try:
                self.resolver.deliver()
            except RuntimeError:
                pass
        self.assertEqual(results, [RESOLVED])

    def test_wrapping_prefetches_the_start_of_the_queue_from_the_last_song(self) -> None:
        queue = [QueueItem(None, SEARCH_URI, False), QueueItem("Now", "https://now", True)]
        self.prefetcher.update(queue)
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [])
        self.prefetcher.update(queue, wrap=True)
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [SEARCH_URI])

    def test_depth_zero_resolves_nothing(self) -> None:
        self.prefetcher.depth = 0
        self.prefetcher.update([QueueItem("Now", "https://now", True), QueueItem(None, SEARCH_URI, False)])
        wait_and_deliver(self.resolver)
        self.assertEqual(self.calls, [])

    def test_advancing_requests_the_next_item_that_came_into_range(self) -> None:
        uris = [f"{SEARCH_URI} {number}" for number in range(3)]
        items = [QueueItem(None, uri, False) for uri in uris]
        self.prefetcher.update([QueueItem("Now", "https://now", True), *items])
        wait_and_deliver(self.resolver)
        self.assertCountEqual(self.calls, uris[:2])
        self.prefetcher.update([QueueItem(None, uris[0], False), QueueItem(None, uris[1], True), items[2]])
        wait_and_deliver(self.resolver)
        self.assertCountEqual(self.calls, uris)


if __name__ == "__main__":
    unittest.main()
