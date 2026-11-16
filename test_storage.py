import tempfile
import threading
import time
import unittest
from pathlib import Path

from storage import LOW_SPACE_BYTES, DriveSpace, DriveSpaceReader, drive_space, used_percent, used_ratio

GB = 1024**3
FOLDER = Path("P:/songs")


class UsedRatioTest(unittest.TestCase):
    def test_is_the_fraction_used(self) -> None:
        self.assertEqual(used_ratio(50, 200), 0.25)
        self.assertEqual(used_ratio(0, 200), 0.0)

    def test_over_the_limit_is_clamped_to_full(self) -> None:
        self.assertEqual(used_ratio(300, 200), 1.0)

    def test_a_zero_limit_is_full_only_when_something_is_stored(self) -> None:
        self.assertEqual(used_ratio(10, 0), 1.0)
        self.assertEqual(used_ratio(0, 0), 0.0)

    def test_negative_values_never_go_below_empty(self) -> None:
        self.assertEqual(used_ratio(-5, 100), 0.0)

    def test_percent_is_rounded(self) -> None:
        self.assertEqual((used_percent(0.654), used_percent(1.0), used_percent(0.0)), (65, 100, 0))


class LowSpaceTest(unittest.TestCase):
    def test_a_full_cache_on_a_roomy_drive_is_not_low(self) -> None:
        self.assertFalse(DriveSpace(500 * GB, 1000 * GB, "P:").is_low)

    def test_less_than_one_gigabyte_free_is_low(self) -> None:
        self.assertTrue(DriveSpace(LOW_SPACE_BYTES - 1, 10 * GB, "P:").is_low)
        self.assertFalse(DriveSpace(LOW_SPACE_BYTES, 10 * GB, "P:").is_low)

    def test_less_than_five_percent_free_is_low(self) -> None:
        self.assertTrue(DriveSpace(40 * GB, 1000 * GB, "P:").is_low)
        self.assertFalse(DriveSpace(50 * GB, 1000 * GB, "P:").is_low)


class DriveSpaceTest(unittest.TestCase):
    def test_measures_the_nearest_existing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            space = drive_space(Path(directory) / "missing" / "deeper")
        self.assertIsNotNone(space)
        self.assertGreater(space.free_bytes, 0)
        self.assertGreaterEqual(space.total_bytes, space.free_bytes)
        self.assertEqual(space.drive, Path(directory).drive)


class DriveSpaceReaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [0.0]
        self.calls: list[Path] = []
        self.release = threading.Event()
        self.release.set()
        self.reader = DriveSpaceReader(self.measure, max_age=30.0, clock=lambda: self.now[0])

    def measure(self, folder: Path) -> DriveSpace | None:
        self.calls.append(folder)
        self.release.wait(2)
        return DriveSpace(len(self.calls) * GB, 100 * GB, "P:")

    def settle(self, folder: Path = FOLDER) -> DriveSpace | None:
        deadline = time.monotonic() + 2
        result = self.reader.read(folder)
        while result is None and time.monotonic() < deadline:
            time.sleep(0.01)
            result = self.reader.read(folder)
        return result

    def test_the_first_read_returns_nothing_without_waiting_for_the_drive(self) -> None:
        self.release.clear()
        self.assertIsNone(self.reader.read(FOLDER))
        self.assertIsNone(self.reader.read(FOLDER))
        self.release.set()
        self.assertEqual(self.settle().free_bytes, GB)
        self.assertEqual(len(self.calls), 1)

    def test_the_cached_value_is_reused_until_it_gets_old(self) -> None:
        self.assertEqual(self.settle().free_bytes, GB)
        self.now[0] = 29.0
        self.assertEqual(self.reader.read(FOLDER).free_bytes, GB)
        self.assertEqual(len(self.calls), 1)
        self.now[0] = 31.0
        self.assertEqual(self.reader.read(FOLDER).free_bytes, GB)
        deadline = time.monotonic() + 2
        while len(self.calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.reader.read(FOLDER).free_bytes, 2 * GB)

    def test_another_folder_never_shows_the_old_folder_value(self) -> None:
        self.settle()
        self.assertIsNone(self.reader.read(Path("G:/other")))


if __name__ == "__main__":
    unittest.main()
