import tkinter as tk
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

OPAQUE_PERCENT = 100
ALPHA_SHIFT = 24
BLUE_SHIFT = 16
GREEN_SHIFT = 8
HEX_COLOR_LENGTH = 7


class ThemeName(str, Enum):
    GLASS = "glass"
    NIGHT = "night"
    VINYL = "vinyl"
    FROST = "frost"


class PlayShape(Enum):
    SQUARE = "square"
    CIRCLE = "circle"
    PILL = "pill"


class TabStyle(Enum):
    FILLED = "filled"
    PILL = "pill"
    SEGMENTED = "segmented"
    UNDERLINE = "underline"


class RowStyle(Enum):
    PLAIN = "plain"
    CARD = "card"
    DIVIDER = "divider"


class IndicatorStyle(Enum):
    BARS = "bars"
    DISC = "disc"


ROW_GAPS = {RowStyle.PLAIN: 0, RowStyle.CARD: 2, RowStyle.DIVIDER: 1}
ROW_GAP_ROLES = {RowStyle.PLAIN: "surface", RowStyle.CARD: "background", RowStyle.DIVIDER: "separator"}
ROW_AREA_ROLES = {RowStyle.PLAIN: "surface", RowStyle.CARD: "background", RowStyle.DIVIDER: "surface"}


@dataclass(frozen=True)
class Theme:
    name: ThemeName
    background: str
    surface: str
    surface_hover: str
    border: str
    foreground: str
    muted: str
    accent: str
    accent_hover: str
    danger: str
    on_accent: str
    tab_track: str
    separator: str
    slider_track: str
    meter_track: str
    bar_fill: str
    bar_alert: str
    downloaded: str
    downloaded_background: str | None
    glass_tint: str
    play_shape: PlayShape
    play_size: int
    outlined_skips: bool
    tab_style: TabStyle
    row_style: RowStyle
    numbered_rows: bool
    indicator_style: IndicatorStyle

    @property
    def row_gap(self) -> int:
        return ROW_GAPS[self.row_style]

    @property
    def row_gap_color(self) -> str:
        return getattr(self, ROW_GAP_ROLES[self.row_style])

    @property
    def row_area_color(self) -> str:
        return getattr(self, ROW_AREA_ROLES[self.row_style])

    def glass_tint_abgr(self, opacity_percent: int) -> int:
        alpha = round(opacity_percent * 255 / OPAQUE_PERCENT)
        red, green, blue = (int(self.glass_tint[index : index + 2], 16) for index in (1, 3, 5))
        return (alpha << ALPHA_SHIFT) | (blue << BLUE_SHIFT) | (green << GREEN_SHIFT) | red

    def marker_background(self, base: str, downloaded: bool) -> str:
        return self.downloaded_background if downloaded and self.downloaded_background else base


GLASS = Theme(
    name=ThemeName.GLASS,
    background="#181825",
    surface="#262637",
    surface_hover="#363650",
    border="#313244",
    foreground="#cdd6f4",
    muted="#a6adc8",
    accent="#89b4fa",
    accent_hover="#b4d0fb",
    danger="#f38ba8",
    on_accent="#181825",
    tab_track="#181825",
    separator="#313244",
    slider_track="#6f6f80",
    meter_track="#6f6f80",
    bar_fill="#b4d0fb",
    bar_alert="#ffc2d1",
    downloaded="#89b4fa",
    downloaded_background=None,
    glass_tint="#181825",
    play_shape=PlayShape.SQUARE,
    play_size=0,
    outlined_skips=False,
    tab_style=TabStyle.FILLED,
    row_style=RowStyle.PLAIN,
    numbered_rows=False,
    indicator_style=IndicatorStyle.BARS,
)

NIGHT = Theme(
    name=ThemeName.NIGHT,
    background="#181825",
    surface="#262637",
    surface_hover="#363650",
    border="#313244",
    foreground="#cdd6f4",
    muted="#a6adc8",
    accent="#89b4fa",
    accent_hover="#b4d0fb",
    danger="#f38ba8",
    on_accent="#11111b",
    tab_track="#11111b",
    separator="#313244",
    slider_track="#6f6f80",
    meter_track="#6f6f80",
    bar_fill="#b4d0fb",
    bar_alert="#ffc2d1",
    downloaded="#a6e3a1",
    downloaded_background=None,
    glass_tint="#181825",
    play_shape=PlayShape.CIRCLE,
    play_size=48,
    outlined_skips=False,
    tab_style=TabStyle.PILL,
    row_style=RowStyle.CARD,
    numbered_rows=False,
    indicator_style=IndicatorStyle.BARS,
)

