import re
from typing import Callable
from urllib.parse import parse_qs, urlparse

SEARCH_PREFIX = "ytdl://ytsearch:"
DISPLAY_PREFIXES = (SEARCH_PREFIX, "ytsearch:", "ytdl://")
UNKNOWN_TIME = "--:--"
ELLIPSIS = "…"
YOUTUBE_PREFIXES = (
    "https://www.youtube.com/",
    "https://youtube.com/",
    "https://m.youtube.com/",
    "https://music.youtube.com/",
    "https://youtu.be/",
)
VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
SHORT_HOST = "youtu.be"


def is_video_id(value: object) -> bool:
    return isinstance(value, str) and VIDEO_ID_PATTERN.fullmatch(value) is not None


def video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if host == SHORT_HOST:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS and parsed.path == "/watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
    else:
        return None
    return candidate if is_video_id(candidate) else None


def watch_url(song_id: str) -> str:
    return f"https://www.youtube.com/watch?v={song_id}"


def is_resolvable(uri: str) -> bool:
    return uri.startswith((SEARCH_PREFIX, *YOUTUBE_PREFIXES))


def to_media_uri(query: str) -> str:
    text = query.strip()
    if not text:
        raise ValueError("Query is empty")
    if text.startswith(("http://", "https://")):
        return text
    return f"{SEARCH_PREFIX}{text}"


def display_name(title: str | None, uri: str) -> str:
    name = title or uri
    for prefix in DISPLAY_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def format_time(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return UNKNOWN_TIME
    total_minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + ELLIPSIS


def fit_text(text: str, limit: int, measure: Callable[[str], int]) -> str:
    if measure(text) <= limit:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if measure(text[:middle].rstrip() + ELLIPSIS) <= limit:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + ELLIPSIS
