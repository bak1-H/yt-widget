import time
import unittest
from pathlib import Path

from playback import PlaybackState
from recommendations import (
    MIX_ENTRIES,
    RECOMMENDATION_LIMIT,
    Autoplay,
    Recommendation,
    RecommendationError,
    mix_command,
    parse_mix,
    pick_recommendations,
    queue_ended,
    should_request,
)
from repeat import RepeatMode
from track import Track

SEED = "aaaaaaaaaaa"


def song(letter: str) -> Recommendation:
    return Recommendation(letter * 11, f"Song {letter}")


def decide(**overrides: object) -> bool:
    arguments: dict[str, object] = dict(
        enabled=True,
        repeat_mode=RepeatMode.OFF,
        state=PlaybackState.PLAYING,
        upcoming_count=1,
        ended=True,
        seed=SEED,
        used_seeds=set(),
        in_flight=False,
        now=100.0,
        retry_at=0.0,
    )
    return should_request(**{**arguments, **overrides})


class PickRecommendationsTest(unittest.TestCase):
    def test_drops_the_seed_the_queue_and_the_history_keeping_order(self) -> None:
        candidates = [song("a"), song("b"), song("c"), song("d"), song("e")]
        picked = pick_recommendations(candidates, SEED, {song("c").video_id, song("e").video_id})
        self.assertEqual(picked, [song("b"), song("d")])

    def test_caps_the_amount_and_ignores_repeated_candidates(self) -> None:
        candidates = [song(letter) for letter in "bbcdefghi"]
        picked = pick_recommendations(candidates, SEED, set())
        self.assertEqual(len(picked), RECOMMENDATION_LIMIT)
        self.assertEqual([item.video_id[0] for item in picked], list("bcdef"))
        self.assertEqual(len(pick_recommendations(candidates, SEED, set(), limit=2)), 2)

    def test_nothing_new_gives_an_empty_list(self) -> None:
        self.assertEqual(pick_recommendations([song("a")], SEED, set()), [])
        self.assertEqual(pick_recommendations([], SEED, set()), [])


class ShouldRequestTest(unittest.TestCase):
    def test_asks_when_playing_with_at_most_one_song_left(self) -> None:
        self.assertTrue(decide(upcoming_count=1))
        self.assertTrue(decide(upcoming_count=0))
        self.assertFalse(decide(upcoming_count=2))

    def test_asks_after_the_queue_ended_only_when_idle(self) -> None:
        self.assertTrue(decide(state=PlaybackState.IDLE, upcoming_count=0))
        self.assertFalse(decide(state=PlaybackState.IDLE, upcoming_count=1))
        for state in (PlaybackState.PAUSED, PlaybackState.LOADING, PlaybackState.FAILED):
            self.assertFalse(decide(state=state, upcoming_count=0))

    def test_idle_without_a_natural_end_never_asks(self) -> None:
        self.assertFalse(decide(state=PlaybackState.IDLE, upcoming_count=0, ended=False))
        self.assertTrue(decide(state=PlaybackState.PLAYING, upcoming_count=0, ended=False))

    def test_disabled_or_repeating_never_asks(self) -> None:
        self.assertFalse(decide(enabled=False))
        self.assertFalse(decide(repeat_mode=RepeatMode.QUEUE))
        self.assertFalse(decide(repeat_mode=RepeatMode.SONG))

    def test_unknown_or_already_used_seed_never_asks(self) -> None:
        self.assertFalse(decide(seed=None))
        self.assertFalse(decide(used_seeds={SEED}))

    def test_one_request_at_a_time_and_cooldown(self) -> None:
        self.assertFalse(decide(in_flight=True))
        self.assertFalse(decide(now=50.0, retry_at=60.0))
        self.assertTrue(decide(now=60.0, retry_at=60.0))


class QueueEndedTest(unittest.TestCase):
    def ended(self, previous: PlaybackState, state: PlaybackState, was_ended: bool = False, user_acted: bool = False) -> bool:
        return queue_ended(was_ended=was_ended, previous=previous, state=state, user_acted=user_acted)

    def test_playing_then_idle_is_a_natural_end(self) -> None:
        self.assertTrue(self.ended(PlaybackState.PLAYING, PlaybackState.IDLE))

    def test_a_user_command_in_the_same_tick_is_not_a_natural_end(self) -> None:
        self.assertFalse(self.ended(PlaybackState.PLAYING, PlaybackState.IDLE, user_acted=True))

    def test_startup_and_stopped_states_are_not_a_natural_end(self) -> None:
        for previous in (PlaybackState.IDLE, PlaybackState.FAILED, PlaybackState.LOADING, PlaybackState.PAUSED):
            self.assertFalse(self.ended(previous, PlaybackState.IDLE))

    def test_the_end_is_kept_while_idle_and_lost_after_a_command_or_new_playback(self) -> None:
        self.assertTrue(self.ended(PlaybackState.IDLE, PlaybackState.IDLE, was_ended=True))
        self.assertFalse(self.ended(PlaybackState.IDLE, PlaybackState.IDLE, was_ended=True, user_acted=True))
        self.assertFalse(self.ended(PlaybackState.IDLE, PlaybackState.LOADING, was_ended=True))
        self.assertFalse(self.ended(PlaybackState.LOADING, PlaybackState.PLAYING, was_ended=True))


