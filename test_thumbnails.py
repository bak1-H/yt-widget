import os
import tempfile
import time
import unittest
from pathlib import Path

from thumbnails import (
    DISK_FOLDER_NAME,
    DiskThumbnails,
    LruCache,
    ThumbnailError,
    ThumbnailFeed,
    ThumbnailLoader,
    fetch_thumbnail,
    is_jpeg,
    thumbnail_url,
)

SONG = "K0HSD_i2DvA"
OTHER = "dQw4w9WgXcQ"
JPEG = b"\xff\xd8\xff\xe0data"


class FakeStore:
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def read(self, song_id: str) -> bytes | None:
        return self.saved.get(song_id)

    def write(self, song_id: str, data: bytes) -> None:
        self.saved[song_id] = data


def settle(loader: ThumbnailLoader, feed: ThumbnailFeed) -> None:
    deadline = time.monotonic() + 2
    while loader._pending and time.monotonic() < deadline:
        time.sleep(0.01)
        feed.deliver()


class ThumbnailUrlTest(unittest.TestCase):
    def test_builds_the_ytimg_url(self) -> None:
        self.assertEqual(thumbnail_url(SONG), f"https://i.ytimg.com/vi/{SONG}/mqdefault.jpg")

    def test_rejects_ids_that_are_not_video_ids(self) -> None:
        for value in ("", "short", "../../etc/passwd", f"{SONG}/../x", f"{SONG}?a=b", "a" * 12):
            with self.assertRaises(ThumbnailError):
                thumbnail_url(value)
            with self.assertRaises(ThumbnailError):
                fetch_thumbnail(value)

    def test_jpeg_check(self) -> None:
        self.assertTrue(is_jpeg(JPEG))
        self.assertFalse(is_jpeg(b"<html>"))
        self.assertFalse(is_jpeg(JPEG + b"x" * 200_000))


class LruCacheTest(unittest.TestCase):
    def test_evicts_least_recently_used(self) -> None:
        cache: LruCache[str, int] = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        cache.put("c", 3)
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertEqual(len(cache), 2)

    def test_missing_key_gives_none(self) -> None:
        self.assertIsNone(LruCache(1).get("x"))


class DiskThumbnailsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.folder: Path | None = Path(self.directory.name)
        self.disk = DiskThumbnails(lambda: self.folder, limit=3)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_path_lives_in_thumbnails_subfolder(self) -> None:
        self.assertEqual(self.disk.path_for(SONG), Path(self.directory.name) / DISK_FOLDER_NAME / f"{SONG}.jpg")

    def test_disabled_cache_never_touches_disk(self) -> None:
        self.folder = None
        self.assertIsNone(self.disk.path_for(SONG))
        self.disk.write(SONG, JPEG)
        self.assertIsNone(self.disk.read(SONG))
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_invalid_ids_have_no_path(self) -> None:
        self.assertIsNone(self.disk.path_for("../evil"))
        self.disk.write("../evil", JPEG)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_round_trip_and_corrupt_file_is_ignored(self) -> None:
        self.disk.write(SONG, JPEG)
        self.assertEqual(self.disk.read(SONG), JPEG)
        self.disk.path_for(SONG).write_bytes(b"garbage")
        self.assertIsNone(self.disk.read(SONG))

    def test_oldest_files_are_pruned_beyond_the_limit(self) -> None:
        ids = ["aaaaaaaaaa1", "aaaaaaaaaa2", "aaaaaaaaaa3", "aaaaaaaaaa4"]
        for index, song_id in enumerate(ids):
            self.disk.write(song_id, JPEG)
            path = self.disk.path_for(song_id)
            os.utime(path, (1000 + index, 1000 + index))
        self.disk.write("aaaaaaaaaa5", JPEG)
        remaining = sorted(path.stem for path in (Path(self.directory.name) / DISK_FOLDER_NAME).iterdir())
        self.assertEqual(len(remaining), 3)
        self.assertNotIn("aaaaaaaaaa1", remaining)
        self.assertIn("aaaaaaaaaa5", remaining)


