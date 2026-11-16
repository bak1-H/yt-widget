import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Protocol

import texts
from json_store import read_json, write_json_atomic
from track import Track

MAX_NAME_LENGTH = 40
BACKUP_SUFFIX = ".bak"
FAVORITES = texts.FAVORITES

Playlists = dict[str, list[Track]]


class PlaylistNameError(ValueError):
    pass


class PlaylistExistsError(PlaylistNameError):
    def __init__(self, existing: str) -> None:
        super().__init__(texts.already_exists(existing))
        self.existing = existing


class PlaylistStore(Protocol):
    load_warning: str | None

    def load(self) -> Playlists: ...

    def save(self, playlists: Playlists) -> None: ...


class PlaylistLibrary:
    def __init__(self, store: PlaylistStore) -> None:
        self._store = store
        self._playlists = with_favorites(store.load())

    @property
    def load_warning(self) -> str | None:
        return self._store.load_warning

    def names(self) -> list[str]:
        others = sorted((name for name in self._playlists if name != FAVORITES), key=str.casefold)
        return [FAVORITES, *others]

    def tracks(self, name: str) -> tuple[Track, ...]:
        return tuple(self._playlists.get(name, ()))

    def index_of(self, name: str, uri: str) -> int | None:
        return next((index for index, track in enumerate(self._playlists.get(name, ())) if track.uri == uri), None)

    def contains(self, name: str, uri: str) -> bool:
        return self.index_of(name, uri) is not None

    def is_favorite(self, uri: str) -> bool:
        return self.contains(FAVORITES, uri)

    def names_containing(self, uri: str) -> list[str]:
        return [name for name in self.names() if self.contains(name, uri)]

    def create(self, name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise PlaylistNameError(texts.NAME_REQUIRED)
        if len(clean_name) > MAX_NAME_LENGTH:
            raise PlaylistNameError(texts.name_too_long(MAX_NAME_LENGTH))
        existing = self._find(clean_name)
        if existing:
            raise PlaylistExistsError(existing)
        self._commit(lambda: self._playlists.__setitem__(clean_name, []))
        return clean_name

    def restore(self, name: str, tracks: tuple[Track, ...]) -> None:
        existing = self._find(name)
        if existing:
            raise PlaylistExistsError(existing)
        self._commit(lambda: self._playlists.__setitem__(name, list(tracks)))

    def delete(self, name: str) -> None:
        if name == FAVORITES:
            raise PlaylistNameError(texts.FAVORITES_PROTECTED)
        if name in self._playlists:
            self._commit(lambda: self._playlists.pop(name))

    def add(self, name: str, track: Track) -> None:
        self._commit(lambda: self._playlists[name].append(track))

    def insert(self, name: str, index: int, track: Track) -> None:
        self._commit(lambda: self._playlists[name].insert(index, track))

    def remove(self, name: str, index: int) -> None:
        self._commit(lambda: self._playlists[name].pop(index))

    def replace(self, uri: str, track: Track) -> None:
        def swap() -> None:
            for tracks in self._playlists.values():
                for index, existing in enumerate(tracks):
                    if existing.uri == uri:
                        tracks[index] = track

        if any(existing.uri == uri for tracks in self._playlists.values() for existing in tracks):
            self._commit(swap)

    def _find(self, name: str) -> str | None:
        return next((existing for existing in self._playlists if existing.casefold() == name.casefold()), None)

    def _commit(self, change: Callable[[], object]) -> None:
        snapshot = {name: list(tracks) for name, tracks in self._playlists.items()}
        change()
        try:
            self._store.save(self._playlists)
        except OSError:
            self._playlists = snapshot
            raise


class JsonPlaylistStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.load_warning: str | None = None

    def load(self) -> Playlists:
        raw = read_json(self._path)
        if raw is None and not self._path.exists():
            return {}
        if not isinstance(raw, dict):
            self._report_damage()
            return {}
        playlists: Playlists = {}
        damaged = False
        for name, items in raw.items():
            tracks = parse_tracks(items)
            if tracks is None:
                damaged = True
                continue
            damaged = damaged or len(tracks) != len(items)
            playlists[str(name)] = tracks
        if damaged:
            self._report_damage()
        return playlists

    def save(self, playlists: Playlists) -> None:
        write_json_atomic(self._path, {name: [asdict(track) for track in tracks] for name, tracks in playlists.items()})

    def _report_damage(self) -> None:
        backup = self._path.with_name(self._path.name + BACKUP_SUFFIX)
        try:
            shutil.copy2(self._path, backup)
        except OSError:
            self.load_warning = texts.PLAYLISTS_DAMAGED_NO_BACKUP
            return
        self.load_warning = texts.playlists_damaged(backup.name)


def with_favorites(playlists: Playlists) -> Playlists:
    favorites: list[Track] = []
    others: Playlists = {}
    for name, tracks in playlists.items():
        if name.casefold() == FAVORITES.casefold():
            favorites.extend(track for track in tracks if track not in favorites)
        else:
            others[name] = tracks
    return {FAVORITES: favorites, **others}


def parse_tracks(items: object) -> list[Track] | None:
    if not isinstance(items, list):
        return None
    tracks = []
    for item in items:
        try:
            tracks.append(Track(**item))
        except TypeError:
            continue
    return tracks
