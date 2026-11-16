import tkinter as tk
import unittest

import theme
from theme import FROST, GLASS, NIGHT, THEMES, VINYL, Theme, ThemeName

MIN_TEXT_CONTRAST = 4.5
MIN_GRAPHIC_CONTRAST = 3.0
TEXT_PAIRS = (
    ("foreground", "background"),
    ("foreground", "surface"),
    ("foreground", "surface_hover"),
    ("muted", "background"),
    ("muted", "surface"),
    ("muted", "surface_hover"),
    ("muted", "tab_track"),
    ("accent", "background"),
    ("accent", "surface"),
    ("accent", "surface_hover"),
    ("accent", "tab_track"),
    ("danger", "background"),
    ("danger", "surface"),
    ("danger", "surface_hover"),
    ("on_accent", "accent"),
    ("on_accent", "accent_hover"),
    ("downloaded", "background"),
    ("downloaded", "surface"),
    ("downloaded", "surface_hover"),
)
GRAPHIC_PAIRS = (
    ("accent", "background"),
    ("accent", "surface"),
    ("accent", "surface_hover"),
    ("accent", "tab_track"),
    ("bar_fill", "slider_track"),
    ("bar_fill", "meter_track"),
    ("bar_alert", "meter_track"),
    ("foreground", "slider_track"),
    ("slider_track", "background"),
    ("slider_track", "surface"),
    ("meter_track", "background"),
    ("meter_track", "surface"),
    ("muted", "background"),
)


def channel(value: int) -> float:
    ratio = value / 255
    return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    red, green, blue = (channel(int(color[index : index + 2], 16)) for index in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def text_pairs(palette: Theme) -> list[tuple[str, str, str, str]]:
    pairs = [(foreground, background, getattr(palette, foreground), getattr(palette, background)) for foreground, background in TEXT_PAIRS]
    if palette.downloaded_background:
        pairs.append(("downloaded", "downloaded_background", palette.downloaded, palette.downloaded_background))
    return pairs


class ThemeRegistryTest(unittest.TestCase):
    def test_every_name_has_one_theme_with_its_own_name(self) -> None:
        self.assertEqual(set(THEMES), set(ThemeName))
        for name, palette in THEMES.items():
            self.assertIs(palette.name, name)

    def test_lookup_accepts_names_and_stored_values(self) -> None:
        self.assertIs(theme.theme_for(ThemeName.VINYL), VINYL)
        self.assertIs(theme.theme_for("frost"), FROST)

    def test_unknown_lookup_falls_back_to_glass(self) -> None:
        self.assertIs(theme.theme_for("neon"), GLASS)
        self.assertIs(theme.theme_for(""), GLASS)

    def test_glass_keeps_the_original_look(self) -> None:
        self.assertEqual(
            (GLASS.background, GLASS.surface, GLASS.surface_hover, GLASS.border, GLASS.foreground, GLASS.muted, GLASS.accent, GLASS.accent_hover, GLASS.danger),
            ("#181825", "#262637", "#363650", "#313244", "#cdd6f4", "#a6adc8", "#89b4fa", "#b4d0fb", "#f38ba8"),
        )
        self.assertEqual(GLASS.on_accent, GLASS.background)
        self.assertEqual(GLASS.row_gap, 0)

    def test_row_styles_resolve_gap_and_colors(self) -> None:
        self.assertEqual((NIGHT.row_gap, NIGHT.row_gap_color), (2, NIGHT.background))
        self.assertEqual((VINYL.row_gap, VINYL.row_gap_color), (1, VINYL.separator))
        self.assertEqual((FROST.row_gap, FROST.row_gap_color, FROST.row_area_color), (1, "#e3e8f2", "#ffffff"))

    def test_marker_background_only_applies_to_downloaded_rows(self) -> None:
        self.assertEqual(FROST.marker_background("#ffffff", True), "#dff3e4")
        self.assertEqual(FROST.marker_background("#ffffff", False), "#ffffff")
        self.assertEqual(NIGHT.marker_background("#262637", True), "#262637")


class ContrastTest(unittest.TestCase):
    def test_every_text_pair_reaches_the_text_minimum(self) -> None:
        for palette in THEMES.values():
            for foreground, background, front, back in text_pairs(palette):
                with self.subTest(theme=palette.name.value, pair=f"{foreground}/{background}"):
                    self.assertGreaterEqual(contrast_ratio(front, back), MIN_TEXT_CONTRAST)

    def test_every_graphic_pair_reaches_the_graphic_minimum(self) -> None:
        for palette in THEMES.values():
            for first, second in GRAPHIC_PAIRS:
                with self.subTest(theme=palette.name.value, pair=f"{first}/{second}"):
                    self.assertGreaterEqual(contrast_ratio(getattr(palette, first), getattr(palette, second)), MIN_GRAPHIC_CONTRAST)


class GlassTintTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.reset()

    def test_default_opacity_matches_the_original_tint(self) -> None:
        self.assertEqual(GLASS.glass_tint_abgr(80), 0xCC251818)
        self.assertEqual(theme.glass_tint(80), 0xCC251818)

    def test_replaces_only_the_alpha_byte(self) -> None:
        for opacity, alpha in ((0, 0), (20, 51), (50, 128), (100, 255)):
            tint = GLASS.glass_tint_abgr(opacity)
            self.assertEqual(tint >> 24, alpha)
            self.assertEqual(tint & 0x00FFFFFF, 0x00251818)

    def test_color_bytes_follow_the_theme_tint_in_abgr_order(self) -> None:
        self.assertEqual(VINYL.glass_tint_abgr(100) & 0x00FFFFFF, 0x0014181D)
        self.assertEqual(NIGHT.glass_tint_abgr(100) & 0x00FFFFFF, 0x00251818)
        self.assertEqual(FROST.glass_tint_abgr(100), 0xFF000000)

    def test_module_tint_follows_the_selected_theme(self) -> None:
        theme.select(ThemeName.VINYL)
        self.assertEqual(theme.glass_tint(100), VINYL.glass_tint_abgr(100))


class LiveRestyleTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available")
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()
        theme.reset()

    def test_bound_widgets_follow_the_selected_theme(self) -> None:
        label = tk.Label(self.root)
        theme.bind(label, bg="surface", fg="muted")
        self.assertEqual(label.cget("bg"), GLASS.surface)
        theme.select(ThemeName.FROST)
        self.assertEqual((label.cget("bg"), label.cget("fg")), (FROST.surface, FROST.muted))

    def test_rebinding_an_option_replaces_its_role(self) -> None:
        label = tk.Label(self.root)
        theme.bind(label, fg="muted")
        theme.bind(label, fg="danger")
        theme.select(ThemeName.NIGHT)
        self.assertEqual(label.cget("fg"), NIGHT.danger)

    def test_observers_are_called_with_the_new_theme(self) -> None:
        seen: list[Theme] = []

        class Probe(tk.Frame):
            def apply_theme(self, palette: Theme) -> None:
                seen.append(palette)

        probe = Probe(self.root)
        theme.observe(probe)
        theme.select(ThemeName.VINYL)
        self.assertEqual(seen, [VINYL])

    def test_destroyed_widgets_are_skipped(self) -> None:
        label = tk.Label(self.root)
        theme.bind(label, bg="surface")
        label.destroy()
        theme.select(ThemeName.NIGHT)

    def test_parent_role_is_known_to_children(self) -> None:
        frame = tk.Frame(self.root)
        theme.bind(frame, bg="background")
        self.assertEqual(theme.role_of(frame), "background")


if __name__ == "__main__":
    unittest.main()