class ThumbnailPruneSafetyTest(unittest.TestCase):
    def test_only_owned_jpg_files_in_the_app_folder_are_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            disk = DiskThumbnails(lambda: Path(directory), limit=1)
            folder = Path(directory) / DISK_FOLDER_NAME
            folder.mkdir()
            foreign = [folder / "holiday-photo.jpg", folder / "notes.txt", folder / f"{SONG}.png", folder / "short.jpg"]
            for file in foreign:
                file.write_bytes(b"mine")
                os.utime(file, (1, 1))
            old_folder = Path(directory) / "thumbnails"
            old_folder.mkdir()
            (old_folder / f"{OTHER}.jpg").write_bytes(JPEG)
            disk.write("aaaaaaaaaa1", JPEG)
            disk.write("aaaaaaaaaa2", JPEG)
            self.assertTrue(all(file.exists() for file in foreign))
            self.assertTrue((old_folder / f"{OTHER}.jpg").exists())
            self.assertEqual(sorted(path.name for path in folder.glob("aaaaaaaaaa*.jpg")), ["aaaaaaaaaa2.jpg"])

    def test_the_folder_name_is_hidden_and_app_specific(self) -> None:
        self.assertEqual(DISK_FOLDER_NAME, ".yt-widget-thumbnails")


class ThumbnailFeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fetched: list[str] = []
        self.shown: list[bytes | None] = []
        self.store = FakeStore()
        self.loader = ThumbnailLoader(self.fetch, self.store)
        self.feed: ThumbnailFeed[bytes] = ThumbnailFeed(self.loader, lambda data: data, self.shown.append, capacity=2)

    def tearDown(self) -> None:
        self.loader.close()

    def fetch(self, song_id: str) -> bytes:
        self.fetched.append(song_id)
        if song_id == "offline0000":
            raise ThumbnailError("offline")
        return JPEG + song_id.encode()

    def test_loads_once_and_shows_the_image(self) -> None:
        self.feed.select(SONG)
        self.feed.select(SONG)
        settle(self.loader, self.feed)
        self.assertEqual(self.fetched, [SONG])
        self.assertEqual(self.shown, [None, JPEG + SONG.encode()])
        self.assertEqual(self.store.saved[SONG], JPEG + SONG.encode())

    def test_stale_result_is_cached_but_not_shown(self) -> None:
        self.feed.select(SONG)
        self.feed.select(OTHER)
        settle(self.loader, self.feed)
        self.assertEqual(self.shown[-1], JPEG + OTHER.encode())
        self.assertNotIn(JPEG + SONG.encode(), self.shown)
        self.feed.select(SONG)
        self.assertEqual(self.shown[-1], JPEG + SONG.encode())
        self.assertEqual(self.fetched.count(SONG), 1)

    def test_failure_keeps_the_placeholder(self) -> None:
        self.feed.select("offline0000")
        settle(self.loader, self.feed)
        self.assertEqual(self.shown, [None])

    def test_undecodable_data_keeps_the_placeholder(self) -> None:
        def decode(_data: bytes) -> bytes:
            raise ThumbnailError("bad")

        feed: ThumbnailFeed[bytes] = ThumbnailFeed(self.loader, decode, self.shown.append)
        feed.select(SONG)
        settle(self.loader, feed)
        self.assertEqual(self.shown, [None])

    def test_no_id_shows_the_placeholder_without_requests(self) -> None:
        self.feed.select(SONG)
        self.feed.select(None)
        self.assertEqual(self.shown, [None, None])
        settle(self.loader, self.feed)
        self.assertEqual(self.shown, [None, None])

    def test_store_hit_skips_the_network(self) -> None:
        self.store.saved[SONG] = JPEG
        self.feed.select(SONG)
        settle(self.loader, self.feed)
        self.assertEqual(self.fetched, [])
        self.assertEqual(self.shown[-1], JPEG)


if __name__ == "__main__":
    unittest.main()
