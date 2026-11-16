import json
import tempfile
import threading
import unittest
from pathlib import Path

from song_cache import INDEX_NAME, SongCache, configured_folder, default_folder, limit_bytes

FIRST = "aaaaaaaaaaa"
SECOND = "bbbbbbbbbbb"
THIRD = "ccccccccccc"


def url_of(song_id: str) -> str:
    return f"https://www.youtube.com/watch?v={song_id}"


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        self.now += 1
        return self.now


class SongCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name) / "songs"
        self.clock = Clock()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def cache(self, limit: int = 1000, enabled: bool = True) -> SongCache:
        return SongCache(self.folder, limit, enabled, self.clock)

    def song_file(self, song_id: str, size: int) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{song_id}.webm"
        path.write_bytes(b"x" * size)
        return path

    def test_add_find_and_usage(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 300), "First")
        found = cache.find(url_of(FIRST))
        self.assertEqual((found.path, found.title), (str(self.folder / f"{FIRST}.webm"), "First"))
        self.assertIsNone(cache.find(url_of(SECOND)))
        self.assertIsNone(cache.find("ytdl://ytsearch:first"))
        usage = cache.usage()
        self.assertEqual((usage.bytes_used, usage.songs), (300, 1))

    def test_find_is_off_when_disabled(self) -> None:
        cache = self.cache(enabled=False)
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        self.assertIsNone(cache.find(url_of(FIRST)))

    def test_index_survives_a_reload(self) -> None:
        self.cache().add(FIRST, self.song_file(FIRST, 300), "First")
        reloaded = self.cache()
        self.assertTrue(reloaded.contains(FIRST))
        self.assertEqual(reloaded.find(url_of(FIRST)).title, "First")

    def test_least_recently_played_is_evicted_first(self) -> None:
        cache = self.cache(limit=700)
        cache.add(FIRST, self.song_file(FIRST, 300), "First")
        cache.add(SECOND, self.song_file(SECOND, 300), "Second")
        cache.find(url_of(FIRST))
        cache.add(THIRD, self.song_file(THIRD, 300), "Third")
        self.assertTrue(cache.contains(FIRST))
        self.assertFalse(cache.contains(SECOND))
        self.assertTrue(cache.contains(THIRD))
        self.assertFalse((self.folder / f"{SECOND}.webm").exists())
        self.assertLessEqual(cache.usage().bytes_used, 700)

    def test_lowering_the_limit_evicts_immediately_and_persists(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 300), "First")
        cache.add(SECOND, self.song_file(SECOND, 300), "Second")
        cache.configure(True, self.folder, 400)
        self.assertEqual(cache.usage().songs, 1)
        self.assertFalse(self.cache(limit=400).contains(FIRST))

    def test_load_skips_bad_entries_and_drops_vanished_files(self) -> None:
        self.song_file(FIRST, 50)
        (self.folder / "stranger.mp3").write_bytes(b"unknown")
        raw = {
            "songs": {
                FIRST: {"file": f"{FIRST}.webm", "last_played": 5, "title": "First"},
                SECOND: {"file": f"{SECOND}.webm", "last_played": 5},
                THIRD: {"file": "../escape.webm"},
                "bad id": {"file": f"{FIRST}.webm"},
                "ddddddddddd": "not a dict",
                "eeeeeeeeeee": {"file": 7},
                "fffffffffff": {"file": INDEX_NAME},
            }
        }
        (self.folder / INDEX_NAME).write_text(json.dumps(raw), encoding="utf-8")
        cache = self.cache()
        self.assertEqual(cache.usage().songs, 1)
        self.assertEqual(cache.usage().bytes_used, 50)
        cache.clear()
        self.assertTrue((self.folder / "stranger.mp3").exists())

    def test_corrupt_or_missing_index_gives_empty_cache(self) -> None:
        self.assertEqual(self.cache().usage().songs, 0)
        self.folder.mkdir(parents=True)
        for content in ("{broken", "[]", '{"songs": []}'):
            (self.folder / INDEX_NAME).write_text(content, encoding="utf-8")
            self.assertEqual(self.cache().usage().songs, 0)

    def test_file_deleted_behind_our_back_is_forgotten_on_find(self) -> None:
        cache = self.cache()
        path = self.song_file(FIRST, 10)
        cache.add(FIRST, path, "First")
        path.unlink()
        self.assertIsNone(cache.find(url_of(FIRST)))
        self.assertFalse(cache.contains(FIRST))

    def test_clear_deletes_only_owned_files(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        (self.folder / "mine.txt").write_text("keep", encoding="utf-8")
        cache.clear()
        self.assertEqual(cache.usage().songs, 0)
        self.assertFalse((self.folder / f"{FIRST}.webm").exists())
        self.assertTrue((self.folder / "mine.txt").exists())
        self.assertEqual(self.cache().usage().songs, 0)

    def test_move_to_relocates_files_and_index(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        destination = Path(self.directory.name) / "elsewhere"
        cache.move_to(destination)
        self.assertEqual(cache.folder, destination)
        self.assertTrue((destination / f"{FIRST}.webm").exists())
        self.assertFalse((self.folder / f"{FIRST}.webm").exists())
        self.assertFalse((self.folder / INDEX_NAME).exists())
        self.assertTrue(SongCache(destination, 1000, True).contains(FIRST))

    def test_switching_folder_starts_empty_and_leaves_old_files(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.configure(True, Path(self.directory.name) / "fresh", 1000)
        self.assertEqual(cache.usage().songs, 0)
        self.assertTrue((self.folder / f"{FIRST}.webm").exists())

    def test_flush_persists_last_played_updates(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.find(url_of(FIRST))
        cache.flush()
        stored = json.loads((self.folder / INDEX_NAME).read_text(encoding="utf-8"))
        self.assertGreater(stored["songs"][FIRST]["last_played"], 101)

    def test_is_stored_follows_the_index_and_the_enabled_flag(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        self.assertTrue(cache.is_stored(url_of(FIRST)))
        self.assertFalse(cache.is_stored(url_of(SECOND)))
        self.assertFalse(cache.is_stored("ytdl://ytsearch:first"))
        cache.enabled = False
        self.assertFalse(cache.is_stored(url_of(FIRST)))

    def test_clear_keeps_the_playing_file_and_reports_it(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.add(SECOND, self.song_file(SECOND, 10), "Second")
        cache.playing_file = str(self.folder / f"{FIRST}.webm")
        report = cache.clear()
        self.assertTrue(report.kept_playing)
        self.assertTrue((self.folder / f"{FIRST}.webm").exists())
        self.assertTrue(cache.contains(FIRST))
        self.assertFalse(cache.contains(SECOND))
        self.assertEqual(cache.take_relocations(), {str(self.folder / f"{SECOND}.webm"): None})
        self.assertEqual(cache.take_relocations(), {})
        self.assertFalse(cache.busy)

    def test_add_is_rejected_while_a_cache_operation_runs_and_accepted_after(self) -> None:
        cache = self.cache()
        file = self.song_file(FIRST, 10)
        cache._busy = True
        self.assertFalse(cache.add(FIRST, file, "First"))
        self.assertFalse(cache.contains(FIRST))
        cache._busy = False
        self.assertTrue(cache.add(FIRST, file, "First"))
        self.assertTrue(cache.contains(FIRST))

    def test_move_skips_missing_files_instead_of_aborting(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        gone = self.song_file(SECOND, 10)
        cache.add(SECOND, gone, "Second")
        gone.unlink()
        destination = Path(self.directory.name) / "elsewhere"
        report = cache.move_to(destination)
        self.assertFalse(report.kept_playing)
        self.assertTrue(cache.contains(FIRST))
        self.assertFalse(cache.contains(SECOND))
        self.assertTrue((destination / f"{FIRST}.webm").exists())
        self.assertEqual(
            cache.take_relocations(),
            {str(self.folder / f"{FIRST}.webm"): str(destination / f"{FIRST}.webm"), str(gone): None},
        )

    def test_move_leaves_the_playing_file_behind_and_reports_it(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.add(SECOND, self.song_file(SECOND, 10), "Second")
        cache.playing_file = str(self.folder / f"{FIRST}.webm")
        destination = Path(self.directory.name) / "elsewhere"
        report = cache.move_to(destination)
        self.assertTrue(report.kept_playing)
        self.assertTrue((self.folder / f"{FIRST}.webm").exists())
        self.assertTrue(cache.contains(FIRST))
        self.assertEqual(cache.usage().songs, 2)
        self.assertTrue((destination / f"{SECOND}.webm").exists())

    def test_song_left_behind_while_playing_stays_tracked_and_clearable(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.playing_file = str(self.folder / f"{FIRST}.webm")
        destination = Path(self.directory.name) / "elsewhere"
        cache.move_to(destination)
        self.assertEqual(cache.find(url_of(FIRST)).path, str(self.folder / f"{FIRST}.webm"))
        reloaded = SongCache(destination, 1000, True)
        self.assertEqual(reloaded.usage().songs, 1)
        cache.playing_file = None
        cache.clear()
        self.assertFalse((self.folder / f"{FIRST}.webm").exists())
        self.assertEqual(cache.usage().songs, 0)

    def test_song_left_behind_while_playing_is_evictable(self) -> None:
        cache = self.cache(limit=100)
        cache.add(FIRST, self.song_file(FIRST, 60), "First")
        cache.playing_file = str(self.folder / f"{FIRST}.webm")
        destination = Path(self.directory.name) / "elsewhere"
        cache.move_to(destination)
        cache.playing_file = None
        destination.joinpath(f"{SECOND}.webm").write_bytes(b"x" * 60)
        cache.add(SECOND, destination / f"{SECOND}.webm", "Second")
        self.assertFalse(cache.contains(FIRST))
        self.assertFalse((self.folder / f"{FIRST}.webm").exists())

    def test_move_keeps_the_destination_copy_when_the_song_already_exists_there(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        cache.add(SECOND, self.song_file(SECOND, 10), "Second")
        destination = Path(self.directory.name) / "elsewhere"
        destination.mkdir()
        (destination / f"{FIRST}.webm").write_bytes(b"y" * 20)
        report = cache.move_to(destination)
        self.assertFalse(report.failed)
        self.assertEqual((destination / f"{FIRST}.webm").read_bytes(), b"y" * 20)
        self.assertFalse((self.folder / f"{FIRST}.webm").exists())
        self.assertTrue((destination / f"{SECOND}.webm").exists())
        self.assertEqual((cache.usage().songs, cache.usage().bytes_used), (2, 30))
        self.assertEqual(cache.take_relocations()[str(self.folder / f"{FIRST}.webm")], str(destination / f"{FIRST}.webm"))

    def test_cancelled_move_puts_everything_back(self) -> None:
        cache = self.cache()
        cache.add(FIRST, self.song_file(FIRST, 10), "First")
        stop = threading.Event()
        stop.set()
        with self.assertRaises(OSError):
            cache.move_to(Path(self.directory.name) / "elsewhere", stop)
        self.assertEqual(cache.folder, self.folder)
        self.assertTrue((self.folder / f"{FIRST}.webm").exists())
        self.assertFalse(cache.busy)

    def test_eviction_never_deletes_the_playing_file_and_reports_the_rest(self) -> None:
        cache = self.cache(limit=700)
        cache.add(FIRST, self.song_file(FIRST, 300), "First")
        cache.add(SECOND, self.song_file(SECOND, 300), "Second")
        cache.playing_file = str(self.folder / f"{FIRST}.webm")
        cache.take_relocations()
        cache.add(THIRD, self.song_file(THIRD, 300), "Third")
        self.assertTrue(cache.contains(FIRST))
        self.assertFalse(cache.contains(SECOND))
        self.assertEqual(cache.take_relocations(), {str(self.folder / f"{SECOND}.webm"): None})

    def test_loading_adopts_valid_orphans_and_removes_partials(self) -> None:
        self.cache().add(FIRST, self.song_file(FIRST, 10), "First")
        orphan = self.song_file(SECOND, 25)
        partial = self.folder / f"{THIRD}.webm.part"
        partial.write_bytes(b"half")
        stranger = self.folder / "notes.txt"
        stranger.write_text("keep", encoding="utf-8")
        wrong_extension = self.folder / f"{THIRD}.txt"
        wrong_extension.write_text("keep", encoding="utf-8")
        reloaded = self.cache()
        self.assertTrue(reloaded.contains(SECOND))
        self.assertEqual(reloaded.usage().bytes_used, 35)
        self.assertTrue(orphan.exists())
        self.assertFalse(partial.exists())
        self.assertTrue(stranger.exists())
        self.assertTrue(wrong_extension.exists())
        reloaded.flush()
        self.assertTrue(self.cache().contains(SECOND))

    def test_folders_without_an_index_are_never_swept(self) -> None:
        orphan = self.song_file(FIRST, 10)
        partial = self.folder / f"{SECOND}.webm.part"
        partial.write_bytes(b"x")
        cache = self.cache()
        self.assertEqual(cache.usage().songs, 0)
        self.assertTrue(orphan.exists())
        self.assertTrue(partial.exists())


class FolderTest(unittest.TestCase):
    def test_default_folder_prefers_project_drive_then_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            drive = Path(directory)
            self.assertEqual(default_folder(drive), drive / "YT Widget" / "Canciones")
            missing = drive / "no-such-drive"
            self.assertEqual(default_folder(missing, drive / "local"), drive / "local" / "YT Widget" / "Canciones")

    def test_configured_folder_and_limit(self) -> None:
        self.assertEqual(configured_folder("D:/Songs"), Path("D:/Songs"))
        self.assertEqual(limit_bytes(0.5), 512 * 1024**2)
        self.assertEqual(limit_bytes(2), 2 * 1024**3)


if __name__ == "__main__":
    unittest.main()
