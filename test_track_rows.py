import unittest

from track_rows import locate
from window_style import rects_intersect


class LocateTest(unittest.TestCase):
    def test_same_row_wins_when_the_song_is_still_there(self) -> None:
        self.assertEqual(locate(["a", "b", "c"], 1, "b"), 1)

    def test_follows_the_song_when_rows_shifted(self) -> None:
        self.assertEqual(locate(["x", "a", "b"], 1, "b"), 2)

    def test_prefers_the_closest_duplicate(self) -> None:
        self.assertEqual(locate(["a", "b", "a", "c", "a"], 3, "a"), 2)

    def test_missing_song_is_not_found(self) -> None:
        self.assertIsNone(locate(["a"], 0, "gone"))
        self.assertIsNone(locate([], 5, "a"))


class RectsIntersectTest(unittest.TestCase):
    def test_overlap_and_touching_edges(self) -> None:
        self.assertTrue(rects_intersect((0, 0, 10, 10), (5, 5, 15, 15)))
        self.assertFalse(rects_intersect((0, 0, 10, 10), (10, 0, 20, 10)))
        self.assertFalse(rects_intersect((0, 0, 10, 10), (0, 20, 10, 30)))


if __name__ == "__main__":
    unittest.main()
