import os
import shutil
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from json_store import read_json, write_json_atomic
from media import is_video_id, video_id
from track import LocalSong

INDEX_NAME = "index.json"
BYTES_PER_GB = 1024**3
PROJECT_DRIVE = Path("P:/")
FOLDER_PARTS = ("YT Widget", "Canciones")
AUDIO_EXTENSIONS = frozenset({"webm", "m4a", "opus", "ogg", "mp3"})
PARTIAL_SUFFIXES = (".part", ".ytdl")


@dataclass(frozen=True)
class CacheEntry:
    file_name: str
    size: int
    last_played: float
    title: str
    folder: Path | None = None


@dataclass(frozen=True)
class CacheUsage:
    bytes_used: int
    songs: int
    favorite_bytes: int = 0


@dataclass(frozen=True)
class CacheReport:
    kept_playing: bool = False
    failed: bool = False


class CacheCancelled(OSError):
    pass


def default_folder(project_drive: Path = PROJECT_DRIVE, local_root: Path | None = None) -> Path:
    if project_drive.exists():
        return project_drive.joinpath(*FOLDER_PARTS)
    root = local_root or Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return root.joinpath(*FOLDER_PARTS)


def configured_folder(folder: str | None) -> Path:
    return Path(folder) if folder else default_folder()


def limit_bytes(limit_gb: float) -> int:
    return int(limit_gb * BYTES_PER_GB)


def load_entries(folder: Path) -> dict[str, CacheEntry]:
    raw = read_json(folder / INDEX_NAME)
    songs = raw.get("songs") if isinstance(raw, dict) else None
    if not isinstance(songs, dict):
        return {}
    parsed = {key: _parse_entry(folder, key, value) for key, value in songs.items()}
    return {key: entry for key, entry in parsed.items() if entry}


def adopt_orphans(folder: Path, entries: dict[str, CacheEntry]) -> bool:
    if not (folder / INDEX_NAME).is_file():
        return False
    known = {entry.file_name for entry in entries.values()}
    try:
        files = [path for path in folder.iterdir() if path.is_file()]
    except OSError:
        return False
    adopted = False
    for path in files:
        song_id, _, extension = path.name.partition(".")
        if path.name in known or not is_video_id(song_id):
            continue
        if path.name.endswith(PARTIAL_SUFFIXES):
            with suppress(OSError):
                path.unlink()
        elif extension in AUDIO_EXTENSIONS and song_id not in entries:
            with suppress(OSError):
                entries[song_id] = CacheEntry(path.name, path.stat().st_size, 0.0, song_id)
                adopted = True
    return adopted


def _parse_entry(folder: Path, key: str, value: object) -> CacheEntry | None:
    if not is_video_id(key) or not isinstance(value, dict):
        return None
    file_name = value.get("file")
    if not isinstance(file_name, str) or Path(file_name).name != file_name or file_name == INDEX_NAME:
        return None
    stored_folder = value.get("folder")
    owner = Path(stored_folder) if isinstance(stored_folder, str) and stored_folder and Path(stored_folder) != folder else None
    try:
        size = ((owner or folder) / file_name).stat().st_size
    except OSError:
        return None
    played = value.get("last_played")
    title = value.get("title")
    return CacheEntry(
        file_name,
        size,
        float(played) if isinstance(played, (int, float)) and not isinstance(played, bool) else 0.0,
        title if isinstance(title, str) and title else key,
        owner,
    )


def _serialize(entry: CacheEntry) -> dict[str, object]:
    stored: dict[str, object] = {"file": entry.file_name, "size": entry.size, "last_played": entry.last_played, "title": entry.title}
    if entry.folder:
        stored["folder"] = str(entry.folder)
    return stored


def _stopped(stop: threading.Event | None) -> bool:
    return stop is not None and stop.is_set()