class MixCommandTest(unittest.TestCase):
    def test_limits_entries_and_separates_the_url(self) -> None:
        command = mix_command(Path("yt-dlp"), SEED)
        self.assertEqual(command[command.index("--playlist-end") + 1], str(MIX_ENTRIES))
        self.assertEqual(MIX_ENTRIES, 25)
        self.assertEqual(command[-2], "--")
        self.assertEqual(command[-1], f"https://www.youtube.com/watch?v={SEED}&list=RD{SEED}")
        self.assertIn("--flat-playlist", command)

    def test_parse_keeps_titles_with_separators_and_skips_unusable_lines(self) -> None:
        output = "\n".join(
            [
                f"{SEED}|Seed | live",
                "bbbbbbbbbbb|[Private video]",
                "ccccccccccc|NA",
                "short|Bad id",
                "ddddddddddd|",
                "eeeeeeeeeee|Fine\r",
                "",
            ]
        )
        self.assertEqual(parse_mix(output), [Recommendation(SEED, "Seed | live"), Recommendation("eeeeeeeeeee", "Fine")])

    def test_recommendation_becomes_a_normal_page_track(self) -> None:
        self.assertEqual(song("b").track, Track("Song b", "https://www.youtube.com/watch?v=bbbbbbbbbbb"))


class FakeSource:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    def fetch(self, seed_id: str) -> list[Recommendation]:
        self.calls.append(seed_id)
        if self.fail:
            raise RecommendationError(seed_id)
        return [song("b"), song("c")]


class AutoplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [0.0]
        self.source = FakeSource()
        self.autoplay = Autoplay(self.source, clock=lambda: self.now[0])
        self.ready: list[tuple[str, list[Recommendation]]] = []
        self.errors = 0

    def tearDown(self) -> None:
        self.autoplay.close()

    def wants(self) -> bool:
        return self.autoplay.wants(True, RepeatMode.OFF, PlaybackState.PLAYING, 0, True, SEED)

    def settle(self) -> None:
        deadline = time.monotonic() + 2
        while self.autoplay._pending and time.monotonic() < deadline:
            time.sleep(0.01)
            self.autoplay.deliver(lambda seed, found: self.ready.append((seed, found)), self.count_error)

    def count_error(self) -> None:
        self.errors += 1

    def test_delivers_once_and_never_asks_the_same_seed_again(self) -> None:
        self.assertTrue(self.wants())
        self.autoplay.request(SEED)
        self.assertFalse(self.wants())
        self.settle()
        self.assertEqual(self.ready, [(SEED, [song("b"), song("c")])])
        self.assertFalse(self.wants())
        self.assertEqual(self.source.calls, [SEED])

    def test_failure_waits_for_the_cooldown_then_retries_and_reports_once(self) -> None:
        self.source.fail = True
        self.autoplay.request(SEED)
        self.settle()
        self.assertEqual((self.errors, self.ready), (1, []))
        self.assertFalse(self.wants())
        self.now[0] = 61.0
        self.assertTrue(self.wants())
        self.autoplay.request(SEED)
        self.settle()
        self.assertEqual(self.errors, 1)

    def test_a_later_outage_is_reported_again_after_a_successful_fetch(self) -> None:
        self.source.fail = True
        self.autoplay.request(SEED)
        self.settle()
        self.source.fail = False
        self.now[0] = 61.0
        self.autoplay.request(SEED)
        self.settle()
        self.source.fail = True
        self.now[0] = 200.0
        self.autoplay.request(SEED)
        self.settle()
        self.assertEqual(self.errors, 2)

    def test_following_another_seed_drops_the_pending_request_and_frees_the_old_seed(self) -> None:
        self.autoplay.request(SEED)
        self.autoplay.follow("zzzzzzzzzzz")
        self.assertFalse(self.autoplay._pending)
        self.settle()
        self.assertEqual(self.ready, [])
        self.assertTrue(self.wants())

    def test_following_the_same_or_no_seed_keeps_the_pending_request(self) -> None:
        self.autoplay.request(SEED)
        self.autoplay.follow(SEED)
        self.autoplay.follow(None)
        self.settle()
        self.assertEqual([seed for seed, _ in self.ready], [SEED])

    def test_suggested_songs_are_marked_until_they_play(self) -> None:
        tracks = [song("b").track, song("c").track]
        self.autoplay.remember(tracks)
        self.assertTrue(self.autoplay.is_suggested(tracks[0].uri))
        self.assertEqual(self.autoplay.titles, {tracks[0].uri: "Song b", tracks[1].uri: "Song c"})
        self.autoplay.played(tracks[0].uri)
        self.assertFalse(self.autoplay.is_suggested(tracks[0].uri))
        self.assertTrue(self.autoplay.is_suggested(tracks[1].uri))
        self.assertFalse(self.autoplay.is_suggested("https://www.youtube.com/watch?v=zzzzzzzzzzz"))


if __name__ == "__main__":
    unittest.main()
