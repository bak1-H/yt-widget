import tkinter as tk
from dataclasses import replace
from typing import Callable

import texts
import theme
from autostart import Autostart
from cache_jobs import CacheJobs
from cache_panel import CachePanel
from components import SliderBar, StatusLine, TextButton, Tooltip
from scroll_area import ScrollArea
from settings import MAX_GLASS_OPACITY, MAX_PREFETCH, MIN_GLASS_OPACITY, CloseAction, Settings, WindowPosition
from repeat import RepeatMode
from settings_rows import ChoiceMenu, RowBuilder
from song_cache import SongCache

PANEL_HEIGHT = 230
VOLUME_SLIDER_LENGTH = 120
VOLUME_SAVE_DELAY_MS = 400
OPACITY_SLIDER_LENGTH = 120

POSITION_LABELS = {
    WindowPosition.TOPMOST: texts.POSITION_TOPMOST,
    WindowPosition.NORMAL: texts.POSITION_NORMAL,
    WindowPosition.DESKTOP: texts.POSITION_DESKTOP,
}
CLOSE_LABELS = {CloseAction.HIDE: texts.CLOSE_HIDE, CloseAction.QUIT: texts.CLOSE_QUIT}
PREFETCH_LABELS = {count: texts.prefetch_option(count) for count in range(MAX_PREFETCH + 1)}


