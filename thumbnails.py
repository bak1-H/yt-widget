import http.client
import urllib.request
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Callable, Generic, Protocol, TypeVar

from callbacks import run_each
from media import is_video_id

THUMBNAIL_HOST = "i.ytimg.com"
THUMBNAIL_QUALITY = "mqdefault"
FETCH_TIMEOUT_SECONDS = 10
MAX_THUMBNAIL_BYTES = 200_000
JPEG_SIGNATURE = b"\xff\xd8"
USER_AGENT = "Mozilla/5.0"
MEMORY_CAPACITY = 20
DISK_FOLDER_NAME = ".yt-widget-thumbnails"
DISK_LIMIT = 200
DISK_SUFFIX = ".jpg"

ImageT = TypeVar("ImageT")
KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


class ThumbnailError(RuntimeError):
    pass


def thumbnail_url(song_id: str) -> str:
    if not is_video_id(song_id):
        raise ThumbnailError(f"Invalid video id: {song_id!r}")
    return f"https://{THUMBNAIL_HOST}/vi/{song_id}/{THUMBNAIL_QUALITY}.jpg"


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_arguments: object, **_options: object) -> None:
        return None


def fetch_thumbnail(song_id: str) -> bytes:
    request = urllib.request.Request(thumbnail_url(song_id), headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_RefuseRedirects)
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_THUMBNAIL_BYTES + 1)
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise ThumbnailError(f"Could not fetch the thumbnail of {song_id}") from error
    if not is_jpeg(data):
        raise ThumbnailError(f"Unexpected thumbnail data for {song_id}")
    return data


def is_jpeg(data: bytes) -> bool:
    return data.startswith(JPEG_SIGNATURE) and len(data) <= MAX_THUMBNAIL_BYTES


class LruCache(Generic[KeyT, ValueT]):
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._items: OrderedDict[KeyT, ValueT] = OrderedDict()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def get(self, key: KeyT) -> ValueT | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: KeyT, value: ValueT) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)


class DiskThumbnails:
    def __init__(self, song_folder: Callable[[], Path | None], limit: int = DISK_LIMIT) -> None:
        self._song_folder = song_folder
        self._limit = limit

    def path_for(self, song_id: str) -> Path | None:
        folder = self._song_folder()
        if folder is None or not is_video_id(song_id):
            return None
        return folder / DISK_FOLDER_NAME / f"{song_id}{DISK_SUFFIX}"

    def read(self, song_id: str) -> bytes | None:
        path = self.path_for(song_id)
        if path is None:
            return None
        try:
            data = path.read_bytes()
        except OSError:
            return None
        return data if is_jpeg(data) else None

    def write(self, song_id: str, data: bytes) -> None:
        path = self.path_for(song_id)
        if path is None:
            return
        with suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self._prune(path.parent)

    def _prune(self, folder: Path) -> None:
        owned = (file for file in folder.glob(f"*{DISK_SUFFIX}") if file.suffix == DISK_SUFFIX and is_video_id(file.stem) and file.is_file())
        files = sorted(owned, key=lambda file: file.stat().st_mtime)
        for stale in files[: max(len(files) - self._limit, 0)]:
            with suppress(OSError):
                stale.unlink()


class ThumbnailStore(Protocol):
    def read(self, song_id: str) -> bytes | None: ...

    def write(self, song_id: str, data: bytes) -> None: ...


OnLoaded = Callable[[str, bytes | None], None]


class ThumbnailLoader:
    def __init__(self, fetch: Callable[[str], bytes], store: ThumbnailStore) -> None:
        self._fetch = fetch
        self._store = store
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="thumbnails")
        self._pending: list[tuple[str, Future[bytes | None]]] = []

    def request(self, song_id: str) -> None:
        if any(pending_id == song_id for pending_id, _ in self._pending):
            return
        self._pending.append((song_id, self._executor.submit(self._load, song_id)))

    def deliver(self, on_loaded: OnLoaded) -> None:
        finished = [entry for entry in self._pending if entry[1].done()]
        self._pending = [entry for entry in self._pending if entry not in finished]
        run_each(partial(on_loaded, song_id, None if future.exception() else future.result()) for song_id, future in finished)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _load(self, song_id: str) -> bytes | None:
        stored = self._store.read(song_id)
        if stored is not None:
            return stored
        try:
            data = self._fetch(song_id)
        except ThumbnailError:
            return None
        self._store.write(song_id, data)
        return data


class ThumbnailFeed(Generic[ImageT]):
    def __init__(
        self,
        loader: ThumbnailLoader,
        decode: Callable[[bytes], ImageT],
        show: Callable[[ImageT | None], None],
        capacity: int = MEMORY_CAPACITY,
    ) -> None:
        self._loader = loader
        self._decode = decode
        self._show = show
        self._images: LruCache[str, ImageT] = LruCache(capacity)
        self._current: str | None = None

    def select(self, song_id: str | None) -> None:
        if song_id == self._current:
            return
        self._current = song_id
        image = self._images.get(song_id) if song_id else None
        self._show(image)
        if song_id and image is None:
            self._loader.request(song_id)

    def deliver(self) -> None:
        self._loader.deliver(self._arrived)

    def _arrived(self, song_id: str, data: bytes | None) -> None:
        if data is None:
            return
        try:
            image = self._decode(data)
        except ThumbnailError:
            return
        self._images.put(song_id, image)
        if song_id == self._current:
            self._show(image)
