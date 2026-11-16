import math
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

import texts
import theme
from components import IconButton, SliderBar, Tooltip, TooltipText, enable_dragging
from indicator import SIZE as INDICATOR_SIZE
from indicator import PlaybackIndicator
from playback import PlaybackState
from theme import Icon
from thumbnail_view import WIDTH as THUMBNAIL_WIDTH
from thumbnail_view import ThumbnailBox, ThumbnailImage

TITLE_WIDTH_CHARS = 32
MARKER_WIDTH_CHARS = 2
BADGE_SIZE = 22
LEAD_GAP = 10


class NowPlayingHeader(tk.Frame):
    def __init__(
        self,
        parent: tk.Tk,
        on_close: Callable[[], None],
        close_tooltip: TooltipText,
        on_menu: Callable[[int, int], None],
        on_favorite: Callable[[], None],
        on_seek: Callable[[float], None],
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._title = tk.StringVar(value=texts.NOTHING_PLAYING)
        self._title_font = tkfont.Font(font=theme.TITLE_FONT)
        self._detail = tk.StringVar(value=texts.STATE_MESSAGES[PlaybackState.IDLE])
        row = tk.Frame(self)
        theme.bind(row, bg="background")
        row.pack(fill="x")
        lead = tk.Frame(row)
        theme.bind(lead, bg="background")
        lead.pack(side="left", padx=(0, LEAD_GAP))
        self._cover = ThumbnailBox(lead)
        self._indicator = PlaybackIndicator(lead)
        self._indicator.pack()
        self._thumbnail_enabled = False
        text = tk.Frame(row)
        theme.bind(text, bg="background")
        text.pack(side="left", fill="x", expand=True)
        title_row = tk.Frame(text)
        theme.bind(title_row, bg="background")
        title_row.pack(fill="x")
        self._marker = tk.Label(title_row, width=MARKER_WIDTH_CHARS, font=theme.ICON_FONT_SMALL)
        theme.bind(self._marker, bg="background", fg="downloaded")
        Tooltip(self._marker, lambda: texts.DOWNLOADED_TOOLTIP if self._marker.cget("text") else "")
        self._marker.pack(side="right")
        title = tk.Label(title_row, textvariable=self._title, width=TITLE_WIDTH_CHARS, anchor="w", font=theme.TITLE_FONT)
        theme.bind(title, bg="background", fg="foreground")
        title.pack(side="left", fill="x", expand=True)
        self._title_label = title
        detail = tk.Label(text, textvariable=self._detail, anchor="w", font=theme.SMALL_FONT)
        theme.bind(detail, bg="background", fg="muted")
        detail.pack(fill="x")
        more = IconButton(row, Icon.MORE, lambda: on_menu(more.winfo_rootx(), more.winfo_rooty() + more.winfo_height()), variant="ghost", tooltip=texts.SONG_OPTIONS)
        self._liked = False
        self._favorite = IconButton(row, Icon.HEART, on_favorite, variant="ghost", tooltip=lambda: texts.UNFAVORITE_TOOLTIP if self._liked else texts.FAVORITE_TOOLTIP)
        close = IconButton(row, Icon.CLOSE, on_close, variant="ghost", tooltip=close_tooltip)
        close.pack(side="right", anchor="n")
        more.pack(side="right", anchor="n")
        self._favorite.pack(side="right", anchor="n")
        Tooltip(title, lambda: self._title.get() if self._title_font.measure(self._title.get()) > title.winfo_width() else "")
        enable_dragging(parent, row, lead, self._indicator, self._cover, text, title_row, title, self._marker, detail)
        self._progress = SliderBar(self, on_change=on_seek, live=False)
        self._progress.pack(fill="x", pady=(10, 8))
        theme.observe(self)

    def apply_theme(self, _theme: theme.Theme) -> None:
        self._paint_marker()

    def render(self, state: PlaybackState, title: str, detail: str, ratio: float, downloaded: bool) -> None:
        self._indicator.set_state(state)
        self._title.set(title)
        self._show_downloaded(downloaded)
        self._detail.set(detail)
        self._progress.set_ratio(ratio)

    def show_favorite(self, liked: bool) -> None:
        if liked == self._liked:
            return
        self._liked = liked
        self._favorite.set_icon(Icon.HEART_FILLED if liked else Icon.HEART)
        self._favorite.set_foreground("accent" if liked else "muted")

    def _show_downloaded(self, downloaded: bool) -> None:
        if bool(self._marker.cget("text")) != downloaded:
            self._marker.configure(text=Icon.DOWNLOADED if downloaded else "")
            self._paint_marker()

    def _paint_marker(self) -> None:
        downloaded = bool(self._marker.cget("text"))
        theme.bind(self._marker, bg="downloaded_background" if downloaded and theme.current().downloaded_background else "background")

    def show_thumbnail(self, image: ThumbnailImage | None) -> None:
        self._cover.show(image)

    def set_thumbnail_enabled(self, enabled: bool) -> None:
        if enabled == self._thumbnail_enabled:
            return
        self._thumbnail_enabled = enabled
        self._indicator.pack_forget()
        self._indicator.place_forget()
        if enabled:
            self._cover.pack()
            self._indicator.set_size(BADGE_SIZE)
            self._indicator.place(in_=self._cover, relx=1, rely=1, anchor="se")
        else:
            self._cover.pack_forget()
            self._indicator.set_size(INDICATOR_SIZE)
            self._indicator.pack()
        self._title_label.configure(width=self._title_chars(enabled))

    def _title_chars(self, thumbnail_enabled: bool) -> int:
        if not thumbnail_enabled:
            return TITLE_WIDTH_CHARS
        self._title_label.configure(width=TITLE_WIDTH_CHARS)
        full_width = self._title_label.winfo_reqwidth()
        self._title_label.configure(width=TITLE_WIDTH_CHARS - 1)
        char_pixels = full_width - self._title_label.winfo_reqwidth()
        return TITLE_WIDTH_CHARS - math.ceil((THUMBNAIL_WIDTH - INDICATOR_SIZE) / char_pixels)

    def set_visible(self, visible: bool) -> None:
        self._indicator.set_visible(visible)

    def show_state(self, state: PlaybackState, detail: str) -> None:
        self._indicator.set_state(state)
        self._detail.set(detail)
