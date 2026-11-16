import unittest

import theme
from theme import FROST, GLASS, ThemeName
from tray import TrayIcon, draw_icon

SAMPLE_POINT = (4, 32)


def noop(*_: object) -> None:
    return None


class TrayIconTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.reset()

    def test_icon_uses_the_palette_accent_and_background(self) -> None:
        for palette in (GLASS, FROST):
            image = draw_icon(palette)
            self.assertEqual(image.getpixel(SAMPLE_POINT)[:3], tuple(int(palette.accent[index : index + 2], 16) for index in (1, 3, 5)))
            self.assertEqual(image.getpixel((30, 32))[:3], tuple(int(palette.background[index : index + 2], 16) for index in (1, 3, 5)))

    def test_the_tray_icon_follows_live_theme_switches(self) -> None:
        tray = TrayIcon(on_toggle=noop, on_play_pause=noop, on_next=noop, on_quit=noop, schedule=noop)
        theme.select(ThemeName.FROST)
        self.assertEqual(tray._icon.icon.getpixel(SAMPLE_POINT)[:3], (0x3B, 0x5B, 0xDB))
        theme.select(ThemeName.GLASS)
        self.assertEqual(tray._icon.icon.getpixel(SAMPLE_POINT)[:3], (0x89, 0xB4, 0xFA))


if __name__ == "__main__":
    unittest.main()
