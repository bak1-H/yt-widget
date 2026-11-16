import tempfile
import unittest
from pathlib import Path

from history import History, JsonHistoryStore
from track import Track


class MemoryStore:
    def __init__(self, entries: list[Track] | None = None) -> None:
        self.entries = entries or []
        self.saves = 0
        self.failing = False

    def load(self) -> list[Track]:
        return list(self.entries)

    def save(self, entries: list[Track]) -> None:
        if self.failing:
            raise OSError("disk full")
        self.entries = list(entries)
        self.saves += 1


FIRST = Track("First", "uri-1")
SECOND = Track("Second", "uri-2")


class HistoryTest(unittest.TestCase):
    def test_newest_first_without_duplicates(self) -> None:
        store = MemoryStore()
        history = History(store)
        for entry in (FIRST, SECOND, FIRST):
            history.record(entry)
        self.assertEqual(history.entries, (FIRST, SECOND))
        self.assertEqual(store.entries, [FIRST, SECOND])

    def test_repeating_latest_does_not_save(self) -> None:
        store = MemoryStore([FIRST])
        History(store).record(FIRST)
        self.assertEqual(store.saves, 0)

    def test_keeps_limit(self) -> None:
        history = History(MemoryStore(), max_entries=1)
        history.record(FIRST)
        history.record(SECOND)
        self.assertEqual(history.entries, (SECOND,))


    def test_failed_save_rolls_back_and_raises(self) -> None:
        store = MemoryStore([FIRST])
        history = History(store)
        store.failing = True
        with self.assertRaises(OSError):
            history.record(SECOND)
        self.assertEqual(history.entries, (FIRST,))

    def test_clear_returns_previous_and_restore_brings_it_back(self) -> None:
        store = MemoryStore([FIRST, SECOND])
        history = History(store)
        previous = history.clear()
        self.assertEqual((history.entries, store.entries), ((), []))
        history.restore(previous)
        self.assertEqual(history.entries, (FIRST, SECOND))

    def test_restore_keeps_newer_entries_first_without_duplicates(self) -> None:
        history = History(MemoryStore([FIRST, SECOND]))
        previous = history.clear()
        history.record(SECOND)
        history.restore(previous)
        self.assertEqual(history.entries, (SECOND, FIRST))

    def test_failed_clear_rolls_back(self) -> None:
        store = MemoryStore([FIRST])
        history = History(store)
        store.failing = True
        with self.assertRaises(OSError):
            history.clear()
        self.assertEqual(history.entries, (FIRST,))

    def test_remove_and_insert_at_index(self) -> None:
        history = History(MemoryStore([FIRST, SECOND]))
        history.remove(0)
        self.assertEqual(history.entries, (SECOND,))
        history.insert(0, FIRST)
        self.assertEqual(history.entries, (FIRST, SECOND))


class JsonHistoryStoreTest(unittest.TestCase):
    def test_round_trip_and_corrupt_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "history.json"
            store = JsonHistoryStore(path)
            self.assertEqual(store.load(), [])
            store.save([FIRST, SECOND])
            self.assertEqual(store.load(), [FIRST, SECOND])
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.load(), [])


if __name__ == "__main__":
    unittest.main()
