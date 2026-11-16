import tempfile
import unittest
from pathlib import Path

from playlists import MAX_NAME_LENGTH, JsonPlaylistStore, PlaylistExistsError, PlaylistLibrary, PlaylistNameError, Playlists
from track import Track

SONG = Track("Song", "uri-1")
OTHER = Track("Other", "uri-2")


class MemoryStore:
    def __init__(self) -> None:
        self.saved: Playlists = {}
        self.load_warning: str | None = None
        self.failing = False

    def load(self) -> Playlists:
        return {}

    def save(self, playlists: Playlists) -> None:
        if self.failing:
            raise OSError("disk full")
        self.saved = {name: list(tracks) for name, tracks in playlists.items()}


class PlaylistLibraryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryStore()
        self.library = PlaylistLibrary(self.store)

    def test_create_trims_name(self) -> None:
        self.assertEqual(self.library.create("  Gym  "), "Gym")
        self.assertEqual(self.library.names(), ["Gym"])

    def test_rejects_blank_and_too_long_names(self) -> None:
        for name in ("   ", "x" * (MAX_NAME_LENGTH + 1)):
            with self.assertRaises(PlaylistNameError):
                self.library.create(name)
        self.assertEqual(self.library.create("x" * MAX_NAME_LENGTH), "x" * MAX_NAME_LENGTH)

    def test_rejects_existing_name_ignoring_case(self) -> None:
        self.library.create("Gym")
        with self.assertRaises(PlaylistExistsError) as raised:
            self.library.create("gYM")
        self.assertEqual(raised.exception.existing, "Gym")

    def test_names_sorted_case_insensitive(self) -> None:
        for name in ("study", "Gym", "chill"):
            self.library.create(name)
        self.assertEqual(self.library.names(), ["chill", "Gym", "study"])

    def test_add_remove_delete_persist(self) -> None:
        self.library.create("Gym")
        self.library.add("Gym", SONG)
        self.library.add("Gym", OTHER)
        self.library.remove("Gym", 0)
        self.assertEqual(self.store.saved, {"Gym": [OTHER]})
        self.library.delete("Gym")
        self.assertEqual(self.store.saved, {})

    def test_restore_brings_back_name_and_tracks(self) -> None:
        self.library.create("Gym")
        self.library.add("Gym", SONG)
        tracks = self.library.tracks("Gym")
        self.library.delete("Gym")
        self.library.restore("Gym", tracks)
        self.assertEqual(self.store.saved, {"Gym": [SONG]})

    def test_restore_refuses_taken_name(self) -> None:
        self.library.create("Gym")
        with self.assertRaises(PlaylistExistsError):
            self.library.restore("gym", (SONG,))

    def test_insert_puts_track_back_at_index(self) -> None:
        self.library.create("Gym")
        self.library.add("Gym", SONG)
        self.library.add("Gym", OTHER)
        self.library.remove("Gym", 0)
        self.library.insert("Gym", 0, SONG)
        self.assertEqual(self.library.tracks("Gym"), (SONG, OTHER))

    def test_membership_helpers_match_by_uri(self) -> None:
        for name in ("Gym", "Study"):
            self.library.create(name)
        self.library.add("Gym", OTHER)
        self.library.add("Gym", SONG)
        self.library.add("Study", Track("Renamed", SONG.uri))
        self.assertEqual(self.library.index_of("Gym", SONG.uri), 1)
        self.assertIsNone(self.library.index_of("Study", OTHER.uri))
        self.assertIsNone(self.library.index_of("Missing", SONG.uri))
        self.assertTrue(self.library.contains("Gym", OTHER.uri))
        self.assertEqual(self.library.names_containing(SONG.uri), ["Gym", "Study"])
        self.assertEqual(self.library.names_containing(OTHER.uri), ["Gym"])

    def test_name_errors_are_in_spanish(self) -> None:
        with self.assertRaises(PlaylistNameError) as raised:
            self.library.create(" ")
        self.assertEqual(str(raised.exception), "Escribe un nombre primero")

    def test_replace_updates_every_playlist(self) -> None:
        for name in ("A", "B"):
            self.library.create(name)
            self.library.add(name, SONG)
        resolved = Track("Real title", "https://youtube.com/watch?v=1")
        self.library.replace(SONG.uri, resolved)
        self.assertEqual(self.store.saved, {"A": [resolved], "B": [resolved]})

    def test_failed_save_rolls_back_every_change(self) -> None:
        self.library.create("Gym")
        self.library.add("Gym", SONG)
        self.store.failing = True
        attempts = (
            lambda: self.library.create("Study"),
            lambda: self.library.add("Gym", OTHER),
            lambda: self.library.remove("Gym", 0),
            lambda: self.library.delete("Gym"),
            lambda: self.library.replace(SONG.uri, OTHER),
            lambda: self.library.insert("Gym", 0, OTHER),
        )
        for attempt in attempts:
            with self.assertRaises(OSError):
                attempt()
        self.assertEqual(self.library.names(), ["Gym"])
        self.assertEqual(self.library.tracks("Gym"), (SONG,))


class JsonPlaylistStoreTest(unittest.TestCase):
    def test_round_trip_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playlists.json"
            store = JsonPlaylistStore(path)
            self.assertEqual(store.load(), {})
            self.assertIsNone(store.load_warning)
            store.save({"Gym": [SONG]})
            self.assertEqual(JsonPlaylistStore(path).load(), {"Gym": [SONG]})

    def test_corrupt_file_is_backed_up_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playlists.json"
            path.write_text("{broken", encoding="utf-8")
            store = JsonPlaylistStore(path)
            self.assertEqual(store.load(), {})
            self.assertIsNotNone(store.load_warning)
            self.assertEqual(Path(directory, "playlists.json.bak").read_text(encoding="utf-8"), "{broken")

    def test_wrong_top_level_type_is_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playlists.json"
            path.write_text("[1, 2]", encoding="utf-8")
            store = JsonPlaylistStore(path)
            self.assertEqual(store.load(), {})
            self.assertTrue(Path(directory, "playlists.json.bak").exists())

    def test_malformed_entries_are_skipped_individually(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playlists.json"
            path.write_text(
                '{"Good": [{"title": "Song", "uri": "uri-1"}, {"oops": 1}, 5], "Bad": 7, "Fine": []}',
                encoding="utf-8",
            )
            store = JsonPlaylistStore(path)
            self.assertEqual(store.load(), {"Good": [SONG], "Fine": []})
            self.assertIsNotNone(store.load_warning)
            self.assertTrue(Path(directory, "playlists.json.bak").exists())


if __name__ == "__main__":
    unittest.main()
