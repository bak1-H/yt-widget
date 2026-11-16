import json
import unittest

from pathlib import Path

from mpv_player import BATCH_SIZE, MpvPlayer
from player import NO_LOCAL_SONGS
from repeat import RepeatMode
from track import LocalSong, ResolvedTrack, Track


class FakePipe:
    def __init__(self, play_state_idle: bool = False, properties: dict | None = None) -> None:
        self.requests: list[dict] = []
        self.properties = properties or {}
        self.outbox = b""
        self.writes = 0
        self.idle = play_state_idle

    def write(self, data: bytes) -> None:
        self.writes += 1
        for line in data.decode().splitlines():
            request = json.loads(line)
            self.requests.append(request)
            command = request["command"]
            data = self.properties.get(command[1], self.idle) if command[0] == "get_property" else self.idle
            reply = {"request_id": request["request_id"], "error": "success", "data": data}
            self.outbox += b'{"event": "noise"}\n' + (json.dumps(reply) + "\n").encode()

    def read(self, size: int) -> bytes:
        chunk, self.outbox = self.outbox[:size], self.outbox[size:]
        return chunk


def player_with(pipe: FakePipe) -> MpvPlayer:
    from itertools import count

    player = MpvPlayer.__new__(MpvPlayer)
    player._pipe = pipe
    player._buffer = b""
    player._request_ids = count(1)
    player._aliases = {}
    player._local_paths = set()
    player._local_songs = NO_LOCAL_SONGS
    player._repeat = RepeatMode.OFF
    player._executable = Path("mpv")
    player._volume = 60
    player._ytdl_path = None
    player._pipe_path = "pipe"
    return player


PAGE_URL = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
UNPAUSE = ["set_property", "pause", False]


def commands_of(pipe: FakePipe) -> list[list]:
    return [request["command"] for request in pipe.requests]