class SongCache:
    def __init__(self, folder: Path, limit_bytes: int, enabled: bool = False, clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.RLock()
        self._folder = folder
        self._limit_bytes = limit_bytes
        self._clock = clock
        self._dirty = False
        self._busy = False
        self._relocations: dict[str, str | None] = {}
        self._favorites: frozenset[str] = frozenset()
        self._entries = self._load(folder)
        self.enabled = enabled
        self.playing_file: str | None = None

    @property
    def folder(self) -> Path:
        return self._folder

    @property
    def busy(self) -> bool:
        return self._busy

    def configure(self, enabled: bool, folder: Path, limit_bytes: int) -> None:
        with self._lock:
            self.enabled = enabled
            if folder != self._folder:
                with suppress(OSError):
                    self.flush()
                self._folder = folder
                self._entries = self._load(folder)
            self._limit_bytes = limit_bytes
            if self._evict():
                self._save()

    def contains(self, song_id: str) -> bool:
        return song_id in self._entries

    def accepts(self, song_id: str) -> bool:
        return self.enabled or song_id in self._favorites

    def is_favorite(self, song_id: str) -> bool:
        return song_id in self._favorites

    def set_favorites(self, song_ids: Iterable[str]) -> None:
        with self._lock:
            chosen = frozenset(song_ids)
            released = self._favorites - chosen
            self._favorites = chosen
            if released and self._evict():
                self._save()

    def is_stored(self, uri: str) -> bool:
        song_id = video_id(uri)
        return song_id is not None and self.accepts(song_id) and song_id in self._entries

    def find(self, uri: str) -> LocalSong | None:
        song_id = video_id(uri)
        with self._lock:
            entry = self._entries.get(song_id) if song_id and self.accepts(song_id) and not self._busy else None
            if entry is None:
                return None
            path = self._path(entry)
            if not path.is_file():
                del self._entries[song_id]
                self._dirty = True
                return None
            self._entries[song_id] = replace(entry, last_played=self._clock())
            self._dirty = True
            return LocalSong(str(path), entry.title)

    def add(self, song_id: str, file: Path, title: str) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._entries[song_id] = CacheEntry(file.name, file.stat().st_size, self._clock(), title)
            self._evict()
            self._save()
            return True

    def usage(self) -> CacheUsage:
        with self._lock:
            regular = [entry for song_id, entry in self._entries.items() if song_id not in self._favorites]
            favorite_bytes = sum(entry.size for song_id, entry in self._entries.items() if song_id in self._favorites)
            return CacheUsage(sum(entry.size for entry in regular), len(regular), favorite_bytes)

    def take_relocations(self) -> dict[str, str | None]:
        with self._lock:
            changes, self._relocations = self._relocations, {}
        return changes

    def clear(self, stop: threading.Event | None = None) -> CacheReport:
        entries, folder, keep = self._begin()
        try:
            deleted: list[tuple[str, str]] = []
            kept = failed = False
            for song_id, entry in entries.items():
                if _stopped(stop):
                    break
                if song_id in self._favorites:
                    continue
                path = (entry.folder or folder) / entry.file_name
                if str(path) == keep:
                    kept = True
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    failed = True
                    continue
                deleted.append((song_id, str(path)))
            with self._lock:
                for song_id, path in deleted:
                    self._entries.pop(song_id, None)
                    self._relocations[path] = None
                self._save()
        finally:
            self._busy = False
        return CacheReport(kept_playing=kept, failed=failed)

    def move_to(self, destination: Path, stop: threading.Event | None = None) -> CacheReport:
        destination.mkdir(parents=True, exist_ok=True)
        entries, folder, keep = self._begin()
        try:
            return self._move(entries, folder, destination, keep, stop)
        finally:
            self._busy = False

    def flush(self) -> None:
        with self._lock:
            if self._dirty:
                self._save()

    def _begin(self) -> tuple[dict[str, CacheEntry], Path, str | None]:
        with self._lock:
            self._busy = True
            return dict(self._entries), self._folder, self.playing_file

    def _move(self, entries: dict[str, CacheEntry], folder: Path, destination: Path, keep: str | None, stop: threading.Event | None) -> CacheReport:
        placed: dict[str, CacheEntry] = {}
        stranded: dict[str, CacheEntry] = {}
        moved_files: list[tuple[Path, Path]] = []
        duplicates: list[Path] = []
        relocated: dict[str, str | None] = {}
        try:
            for song_id, entry in entries.items():
                if _stopped(stop):
                    raise CacheCancelled("Moving the cached songs was cancelled")
                source = (entry.folder or folder) / entry.file_name
                target = destination / entry.file_name
                if str(source) == keep:
                    stranded[song_id] = replace(entry, folder=source.parent)
                elif not source.is_file():
                    relocated[str(source)] = None
                elif source == target:
                    placed[song_id] = replace(entry, folder=None)
                elif target.exists():
                    placed[song_id] = replace(entry, size=target.stat().st_size, folder=None)
                    duplicates.append(source)
                    relocated[str(source)] = str(target)
                else:
                    shutil.move(source, target)
                    moved_files.append((source, target))
                    placed[song_id] = replace(entry, folder=None)
                    relocated[str(source)] = str(target)
        except OSError:
            for source, target in moved_files:
                with suppress(OSError):
                    shutil.move(target, source)
            raise
        arrived = self._load(destination)
        with self._lock:
            self._folder = destination
            self._entries = {**placed, **arrived, **stranded}
            self._relocations.update(relocated)
            self._save()
        for duplicate in duplicates:
            with suppress(OSError):
                duplicate.unlink()
        with suppress(OSError):
            (folder / INDEX_NAME).unlink()
        return CacheReport(kept_playing=bool(stranded))

    def _path(self, entry: CacheEntry) -> Path:
        return (entry.folder or self._folder) / entry.file_name

    def _load(self, folder: Path) -> dict[str, CacheEntry]:
        entries = load_entries(folder)
        if adopt_orphans(folder, entries):
            self._dirty = True
        return entries

    def _evict(self) -> bool:
        if self._busy:
            return False
        regular = {song_id: entry for song_id, entry in self._entries.items() if song_id not in self._favorites}
        total = sum(entry.size for entry in regular.values())
        removed = False
        for song_id, entry in sorted(regular.items(), key=lambda item: item[1].last_played):
            if total <= self._limit_bytes:
                break
            path = self._path(entry)
            if str(path) == self.playing_file:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            del self._entries[song_id]
            self._relocations[str(path)] = None
            total -= entry.size
            removed = True
        return removed

    def _save(self) -> None:
        write_json_atomic(
            self._folder / INDEX_NAME,
            {
                "songs": {song_id: _serialize(entry) for song_id, entry in self._entries.items()}
            },
        )
        self._dirty = False
