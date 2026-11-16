import unittest

from repeat import RepeatMode, next_repeat


class RepeatCycleTest(unittest.TestCase):
    def test_cycles_off_queue_song_and_back(self) -> None:
        self.assertIs(next_repeat(RepeatMode.OFF), RepeatMode.QUEUE)
        self.assertIs(next_repeat(RepeatMode.QUEUE), RepeatMode.SONG)
        self.assertIs(next_repeat(RepeatMode.SONG), RepeatMode.OFF)


if __name__ == "__main__":
    unittest.main()
