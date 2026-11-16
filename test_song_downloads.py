import tempfile
import time
import unittest
from pathlib import Path

from settings import CacheQuality
from song_cache import SongCache
from song_downloads import QUALITY_FORMATS, SongDownloads
from storage import DriveSpace

SONG_ID = "aaaaaaaaaaa"
OTHER_ID = "bbbbbbbbbbb"


def url_of(song_id: str) -> str:
    return f"https://www.youtube.com/watch?v={song_id}"


class SongDownloadsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.cache = SongCache(self.folder, 10_000, True)
        self.calls: list[tuple[str, CacheQuality]] = []
        self.fail = False
        self.errors = 0
        self.low_space_errors = 0
        self.free_bytes = 10**12
        self.downloads = SongDownloads(self.cache, self.fake_download, self.measure_space)

    def tearDown(self) -> None:
        self.downloads.close()
        self.directory.cleanup()

    def fake_download(self, page_url: str, folder: Path, quality: CacheQuality) -> Path:
        self.calls.append((page_url, quality))
        if self.fail:
            raise RuntimeError("boom")
        file = folder / f"{page_url[-11:]}.webm"
        file.write_bytes(b"x" * 20)
        return file

    def measure_space(self, folder: Path) -> DriveSpace:
        return DriveSpace(self.free_bytes, 10**12, "P:")

    def count_error(self) -> None:
        self.errors += 1

    def count_low_space(self) -> None:
        self.low_space_errors += 1

    def settle(self, downloads: SongDownloads | None = None, *callbacks) -> None:
        target = downloads or self.downloads
        deadline = time.monotonic() + 2
        while target._jobs and time.monotonic() < deadline:
            time.sleep(0.01)
            target.deliver(*(callbacks or (self.count_error, self.count_low_space)))

    def test_downloads_once_and_indexes_the_result(self) -> None:
        self.downloads.request(url_of(SONG_ID), "Song")
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.assertEqual(self.calls, [(url_of(SONG_ID), CacheQuality.MAX)])
        self.assertEqual(self.cache.find(url_of(SONG_ID)).title, "Song")

    def test_skips_when_disabled_or_not_a_youtube_page(self) -> None:
        self.downloads.request("ytdl://ytsearch:daft punk", "Search")
        self.cache.enabled = False
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.assertEqual(self.calls, [])

    def test_uses_the_configured_quality(self) -> None:
        self.downloads.quality = CacheQuality.MEDIUM
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.assertEqual(self.calls[0][1], CacheQuality.MEDIUM)
        self.assertIn("abr<=96", QUALITY_FORMATS[CacheQuality.MEDIUM])
        self.assertTrue(QUALITY_FORMATS[CacheQuality.MAX].startswith("251/"))

    def test_failures_report_one_error_until_a_success(self) -> None:
        self.fail = True
        self.downloads.request(url_of(SONG_ID), "Song")
        self.downloads.request(url_of(OTHER_ID), "Other")
        self.settle()
        self.assertEqual(self.errors, 1)
        self.assertEqual(self.cache.usage().songs, 0)

    def test_a_cache_operation_in_progress_discards_the_finished_file(self) -> None:
        self.downloads.request(url_of(SONG_ID), "Song")
        self.cache._busy = True
        self.settle()
        self.cache._busy = False
        self.assertEqual(self.cache.usage().songs, 0)
        self.assertFalse((self.folder / f"{SONG_ID}.webm").exists())

    def test_disabling_mid_download_discards_the_file(self) -> None:
        self.downloads.request(url_of(SONG_ID), "Song")
        self.cache.enabled = False
        self.settle()
        self.assertEqual(self.cache.usage().songs, 0)
        self.assertFalse((self.folder / f"{SONG_ID}.webm").exists())

    def fake_download_into_folder(self, page_url: str, folder: Path, quality: CacheQuality) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        return self.fake_download(page_url, folder, quality)

    def test_favorites_download_with_the_cache_off_into_the_configured_folder(self) -> None:
        folder = self.folder / "not-created-yet"
        cache = SongCache(folder, 10_000, False)
        downloads = SongDownloads(cache, self.fake_download_into_folder, self.measure_space)
        self.addCleanup(downloads.close)
        cache.set_favorites({SONG_ID})
        downloads.request(url_of(SONG_ID), "Song")
        downloads.request(url_of(OTHER_ID), "Other")
        self.settle(downloads)
        self.assertEqual([call[0] for call in self.calls], [url_of(SONG_ID)])
        self.assertEqual(cache.find(url_of(SONG_ID)).title, "Song")
        self.assertTrue((folder / f"{SONG_ID}.webm").exists())
        self.assertTrue((folder / "index.json").exists())
        self.assertIsNone(cache.find(url_of(OTHER_ID)))

    def test_a_favorite_that_cannot_fit_reports_low_space_once_and_downloads_nothing(self) -> None:
        self.free_bytes = 100
        self.cache.set_favorites({SONG_ID, OTHER_ID})
        self.downloads.request(url_of(SONG_ID), "Song")
        self.downloads.request(url_of(OTHER_ID), "Other")
        self.settle()
        self.assertEqual((self.low_space_errors, self.errors), (1, 0))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.cache.usage().favorite_bytes, 0)

    def test_regular_songs_are_not_blocked_by_the_space_guard(self) -> None:
        self.free_bytes = 100
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.low_space_errors, 0)

    def test_low_space_falls_back_to_the_generic_error_without_a_dedicated_callback(self) -> None:
        self.free_bytes = 100
        self.cache.set_favorites({SONG_ID})
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle(self.downloads, self.count_error)
        self.assertEqual(self.errors, 1)

    def test_a_released_favorite_is_no_longer_downloaded_while_the_cache_is_off(self) -> None:
        self.cache.enabled = False
        self.cache.set_favorites({SONG_ID})
        self.cache.set_favorites(set())
        self.downloads.request(url_of(SONG_ID), "Song")
        self.settle()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