VINYL = Theme(
    name=ThemeName.VINYL,
    background="#1d1814",
    surface="#2a231d",
    surface_hover="#3a3029",
    border="#3a3029",
    foreground="#f3e9dc",
    muted="#c9b8a6",
    accent="#f2a65a",
    accent_hover="#f7c08a",
    danger="#e5846a",
    on_accent="#1d1814",
    tab_track="#1d1814",
    separator="#3a3029",
    slider_track="#746d67",
    meter_track="#746d67",
    bar_fill="#f7c08a",
    bar_alert="#ffbfae",
    downloaded="#f2a65a",
    downloaded_background=None,
    glass_tint="#1d1814",
    play_shape=PlayShape.CIRCLE,
    play_size=50,
    outlined_skips=True,
    tab_style=TabStyle.UNDERLINE,
    row_style=RowStyle.DIVIDER,
    numbered_rows=True,
    indicator_style=IndicatorStyle.DISC,
)

FROST = Theme(
    name=ThemeName.FROST,
    background="#eef1f6",
    surface="#ffffff",
    surface_hover="#e3e8f2",
    border="#cfd6e4",
    foreground="#1b1f2a",
    muted="#4a5468",
    accent="#3b5bdb",
    accent_hover="#2f4ac0",
    danger="#c02626",
    on_accent="#ffffff",
    tab_track="#e3e8f2",
    separator="#e3e8f2",
    slider_track="#7d879c",
    meter_track="#7d879c",
    bar_fill="#1b2f85",
    bar_alert="#6b1414",
    downloaded="#1e6b34",
    downloaded_background="#dff3e4",
    glass_tint="#000000",
    play_shape=PlayShape.PILL,
    play_size=36,
    outlined_skips=False,
    tab_style=TabStyle.SEGMENTED,
    row_style=RowStyle.DIVIDER,
    numbered_rows=False,
    indicator_style=IndicatorStyle.BARS,
)

THEMES = {theme.name: theme for theme in (GLASS, NIGHT, VINYL, FROST)}
DEFAULT_THEME = ThemeName.GLASS

TITLE_FONT = ("Segoe UI Semibold", 11)
TEXT_FONT = ("Segoe UI", 10)
SMALL_FONT = ("Segoe UI", 9)
LINK_FONT = ("Segoe UI", 9, "underline")
HEADING_FONT = ("Segoe UI Semibold", 9)
ICON_FONT = ("Segoe Fluent Icons", 11)
ICON_FONT_LARGE = ("Segoe Fluent Icons", 15)
ICON_FONT_SMALL = ("Segoe Fluent Icons", 9)
NOTE_FONT = ("Segoe UI Symbol", 20)
NOTE_GLYPH = "♪"


class Icon:
    PLAY = ""
    PAUSE = ""
    PREVIOUS = ""
    NEXT = ""
    VOLUME = ""
    ADD = ""
    LIST = ""
    CLOSE = ""
    SEARCH = ""
    DELETE = ""
    MORE = ""
    REPEAT_ALL = ""
    REPEAT_OFF = ""
    REPEAT_ONE = ""
    DOWNLOADED = ""
    HEART = ""
    HEART_FILLED = ""


class Restylable(Protocol):
    def apply_theme(self, theme: Theme) -> None: ...


class _Registry:
    def __init__(self) -> None:
        self.current = THEMES[DEFAULT_THEME]
        self.roles: weakref.WeakKeyDictionary[tk.Misc, dict[str, str]] = weakref.WeakKeyDictionary()
        self.observers: weakref.WeakSet[Restylable] = weakref.WeakSet()


_registry = _Registry()


def theme_for(name: ThemeName | str) -> Theme:
    try:
        return THEMES[ThemeName(name)]
    except ValueError:
        return THEMES[DEFAULT_THEME]


def current() -> Theme:
    return _registry.current


def color(role: str) -> str:
    return getattr(_registry.current, role)


def glass_tint(opacity_percent: int) -> int:
    return _registry.current.glass_tint_abgr(opacity_percent)


def bind(widget: tk.Misc, **roles: str) -> None:
    _registry.roles.setdefault(widget, {}).update(roles)
    widget.configure(**{option: color(role) for option, role in roles.items()})


def bind_menu(menu: tk.Menu) -> None:
    bind(menu, bg="surface", fg="foreground", activebackground="accent", activeforeground="on_accent", selectcolor="accent")


def role_of(widget: tk.Misc, option: str = "bg") -> str:
    return _registry.roles[widget][option]


def observe(widget: Restylable) -> None:
    _registry.observers.add(widget)


def select(name: ThemeName | str) -> Theme:
    theme = theme_for(name)
    _registry.current = theme
    for widget, roles in list(_registry.roles.items()):
        if _is_alive(widget):
            widget.configure(**{option: getattr(theme, role) for option, role in roles.items()})
    for observer in list(_registry.observers):
        if _is_alive(observer):
            observer.apply_theme(theme)
    return theme


def reset() -> None:
    select(DEFAULT_THEME)


def _is_alive(widget: object) -> bool:
    if not isinstance(widget, tk.Misc):
        return True
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False