class PlayAllTest(unittest.TestCase):
    def test_sends_commands_in_batches_instead_of_one_round_trip_each(self) -> None:
        pipe = FakePipe()
        player_with(pipe).play_all([f"uri-{number}" for number in range(100)], start=3)
        commands = commands_of(pipe)
        self.assertEqual(commands[:2], [["stop"], ["set_property", "pause", False]])
        self.assertEqual(commands[2], ["loadfile", "uri-0", "append"])
        self.assertEqual(commands[-1], ["set_property", "playlist-pos", 3])
        self.assertEqual(len(commands), 103)
        self.assertEqual(pipe.writes, -(-103 // BATCH_SIZE))


class LoadTest(unittest.TestCase):
    def test_skips_to_new_song_when_something_is_playing(self) -> None:
        pipe = FakePipe(play_state_idle=False)
        player_with(pipe).load("song")
        self.assertEqual(commands_of(pipe)[1:], [UNPAUSE, ["loadfile", "song", "insert-next-play"], ["playlist-next"]])

    def test_only_inserts_when_idle(self) -> None:
        pipe = FakePipe(play_state_idle=True)
        player_with(pipe).load("song")
        self.assertEqual(commands_of(pipe)[1:], [UNPAUSE, ["loadfile", "song", "insert-next-play"]])


class AttachTest(unittest.TestCase):
    def test_replaces_the_entry_after_the_current_one(self) -> None:
        playlist = [{"filename": "a"}, {"filename": "b", "current": True}, {"filename": "c"}]
        pipe = FakePipe(properties={"playlist": playlist})
        player_with(pipe).attach_stream("c", ResolvedTrack("C", "page", "stream"))
        self.assertEqual(commands_of(pipe)[1:], [["loadfile", "stream", "insert-at", 2], ["playlist-remove", 3]])

    def test_replaces_an_entry_before_the_current_one_when_the_queue_wraps(self) -> None:
        playlist = [{"filename": "a"}, {"filename": "b", "current": True}]
        pipe = FakePipe(properties={"playlist": playlist})
        player_with(pipe).attach_stream("a", ResolvedTrack("A", "page", "stream"))
        self.assertEqual(commands_of(pipe)[1:], [["loadfile", "stream", "insert-at", 0], ["playlist-remove", 1]])


class QueueEditingTest(unittest.TestCase):
    def test_play_next_inserts_after_current(self) -> None:
        pipe = FakePipe()
        player_with(pipe).play_next("song")
        self.assertEqual(commands_of(pipe)[1:], [["loadfile", "song", "insert-next-play"]])

    def test_starting_from_idle_clears_a_stale_pause(self) -> None:
        pipe = FakePipe(play_state_idle=True)
        player_with(pipe).play_next("song")
        self.assertEqual(commands_of(pipe)[1:], [UNPAUSE, ["loadfile", "song", "insert-next-play"]])

    def test_toggle_pause_does_nothing_when_idle(self) -> None:
        idle, busy = FakePipe(play_state_idle=True), FakePipe(play_state_idle=False)
        player_with(idle).toggle_pause()
        player_with(busy).toggle_pause()
        self.assertEqual(commands_of(idle), [["get_property", "idle-active"]])
        self.assertEqual(commands_of(busy)[-1], ["cycle", "pause"])

    def test_play_at_unpauses(self) -> None:
        pipe = FakePipe()
        player_with(pipe).play_at(2)
        self.assertEqual(commands_of(pipe), [UNPAUSE, ["set_property", "playlist-pos", 2]])

    def test_remove_drops_entry_by_index(self) -> None:
        pipe = FakePipe()
        player_with(pipe).remove(4)
        self.assertEqual(commands_of(pipe), [["playlist-remove", 4]])

    def test_insert_puts_entry_back_at_index(self) -> None:
        pipe = FakePipe()
        player_with(pipe).insert("song", 2)
        self.assertEqual(commands_of(pipe), [["loadfile", "song", "insert-at", 2]])


class ObserveTest(unittest.TestCase):
    def test_reads_every_property_in_one_exchange(self) -> None:
        pipe = FakePipe()
        observation = player_with(pipe).observe()
        self.assertEqual(pipe.writes, 1)
        self.assertEqual(len(pipe.requests), 8)
        self.assertEqual(observation.queue, [])


class FakeLocalSongs:
    def __init__(self) -> None:
        self.songs = {PAGE_URL: LocalSong(r"C:\songs\x.webm", "Real Title")}

    def find(self, uri: str) -> LocalSong | None:
        return self.songs.get(uri)


class LocalSongsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pipe = FakePipe()
        self.player = player_with(self.pipe)
        self.player._local_songs = FakeLocalSongs()

    def test_every_entry_point_loads_the_local_file_instead_of_the_page(self) -> None:
        self.player.enqueue(PAGE_URL)
        self.player.play_next(PAGE_URL)
        self.player.insert(PAGE_URL, 1)
        self.player.play_all([PAGE_URL, "other"])
        loaded = [command[1] for command in commands_of(self.pipe) if command[0] == "loadfile"]
        self.assertEqual(loaded, [r"C:\songs\x.webm"] * 4 + ["other"])

    def test_alias_keeps_the_real_title_and_page_url(self) -> None:
        self.player.enqueue(PAGE_URL)
        self.assertEqual(self.player._aliases[r"C:\songs\x.webm"].title, "Real Title")
        self.assertEqual(self.player._aliases[r"C:\songs\x.webm"].uri, PAGE_URL)

    def test_uncached_uris_are_untouched(self) -> None:
        self.player.enqueue("ytdl://ytsearch:x")
        self.assertEqual(commands_of(self.pipe)[1:], [["loadfile", "ytdl://ytsearch:x", "append-play"]])
        self.assertEqual(self.player._aliases, {})


class RepeatTest(unittest.TestCase):
    def test_each_mode_sets_both_loop_properties(self) -> None:
        expected = {
            RepeatMode.OFF: ("no", "no"),
            RepeatMode.QUEUE: ("inf", "no"),
            RepeatMode.SONG: ("no", "inf"),
        }
        for mode, (loop_playlist, loop_file) in expected.items():
            pipe = FakePipe()
            player_with(pipe).set_repeat(mode)
            self.assertEqual(commands_of(pipe), [["set_property", "loop-playlist", loop_playlist], ["set_property", "loop-file", loop_file]])

    def test_the_last_mode_is_reapplied_when_mpv_starts_again(self) -> None:
        player = player_with(FakePipe())
        player.set_repeat(RepeatMode.SONG)
        self.assertIn("--loop-file=inf", player._arguments())
        self.assertIn("--loop-playlist=no", player._arguments())
        player.set_repeat(RepeatMode.QUEUE)
        self.assertIn("--loop-playlist=inf", player._arguments())
        self.assertIn("--loop-file=no", player._arguments())


class RelocateLocalTest(unittest.TestCase):
    OLD = r"C:\old\a.webm"
    NEW = r"D:\new\a.webm"

    def player(self, entries: list[dict]) -> tuple[MpvPlayer, FakePipe]:
        pipe = FakePipe(properties={"playlist": entries})
        player = player_with(pipe)
        player._aliases = {self.OLD: Track("A", PAGE_URL)}
        player._local_paths = {self.OLD}
        return player, pipe

    def test_moved_file_replaces_the_queued_entry_in_place(self) -> None:
        player, pipe = self.player([{"filename": "now", "current": True}, {"filename": self.OLD}])
        player.relocate_local({self.OLD: self.NEW})
        self.assertEqual(commands_of(pipe)[1:], [["loadfile", self.NEW, "insert-at", 1], ["playlist-remove", 2]])
        self.assertEqual(player._aliases, {self.NEW: Track("A", PAGE_URL)})
        self.assertEqual(player._local_paths, {self.NEW})

    def test_deleted_file_goes_back_to_the_page_url(self) -> None:
        player, pipe = self.player([{"filename": "now", "current": True}, {"filename": self.OLD}])
        player.relocate_local({self.OLD: None})
        self.assertEqual(commands_of(pipe)[1:], [["loadfile", PAGE_URL, "insert-at", 1], ["playlist-remove", 2]])
        self.assertEqual(player._aliases, {})

    def test_the_playing_entry_and_unrelated_entries_are_left_alone(self) -> None:
        player, pipe = self.player([{"filename": self.OLD, "current": True}, {"filename": "other"}])
        player.relocate_local({self.OLD: None})
        self.assertEqual(len(pipe.requests), 1)


class LocalFileTest(unittest.TestCase):
    def test_observation_exposes_the_local_file_being_played(self) -> None:
        local = r"C:\songs\x.webm"
        pipe = FakePipe(properties={"path": local})
        player = player_with(pipe)
        player._aliases = {local: Track("Real", PAGE_URL)}
        player._local_paths = {local}
        status = player.observe().status
        self.assertEqual((status.path, status.local_file), (PAGE_URL, local))


if __name__ == "__main__":
    unittest.main()
