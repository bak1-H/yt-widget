import unittest

from media import fit_text
from undo import UndoSlot


class UndoSlotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [0.0]
        self.slot = UndoSlot(clock=lambda: self.now[0], window=30.0)

    def test_action_is_available_until_the_window_ends(self) -> None:
        self.slot.keep(lambda: None)
        self.now[0] = 29.0
        self.assertTrue(self.slot.available())
        self.now[0] = 30.5
        self.assertFalse(self.slot.available())
        self.assertIsNone(self.slot.take())

    def test_take_consumes_the_action(self) -> None:
        calls: list[int] = []
        self.slot.keep(lambda: calls.append(1))
        action = self.slot.take()
        self.assertIsNotNone(action)
        self.assertIsNone(self.slot.take())

    def test_a_newer_action_replaces_the_older_one_and_restarts_the_window(self) -> None:
        self.slot.keep(lambda: None)
        self.now[0] = 20.0
        newer = lambda: None
        self.slot.keep(newer)
        self.now[0] = 40.0
        self.assertIs(self.slot.take(), newer)

    def test_discard_drops_the_action(self) -> None:
        self.slot.keep(lambda: None)
        self.slot.discard()
        self.assertFalse(self.slot.available())
        self.assertIsNone(self.slot.take())

    def test_remaining_time(self) -> None:
        self.assertEqual(self.slot.remaining(), 0.0)
        self.slot.keep(lambda: None)
        self.now[0] = 10.0
        self.assertEqual(self.slot.remaining(), 20.0)


class FitTextTest(unittest.TestCase):
    def test_short_text_is_untouched(self) -> None:
        self.assertEqual(fit_text("hola", 10, len), "hola")

    def test_long_text_is_cut_with_an_ellipsis_within_the_limit(self) -> None:
        fitted = fit_text("una frase bastante larga", 10, len)
        self.assertTrue(fitted.endswith("…"))
        self.assertLessEqual(len(fitted), 10)

    def test_tiny_limit_still_returns_something_valid(self) -> None:
        self.assertEqual(fit_text("abc", 0, len), "…")


if __name__ == "__main__":
    unittest.main()
