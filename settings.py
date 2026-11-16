from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, TypeVar

from json_store import read_json, write_json_atomic
from repeat import RepeatMode
from theme import DEFAULT_THEME, ThemeName

DEFAULT_VOLUME = 60
MAX_VOLUME = 100
DEFAULT_PREFETCH = 2
MAX_PREFETCH = 3
MIN_GLASS_OPACITY = 0
MAX_GLASS_OPACITY = 100
DEFAULT_GLASS_OPACITY = 80
CACHE_LIMITS_GB = (0.5, 1.0, 2.0, 5.0, 10.0)
DEFAULT_CACHE_LIMIT_GB = 2.0

EnumT = TypeVar("EnumT", bound=Enum)


class WindowPosition(str, Enum):
    TOPMOST = "topmost"
    NORMAL = "normal"
    DESKTOP = "desktop"


class CloseAction(str, Enum):
    HIDE = "hide"
    QUIT = "quit"


class GlassStyle(str, Enum):
    BLUR = "blur"
    CLEAR = "clear"


class CacheQuality(str, Enum):
    MAX = "max"
    MEDIUM = "medium"


@dataclass(frozen=True)
class Settings:
    window_position: WindowPosition = WindowPosition.TOPMOST
    glass: bool = True
    startup_volume: int = DEFAULT_VOLUME
    close_action: CloseAction = CloseAction.HIDE
    prefetch_count: int = DEFAULT_PREFETCH
    glass_opacity: int = DEFAULT_GLASS_OPACITY
    cache_enabled: bool = False
    cache_folder: str | None = None
    cache_limit_gb: float = DEFAULT_CACHE_LIMIT_GB
    cache_quality: CacheQuality = CacheQuality.MAX
    repeat_mode: RepeatMode = RepeatMode.OFF
    autoplay: bool = False
    show_thumbnail: bool = True
    theme: ThemeName = DEFAULT_THEME
    glass_style: GlassStyle = GlassStyle.BLUR


class SettingsStore(Protocol):
    def load(self) -> Settings: ...

    def save(self, settings: Settings) -> None: ...


class JsonSettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Settings:
        return parse_settings(read_json(self._path))

    def save(self, settings: Settings) -> None:
        write_json_atomic(
            self._path,
            {
                "window_position": settings.window_position.value,
                "glass": settings.glass,
                "startup_volume": settings.startup_volume,
                "close_action": settings.close_action.value,
                "prefetch_count": settings.prefetch_count,
                "glass_opacity": settings.glass_opacity,
                "cache_enabled": settings.cache_enabled,
                "cache_folder": settings.cache_folder,
                "cache_limit_gb": settings.cache_limit_gb,
                "cache_quality": settings.cache_quality.value,
                "repeat_mode": settings.repeat_mode.value,
                "autoplay": settings.autoplay,
                "show_thumbnail": settings.show_thumbnail,
                "theme": settings.theme.value,
                "glass_style": settings.glass_style.value,
            },
        )


def parse_settings(raw: object) -> Settings:
    defaults = Settings()
    if not isinstance(raw, dict):
        return defaults
    return Settings(
        window_position=_choice(WindowPosition, raw.get("window_position"), defaults.window_position),
        glass=_flag(raw.get("glass"), defaults.glass),
        startup_volume=_bounded(raw.get("startup_volume"), defaults.startup_volume, MAX_VOLUME),
        close_action=_choice(CloseAction, raw.get("close_action"), defaults.close_action),
        prefetch_count=_bounded(raw.get("prefetch_count"), defaults.prefetch_count, MAX_PREFETCH),
        glass_opacity=_bounded(raw.get("glass_opacity"), defaults.glass_opacity, MAX_GLASS_OPACITY, MIN_GLASS_OPACITY),
        cache_enabled=_flag(raw.get("cache_enabled"), defaults.cache_enabled),
        cache_folder=_folder(raw.get("cache_folder")),
        cache_limit_gb=_cache_limit(raw.get("cache_limit_gb"), defaults.cache_limit_gb),
        cache_quality=_choice(CacheQuality, raw.get("cache_quality"), defaults.cache_quality),
        repeat_mode=_choice(RepeatMode, raw.get("repeat_mode"), defaults.repeat_mode),
        autoplay=_flag(raw.get("autoplay"), defaults.autoplay),
        show_thumbnail=_flag(raw.get("show_thumbnail"), defaults.show_thumbnail),
        theme=_choice(ThemeName, raw.get("theme"), defaults.theme),
        glass_style=_choice(GlassStyle, raw.get("glass_style"), defaults.glass_style),
    )


def _choice(kind: type[EnumT], value: object, default: EnumT) -> EnumT:
    try:
        return kind(value)
    except ValueError:
        return default


def _flag(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _bounded(value: object, default: int, maximum: int, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(max(value, minimum), maximum)


def _folder(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _cache_limit(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if float(value) in CACHE_LIMITS_GB else default
