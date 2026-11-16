import unittest

from media import SEARCH_PREFIX, UNKNOWN_TIME, display_name, format_time, is_resolvable, shorten, to_media_uri, video_id, video_id


class ShortenTest(unittest.TestCase):
    def test_keeps_short_text_and_truncates_long_text(self) -> None:
        self.assertEqual(shorten("short", 10), "short")
        self.assertEqual(shorten("a very long title", 8), "a very…")
        self.assertLessEqual(len(shorten("x" * 50, 10)), 10)


class IsResolvableTest(unittest.TestCase):
    def test_youtube_and_search_only(self) -> None:
        self.assertTrue(is_resolvable(f"{SEARCH_PREFIX}song"))
        self.assertTrue(is_resolvable("https://youtu.be/abc"))
        self.assertFalse(is_resolvable("https://rr5---sn.googlevideo.com/videoplayback"))


class VideoIdTest(unittest.TestCase):
    def test_extracts_from_supported_youtube_urls(self) -> None:
        expected = "dQw4w9WgXcQ"
        urls = (
            f"https://www.youtube.com/watch?v={expected}",
            f"https://youtube.com/watch?feature=share&v={expected}&list=PL123",
            f"https://music.youtube.com/watch?v={expected}&si=abc",
            f"https://m.youtube.com/watch?v={expected}",
            f"https://youtu.be/{expected}",
            f"https://youtu.be/{expected}?t=42",
        )
        for url in urls:
            self.assertEqual(video_id(url), expected, url)

    def test_rejects_everything_else(self) -> None:
        for url in (
            "",
            f"{SEARCH_PREFIX}daft punk",
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/watch",
            "https://example.com/watch?v=dQw4w9WgXcQ",
            "ftp://youtu.be/dQw4w9WgXcQ",
            "C:/songs/dQw4w9WgXcQ.webm",
        ):
            self.assertIsNone(video_id(url), url)


class VideoIdTest(unittest.TestCase):
    def test_extracts_from_supported_youtube_urls(self) -> None:
        expected = "dQw4w9WgXcQ"
        urls = (
            f"https://www.youtube.com/watch?v={expected}",
            f"https://youtube.com/watch?feature=share&v={expected}&list=PL123",
            f"https://music.youtube.com/watch?v={expected}&si=abc",
            f"https://m.youtube.com/watch?v={expected}",
            f"https://youtu.be/{expected}",
            f"https://youtu.be/{expected}?t=42",
        )
        for url in urls:
            self.assertEqual(video_id(url), expected, url)

    def test_rejects_everything_else(self) -> None:
        for url in (
            "",
            f"{SEARCH_PREFIX}daft punk",
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/watch",
            "https://example.com/watch?v=dQw4w9WgXcQ",
            "ftp://youtu.be/dQw4w9WgXcQ",
            "C:/songs/dQw4w9WgXcQ.webm",
        ):
            self.assertIsNone(video_id(url), url)


class DisplayNameTest(unittest.TestCase):
    def test_prefers_title(self) -> None:
        self.assertEqual(display_name("Song", "https://x"), "Song")

    def test_strips_search_prefixes(self) -> None:
        self.assertEqual(display_name(None, f"{SEARCH_PREFIX}daft punk"), "daft punk")
        self.assertEqual(display_name("ytsearch:daft punk", "x"), "daft punk")


class ToMediaUriTest(unittest.TestCase):
    def test_keeps_urls(self) -> None:
        url = "https://www.youtube.com/watch?v=abc"
        self.assertEqual(to_media_uri(f"  {url} "), url)

    def test_turns_text_into_search(self) -> None:
        self.assertEqual(to_media_uri("daft punk"), f"{SEARCH_PREFIX}daft punk")

    def test_rejects_blank_query(self) -> None:
        with self.assertRaises(ValueError):
            to_media_uri("   ")


class FormatTimeTest(unittest.TestCase):
    def test_unknown(self) -> None:
        self.assertEqual(format_time(None), UNKNOWN_TIME)

    def test_minutes(self) -> None:
        self.assertEqual(format_time(125.9), "02:05")

    def test_hours(self) -> None:
        self.assertEqual(format_time(3723), "1:02:03")


if __name__ == "__main__":
    unittest.main()
