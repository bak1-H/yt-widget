import ctypes
import unittest
from unittest import mock

import window_style
from settings import GlassStyle
from theme import FROST, GLASS
from window_style import AccentPolicy, accent_for, apply_glass

FAKE_HANDLE = 1234


def applied_policy(style: GlassStyle | None, tint: int) -> tuple[AccentPolicy, int]:
    captured: list[AccentPolicy] = []

    def capture(handle: int, data: object) -> int:
        payload = data._obj
        captured.append(ctypes.cast(payload.data, ctypes.POINTER(AccentPolicy)).contents)
        return 1

    with mock.patch.object(window_style, "_window_handle", return_value=FAKE_HANDLE):
        with mock.patch.object(ctypes.windll.user32, "SetWindowCompositionAttribute", side_effect=capture):
            result = apply_glass(mock.Mock(), tint, style)
    return captured[0], result


class AccentMappingTest(unittest.TestCase):
    def test_blur_uses_acrylic_and_clear_uses_the_transparent_gradient(self) -> None:
        self.assertEqual(accent_for(GlassStyle.BLUR), (window_style.ACCENT_ENABLE_ACRYLICBLURBEHIND, window_style.ACCENT_DRAW_ALL_BORDERS))
        self.assertEqual(accent_for(GlassStyle.CLEAR), (window_style.ACCENT_ENABLE_TRANSPARENTGRADIENT, window_style.ACCENT_DRAW_ALL_BORDERS))

    def test_glass_off_disables_the_accent(self) -> None:
        self.assertEqual(accent_for(None), (window_style.ACCENT_DISABLED, 0))

    def test_every_style_has_its_own_accent_state(self) -> None:
        states = {accent_for(style)[0] for style in GlassStyle}
        self.assertEqual(len(states), len(GlassStyle))
        self.assertNotIn(window_style.ACCENT_DISABLED, states)

    def test_blur_state_is_still_the_original_acrylic_value(self) -> None:
        self.assertEqual(accent_for(GlassStyle.BLUR)[0], 4)
        self.assertEqual(accent_for(GlassStyle.CLEAR)[0], 2)


class ApplyGlassTest(unittest.TestCase):
    def test_policy_carries_the_style_state_and_the_tint_unchanged(self) -> None:
        for style in GlassStyle:
            for opacity in (0, 35, 80, 100):
                with self.subTest(style=style.value, opacity=opacity):
                    tint = GLASS.glass_tint_abgr(opacity)
                    policy, result = applied_policy(style, tint)
                    self.assertEqual((policy.accent_state, policy.accent_flags), accent_for(style))
                    self.assertEqual(policy.gradient_color & 0xFFFFFFFF, tint)
                    self.assertTrue(result)

    def test_opacity_is_the_tint_alpha_in_both_styles(self) -> None:
        for style in GlassStyle:
            alphas = [applied_policy(style, FROST.glass_tint_abgr(opacity))[0].gradient_color >> 24 for opacity in (0, 50, 100)]
            self.assertEqual(alphas, [0, 128, 255])

    def test_disabled_glass_applies_the_disabled_accent(self) -> None:
        policy, _ = applied_policy(None, GLASS.glass_tint_abgr(80))
        self.assertEqual((policy.accent_state, policy.accent_flags), (window_style.ACCENT_DISABLED, 0))


if __name__ == "__main__":
    unittest.main()
