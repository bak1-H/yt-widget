from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from json_store import read_json, write_json_atomic
from track import Track

MAX_ENTRIES = 50


class HistoryStore(Protocol):
    def load(self) -> list[Track]: ...

    def save(self, entries: list[Track]) -> None: ...


class History:
    def __init__(self, store: HistoryStore, max_entries: int = MAX_ENTRIES) -> None:
        self._store = store
        self._max_entries = max_entries
        self._entries = store.load()[:max_entries]

    @property
    def entries(self) -> tuple[Track, ...]:
        return tuple(self._entries)

    def record(self, entry: Track) -> None:
        if self._entries[:1] == [entry]:
            return
        others = [existing for existing in self._entries if existing.uri != entry.uri]
        self._commit([entry, *others][: self._max_entries])

    def clear(self) -> tuple[Track, ...]:
        previous = self.entries
        self._commit([])
        return previous

    def restore(self, entries: tuple[Track, ...]) -> None:
        current = {entry.uri for entry in self._entries}
        recovered = [entry for entry in entries if entry.uri not in current]
        self._commit([*self._entries, *recovered][: self._max_entries])

    def remove(self, index: int) -> None:
        self._commit([entry for position, entry in enumerate(self._entries) if position != index])

    def insert(self, index: int, entry: Track) -> None:
        others = [existing for existing in self._entries if existing.uri != entry.uri]
        self._commit([*others[:index], entry, *others[index:]][: self._max_entries])

    def _commit(self, entries: list[Track]) -> None:
        previous = self._entries
        self._entries = entries
        try:
            self._store.save(self._entries)
        except OSError:
            self._entries = previous
            raise


class JsonHistoryStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[Track]:
        try:
            return [Track(**item) for item in read_json(self._path)]
        except TypeError:
            return []

    def save(self, entries: list[Track]) -> None:
        write_json_atomic(self._path, [asdict(entry) for entry in entries])
