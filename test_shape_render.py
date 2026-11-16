import unittest

from shape_render import SUPERSAMPLE, RoundSpec, round_image

CIRCLE = RoundSpec(40, 40, (2, 2, 38, 38), fill="#89b4fa")


class RoundImageTest(unittest.TestCase):
    def test_image_has_the_requested_size_not_the_supersampled_one(self) -> None:
        self.assertEqual(round_image(CIRCLE).size, (40, 40))
        self.assertGreater(SUPERSAMPLE, 1)

    def test_equal_specs_share_one_cached_image_and_any_state_change_renders_another(self) -> None:
        same = RoundSpec(40, 40, (2, 2, 38, 38), fill="#89b4fa")
        hovered = RoundSpec(40, 40, (2, 2, 38, 38), fill="#b4d0fb")
        focused = RoundSpec(40, 40, (2, 2, 38, 38), fill="#89b4fa", ring="#ffffff", ring_width=2)
        self.assertIs(round_image(CIRCLE), round_image(same))
        self.assertIsNot(round_image(CIRCLE), round_image(hovered))
        self.assertIsNot(round_image(CIRCLE), round_image(focused))

    def test_corners_are_transparent_and_the_center_has_the_fill(self) -> None:
        image = round_image(CIRCLE)
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertEqual(image.getpixel((20, 20)), (0x89, 0xB4, 0xFA, 255))

    def test_edges_are_anti_aliased(self) -> None:
        image = round_image(RoundSpec(40, 40, (2, 2, 38, 38), fill="#ffffff"))
        alphas = {image.getpixel((x, y))[3] for x in range(40) for y in range(40)}
        self.assertTrue(any(0 < alpha < 255 for alpha in alphas))

    def test_a_pill_is_wider_than_tall_with_round_ends(self) -> None:
        pill = round_image(RoundSpec(100, 30, (0, 0, 100, 30), fill="#ffffff"))
        self.assertEqual(pill.size, (100, 30))
        self.assertEqual(pill.getpixel((0, 0))[3], 0)
        self.assertEqual(pill.getpixel((50, 15))[3], 255)


if __name__ == "__main__":
    unittest.main()
