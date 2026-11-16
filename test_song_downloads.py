import tempfile
import time
import unittest
from pathlib import Path

from settings import CacheQuality
from song_cache import SongCache
from song_downloads import QUALITY_FORMATS, SongDownloads

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
        self.downloads = SongDownloads(self.cache, self.fake_download)

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

    def count_error(self) -> None:
        self.errors += 1

    def settle(self) -> None:
        deadline = time.monotonic() + 2
        while self.downloads._jobs and time.monotonic() < deadline:
            time.sleep(0.01)
            self.downloads.deliver(self.count_error)

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


if __name__ == "__main__":
    unittest.main()
