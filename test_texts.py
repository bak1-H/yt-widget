import unittest

import texts

GB = 1024**3


class CacheUsageTest(unittest.TestCase):
    def test_uses_comma_decimals_and_drops_empty_decimals(self) -> None:
        self.assertEqual(texts.cache_usage(round(1.3 * GB), 2.0, 312), "1,3 GB de 2 GB · 312 canciones")
        self.assertEqual(texts.cache_usage(5 * GB, 10.0, 40), "5 GB de 10 GB · 40 canciones")

    def test_favorites_size_is_appended_only_when_there_are_favorites(self) -> None:
        self.assertEqual(texts.cache_usage(GB, 2.0, 3, round(1.2 * GB)), "1 GB de 2 GB · 3 canciones · 1,2 GB en Me gusta")
        self.assertEqual(texts.cache_usage(0, 2.0, 0, 300 * 1024**2), "0 MB de 2 GB · 0 canciones · 300 MB en Me gusta")
        self.assertEqual(texts.cache_usage(GB, 2.0, 3, 0), "1 GB de 2 GB · 3 canciones")

    def test_small_usage_is_shown_in_megabytes_and_singular_is_respected(self) -> None:
        self.assertEqual(texts.cache_usage(480 * 1024**2, 0.5, 1), "480 MB de 0,5 GB · 1 canción")
        self.assertEqual(texts.cache_usage(0, 2.0, 0), "0 MB de 2 GB · 0 canciones")

    def test_a_full_cache_is_the_normal_state_and_has_no_warning(self) -> None:
        self.assertEqual(texts.cache_usage(2 * GB, 2.0, 3), "2 GB de 2 GB · 3 canciones")

    def test_low_drive_space_is_spelled_out_so_color_is_not_the_only_signal(self) -> None:
        self.assertEqual(texts.drive_free(GB // 2, "P:", low_space=True), "Quedan 512 MB libres en P: · poco espacio en el disco")
        self.assertEqual(texts.drive_free(GB // 2, "P:"), "Quedan 512 MB libres en P:")

    def test_autoplay_explains_when_it_adds_songs_and_its_repeat_requirement(self) -> None:
        self.assertIn("una canción o menos", texts.AUTOPLAY_TOOLTIP)
        self.assertIn("Repetir: no", texts.AUTOPLAY_TOOLTIP)
        self.assertIn("Repetir: no", texts.AUTOPLAY_NEEDS_NO_REPEAT)

    def test_tooltip_and_free_space(self) -> None:
        self.assertEqual(texts.cache_usage_tooltip(round(1.3 * GB), 2.0, 65), "1,3 GB de 2 GB (65 %)")
        self.assertEqual(texts.drive_free(812 * GB, "P:"), "Quedan 812 GB libres en P:")
        self.assertEqual(texts.drive_free(1536 * GB, ""), "Quedan 1,5 TB libres")

    def test_limit_labels(self) -> None:
        self.assertEqual([texts.gigabytes(value) for value in (0.5, 1.0, 2.0, 5.0, 10.0)], ["0,5 GB", "1 GB", "2 GB", "5 GB", "10 GB"])


if __name__ == "__main__":
    unittest.main()
