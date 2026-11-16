import unittest

from playback import LoadTracker, PlaybackState, reinsert_index, resolve_state, take_snapshot, upcoming
from player import PlaybackStatus, QueueItem


def make_status(*, idle: bool = False, paused: bool = False, buffering: bool = False) -> PlaybackStatus:
    return PlaybackStatus(title=None, path=None, position=None, duration=None, paused=paused, idle=idle, buffering=buffering)


IDLE = make_status(idle=True)
PLAYING = make_status()


class ResolveStateTest(unittest.TestCase):
    def test_states(self) -> None:
        self.assertIs(resolve_state(IDLE), PlaybackState.IDLE)
        self.assertIs(resolve_state(make_status(paused=True, buffering=True)), PlaybackState.PAUSED)
        self.assertIs(resolve_state(make_status(buffering=True)), PlaybackState.LOADING)
        self.assertIs(resolve_state(PLAYING), PlaybackState.PLAYING)


class SnapshotTest(unittest.TestCase):
    def test_keeps_uris_current_index_position_and_source_playlist(self) -> None:
        queue = [QueueItem("a", "uri-a", False), QueueItem("b", "uri-b", True), QueueItem(None, "uri-c", False)]
        snapshot = take_snapshot(queue, 12.5, "Mix")
        self.assertEqual((snapshot.uris, snapshot.index, snapshot.position, snapshot.playlist), (("uri-a", "uri-b", "uri-c"), 1, 12.5, "Mix"))

    def test_empty_queue_has_nothing_to_restore(self) -> None:
        self.assertEqual(take_snapshot([], None, None).uris, ())


class LoadTrackerTest(unittest.TestCase):
    def test_idle_without_request(self) -> None:
        self.assertIs(LoadTracker().state(IDLE, now=0), PlaybackState.IDLE)

    def test_loading_during_grace_period(self) -> None:
        tracker = LoadTracker(grace_seconds=3)
        tracker.request(now=10)
        self.assertIs(tracker.state(IDLE, now=12), PlaybackState.LOADING)

    def test_failure_sticks_until_next_request(self) -> None:
        tracker = LoadTracker(grace_seconds=3)
        tracker.request(now=10)
        self.assertIs(tracker.state(IDLE, now=14), PlaybackState.FAILED)
        self.assertIs(tracker.state(IDLE, now=20), PlaybackState.FAILED)
        tracker.request(now=21)
        self.assertIs(tracker.state(IDLE, now=22), PlaybackState.LOADING)

    def test_failure_after_long_load(self) -> None:
        tracker = LoadTracker(grace_seconds=3)
        tracker.request(now=10)
        self.assertIs(tracker.state(make_status(buffering=True), now=15), PlaybackState.LOADING)
        self.assertIs(tracker.state(IDLE, now=22), PlaybackState.FAILED)

    def test_playback_clears_request(self) -> None:
        tracker = LoadTracker(grace_seconds=3)
        tracker.request(now=10)
        self.assertIs(tracker.state(PLAYING, now=11), PlaybackState.PLAYING)
        self.assertIs(tracker.state(IDLE, now=30), PlaybackState.IDLE)


class UpcomingTest(unittest.TestCase):
    def test_items_after_current(self) -> None:
        queue = [QueueItem("a", "1", False), QueueItem("b", "2", True), QueueItem("c", "3", False)]
        self.assertEqual(upcoming(queue), [(2, queue[2])])

    def test_empty_without_current(self) -> None:
        self.assertEqual(upcoming([QueueItem("a", "1", False)]), [])

    def test_wrapping_lists_the_rest_of_the_queue_then_the_start(self) -> None:
        queue = [QueueItem("a", "1", False), QueueItem("b", "2", False), QueueItem("c", "3", True), QueueItem("d", "4", False)]
        self.assertEqual([index for index, _ in upcoming(queue, wrap=True)], [3, 0, 1])
        self.assertEqual([index for index, _ in upcoming(queue)], [3])

    def test_wrapping_from_the_last_song_shows_the_loop(self) -> None:
        queue = [QueueItem("a", "1", False), QueueItem("b", "2", True)]
        self.assertEqual([index for index, _ in upcoming(queue, wrap=True)], [0])
        self.assertEqual(upcoming([QueueItem("a", "1", False)], wrap=True), [])



class ReinsertIndexTest(unittest.TestCase):
    def test_keeps_the_original_slot_when_it_is_still_ahead(self) -> None:
        self.assertEqual(reinsert_index(4, 1, 8), 4)

    def test_never_lands_before_or_on_the_current_song(self) -> None:
        self.assertEqual(reinsert_index(2, 2, 8), 3)
        self.assertEqual(reinsert_index(0, 5, 8), 6)

    def test_is_clamped_to_the_queue_length(self) -> None:
        self.assertEqual(reinsert_index(9, 1, 4), 4)
        self.assertEqual(reinsert_index(3, None, 2), 2)


if __name__ == "__main__":
    unittest.main()
