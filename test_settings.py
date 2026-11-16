import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from repeat import RepeatMode
from settings import MAX_PREFETCH, CacheQuality, CloseAction, GlassStyle, JsonSettingsStore, Settings, WindowPosition
from theme import ThemeName


class JsonSettingsStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "nested" / "settings.json"
        self.store = JsonSettingsStore(self.path)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_missing_file_gives_defaults(self) -> None:
        settings = self.store.load()
        self.assertEqual(settings, Settings())
        self.assertIs(settings.window_position, WindowPosition.TOPMOST)
        self.assertTrue(settings.glass)
        self.assertEqual(settings.startup_volume, 60)
        self.assertIs(settings.close_action, CloseAction.HIDE)
        self.assertEqual(settings.prefetch_count, 2)
        self.assertEqual(settings.glass_opacity, 80)
        self.assertFalse(settings.cache_enabled)
        self.assertIsNone(settings.cache_folder)
        self.assertEqual(settings.cache_limit_gb, 2.0)
        self.assertIs(settings.cache_quality, CacheQuality.MAX)
        self.assertIs(settings.repeat_mode, RepeatMode.OFF)
        self.assertFalse(settings.autoplay)
        self.assertTrue(settings.show_thumbnail)
        self.assertIs(settings.theme, ThemeName.GLASS)
        self.assertIs(settings.glass_style, GlassStyle.BLUR)

    def test_round_trip(self) -> None:
        changed = Settings(WindowPosition.DESKTOP, False, 25, CloseAction.QUIT, 0)
        self.store.save(changed)
        self.assertEqual(self.store.load(), changed)

    def test_cache_and_opacity_round_trip(self) -> None:
        changed = replace(Settings(), glass_opacity=35, cache_enabled=True, cache_folder="D:/Songs", cache_limit_gb=0.5, cache_quality=CacheQuality.MEDIUM)
        self.store.save(changed)
        self.assertEqual(self.store.load(), changed)

    def test_invalid_cache_fields_fall_back_and_opacity_is_clamped(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"glass_opacity": -5, "cache_enabled": 1, "cache_folder": "  ", "cache_limit_gb": 3, "cache_quality": "ultra"}',
            encoding="utf-8",
        )
        loaded = self.store.load()
        self.assertEqual(loaded, replace(Settings(), glass_opacity=0))
        self.path.write_text('{"glass_opacity": 500, "cache_limit_gb": 10}', encoding="utf-8")
        loaded = self.store.load()
        self.assertEqual((loaded.glass_opacity, loaded.cache_limit_gb), (100, 10.0))

    def test_repeat_mode_round_trips_and_unknown_values_fall_back(self) -> None:
        changed = replace(Settings(), repeat_mode=RepeatMode.SONG)
        self.store.save(changed)
        self.assertEqual(self.store.load(), changed)
        self.path.write_text('{"repeat_mode": "forever"}', encoding="utf-8")
        self.assertIs(self.store.load().repeat_mode, RepeatMode.OFF)

    def test_autoplay_round_trips_and_invalid_values_fall_back(self) -> None:
        changed = replace(Settings(), autoplay=True)
        self.store.save(changed)
        self.assertEqual(self.store.load(), changed)
        self.path.write_text('{"autoplay": "yes"}', encoding="utf-8")
        self.assertFalse(self.store.load().autoplay)

    def test_show_thumbnail_round_trips_and_invalid_values_fall_back(self) -> None:
        changed = replace(Settings(), show_thumbnail=False)
        self.store.save(changed)
        self.assertEqual(self.store.load(), changed)
        self.path.write_text('{"show_thumbnail": 0}', encoding="utf-8")
        self.assertTrue(self.store.load().show_thumbnail)

    def test_theme_round_trips_for_every_choice(self) -> None:
        for name in ThemeName:
            changed = replace(Settings(), theme=name)
            self.store.save(changed)
            self.assertEqual(self.store.load(), changed)

    def test_unknown_or_invalid_theme_falls_back_to_glass(self) -> None:
        self.path.parent.mkdir(parents=True)
        for raw in ('"neon"', "3", "null", "true"):
            self.path.write_text('{"theme": ' + raw + "}", encoding="utf-8")
            self.assertIs(self.store.load().theme, ThemeName.GLASS)

    def test_glass_style_round_trips_for_every_choice(self) -> None:
        for style in GlassStyle:
            changed = replace(Settings(), glass_style=style)
            self.store.save(changed)
            self.assertEqual(self.store.load(), changed)

    def test_unknown_or_invalid_glass_style_falls_back_to_blur(self) -> None:
        self.path.parent.mkdir(parents=True)
        for raw in ('"frosted"', "1", "null", "true"):
            self.path.write_text('{"glass_style": ' + raw + "}", encoding="utf-8")
            self.assertIs(self.store.load().glass_style, GlassStyle.BLUR)

    def test_settings_saved_before_glass_style_existed_load_as_blur(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"glass": false, "theme": "frost"}', encoding="utf-8")
        loaded = self.store.load()
        self.assertEqual((loaded.glass, loaded.theme, loaded.glass_style), (False, ThemeName.FROST, GlassStyle.BLUR))

    def test_corrupt_file_gives_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.store.load(), Settings())
        self.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.store.load(), Settings())

    def test_invalid_fields_fall_back_individually(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"window_position": "sideways", "glass": "yes", "startup_volume": 250, "close_action": "quit", "prefetch_count": true}',
            encoding="utf-8",
        )
        self.assertEqual(self.store.load(), replace(Settings(), startup_volume=100, close_action=CloseAction.QUIT))

    def test_numbers_are_clamped(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"startup_volume": -4, "prefetch_count": 99}', encoding="utf-8")
        loaded = self.store.load()
        self.assertEqual((loaded.startup_volume, loaded.prefetch_count), (0, MAX_PREFETCH))


if __name__ == "__main__":
    unittest.main()