class SettingsPanel(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        settings: Settings,
        autostart: Autostart,
        status: StatusLine,
        on_change: Callable[..., None],
        on_clear_history: Callable[[], None],
        on_preview_opacity: Callable[[int], None],
        cache: SongCache,
        jobs: CacheJobs,
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._settings = settings
        self._autostart = autostart
        self._status = status
        self._on_change = on_change
        self._on_preview_opacity = on_preview_opacity
        self._save_job: str | None = None
        self._opacity_save_job: str | None = None
        area = ScrollArea(self, height=PANEL_HEIGHT)
        area.pack(fill="x")
        self._body = area.body
        self._rows = RowBuilder(self._body)
        self._build_theme()
        self._build_autostart()
        self._build_position()
        self._rows.toggle(texts.GLASS, settings.glass, self._on_glass)
        self._build_glass_style()
        self._rows.toggle(
            texts.SHOW_THUMBNAIL, settings.show_thumbnail, lambda enabled: self._update(show_thumbnail=enabled), tooltip=texts.SHOW_THUMBNAIL_TOOLTIP
        )
        self._build_opacity()
        self._build_volume()
        self._build_close_action()
        self._build_prefetch()
        self._build_autoplay(settings)
        CachePanel(self._rows, settings, status, cache, jobs, self._update)
        self._build_clear_history(on_clear_history)
        area.forward_wheel(*(widget for widget in self._descendants(self._body) if not isinstance(widget, SliderBar)))

    def _descendants(self, widget: tk.Misc) -> list[tk.Misc]:
        return [descendant for child in widget.winfo_children() for descendant in (child, *self._descendants(child))]

    def _build_theme(self) -> None:
        row = self._rows.row(texts.THEME)
        ChoiceMenu(row, texts.THEME_LABELS, self._settings.theme, lambda value: self._update(theme=value)).pack(side="right")

    def _build_autostart(self) -> None:
        self._autostart_value = self._rows.toggle(texts.AUTOSTART, self._autostart.is_enabled(), self._set_autostart)

    def _set_autostart(self, enabled: bool) -> None:
        try:
            self._autostart.set_enabled(enabled)
        except OSError:
            self._status.show(texts.AUTOSTART_FAILED, "error")
        self._autostart_value.set(self._autostart.is_enabled())

    def _build_position(self) -> None:
        row = self._rows.row(texts.WINDOW_POSITION)
        ChoiceMenu(row, POSITION_LABELS, self._settings.window_position, lambda value: self._update(window_position=value)).pack(side="right")

    def _build_volume(self) -> None:
        row = self._rows.row(texts.STARTUP_VOLUME)
        self._volume_label = tk.Label(row, text=str(self._settings.startup_volume), width=4, font=theme.TEXT_FONT)
        theme.bind(self._volume_label, bg="surface", fg="muted")
        self._volume_label.pack(side="right")
        slider = SliderBar(row, on_change=self._on_volume, width=VOLUME_SLIDER_LENGTH, show_knob=True, wheel=True, background="surface")
        slider.set_ratio(self._settings.startup_volume / 100)
        slider.pack(side="right")

    def _on_volume(self, ratio: float) -> None:
        volume = round(ratio * 100)
        self._volume_label.configure(text=str(volume))
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(VOLUME_SAVE_DELAY_MS, lambda: self._update(startup_volume=volume))

    def _build_glass_style(self) -> None:
        row = self._rows.row(texts.GLASS_STYLE)
        self._glass_style_menu = ChoiceMenu(row, texts.GLASS_STYLE_LABELS, self._settings.glass_style, lambda value: self._update(glass_style=value))
        self._glass_style_menu.pack(side="right")
        self._glass_style_hint = tk.Label(row, text=texts.GLASS_REQUIRED, font=theme.SMALL_FONT)
        theme.bind(self._glass_style_hint, bg="surface", fg="muted")
        self._show_glass_style_enabled(self._settings.glass)

    def _show_glass_style_enabled(self, enabled: bool) -> None:
        self._glass_style_menu.set_enabled(enabled)
        if enabled:
            self._glass_style_hint.pack_forget()
        else:
            self._glass_style_hint.pack(side="right", padx=(0, 8))

    def _on_glass(self, enabled: bool) -> None:
        self._show_glass_style_enabled(enabled)
        self._show_opacity_enabled(enabled)
        self._update(glass=enabled)

    def _build_opacity(self) -> None:
        row = self._rows.row(texts.GLASS_OPACITY)
        self._opacity_label = tk.Label(row, text=f"{self._settings.glass_opacity}%", width=5, font=theme.TEXT_FONT)
        theme.bind(self._opacity_label, bg="surface", fg="muted")
        self._opacity_label.pack(side="right")
        self._opacity_hint = tk.Label(row, text=texts.GLASS_REQUIRED, font=theme.SMALL_FONT)
        theme.bind(self._opacity_hint, bg="surface", fg="muted")
        self._opacity_slider = SliderBar(row, on_change=self._on_opacity, width=OPACITY_SLIDER_LENGTH, show_knob=True, wheel=True, background="surface")
        self._opacity_slider.set_ratio(self._opacity_ratio(self._settings.glass_opacity))
        self._opacity_slider.pack(side="right")
        self._show_opacity_enabled(self._settings.glass)

    def _show_opacity_enabled(self, enabled: bool) -> None:
        self._opacity_slider.set_enabled(enabled)
        if enabled:
            self._opacity_hint.pack_forget()
        else:
            self._opacity_hint.pack(side="right", padx=(0, 8))

    def _opacity_ratio(self, opacity: int) -> float:
        return (opacity - MIN_GLASS_OPACITY) / (MAX_GLASS_OPACITY - MIN_GLASS_OPACITY)

    def _on_opacity(self, ratio: float) -> None:
        opacity = MIN_GLASS_OPACITY + round(ratio * (MAX_GLASS_OPACITY - MIN_GLASS_OPACITY))
        self._opacity_label.configure(text=f"{opacity}%")
        self._on_preview_opacity(opacity)
        if self._opacity_save_job:
            self.after_cancel(self._opacity_save_job)
        self._opacity_save_job = self.after(VOLUME_SAVE_DELAY_MS, lambda: self._update(glass_opacity=opacity))

    def _build_close_action(self) -> None:
        row = self._rows.row(texts.CLOSE_ACTION)
        ChoiceMenu(row, CLOSE_LABELS, self._settings.close_action, lambda value: self._update(close_action=value)).pack(side="right")

    def _build_autoplay(self, settings: Settings) -> None:
        row = self._rows.row()
        self._autoplay_note = tk.Label(row, text=texts.AUTOPLAY_NEEDS_NO_REPEAT, font=theme.SMALL_FONT)
        theme.bind(self._autoplay_note, bg="surface", fg="muted")
        self._rows.toggle(texts.AUTOPLAY, settings.autoplay, lambda enabled: self._update(autoplay=enabled), tooltip=texts.AUTOPLAY_TOOLTIP, row=row)
        Tooltip(self._autoplay_note, texts.AUTOPLAY_TOOLTIP)
        self.show_repeat(settings.repeat_mode)

    def show_repeat(self, mode: RepeatMode) -> None:
        if mode is RepeatMode.OFF:
            self._autoplay_note.pack_forget()
        else:
            self._autoplay_note.pack(side="left", padx=(8, 0))

    def _build_prefetch(self) -> None:
        row = self._rows.row(texts.PREFETCH)
        ChoiceMenu(row, PREFETCH_LABELS, self._settings.prefetch_count, lambda value: self._update(prefetch_count=value)).pack(side="right")

    def _build_clear_history(self, on_clear: Callable[[], None]) -> None:
        TextButton(self._rows.row(), texts.CLEAR_HISTORY, on_clear, tooltip=texts.CLEAR_HISTORY_TOOLTIP, variant="danger").pack(side="left")

    def _update(self, **changes: object) -> None:
        self._on_change(**changes)
