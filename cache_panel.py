import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import texts
import theme
from cache_jobs import CacheJobs, CacheTask
from components import StatusLine, TextButton, Tooltip
from media import shorten
from settings import CACHE_LIMITS_GB, CacheQuality, Settings
from settings_rows import ChoiceMenu, RowBuilder
from song_cache import CacheReport, SongCache, limit_bytes
from storage import DriveSpaceReader, used_percent, used_ratio
from storage_bar import StorageBar

FOLDER_PREVIEW_LENGTH = 26
USAGE_REFRESH_MS = 2000

LIMIT_LABELS = {limit: texts.gigabytes(limit) for limit in CACHE_LIMITS_GB}
QUALITY_LABELS = {CacheQuality.MAX: texts.CACHE_QUALITY_MAX, CacheQuality.MEDIUM: texts.CACHE_QUALITY_MEDIUM}


class CachePanel:
    def __init__(
        self,
        rows: RowBuilder,
        settings: Settings,
        status: StatusLine,
        cache: SongCache,
        jobs: CacheJobs,
        update: Callable[..., None],
        drive_space: DriveSpaceReader | None = None,
    ) -> None:
        self._status = status
        self._cache = cache
        self._jobs = jobs
        self._update = update
        self._drive_space = drive_space or DriveSpaceReader()
        self._limit_gb = settings.cache_limit_gb
        rows.toggle(texts.CACHE_ENABLED, settings.cache_enabled, lambda value: update(cache_enabled=value))
        self._build_folder(rows)
        ChoiceMenu(rows.row(texts.CACHE_LIMIT), LIMIT_LABELS, settings.cache_limit_gb, self._set_limit).pack(side="right")
        ChoiceMenu(rows.row(texts.CACHE_QUALITY), QUALITY_LABELS, settings.cache_quality, lambda value: update(cache_quality=value)).pack(side="right")
        self._build_usage(rows)

    def _build_folder(self, rows: RowBuilder) -> None:
        row = rows.row(texts.CACHE_FOLDER)
        TextButton(row, texts.CACHE_CHANGE_FOLDER, self._change_folder, tooltip=texts.CACHE_CHANGE_FOLDER_TOOLTIP).pack(side="right")
        self._folder_label = tk.Label(row, font=theme.SMALL_FONT)
        theme.bind(self._folder_label, bg="surface", fg="muted")
        self._folder_label.pack(side="right", padx=(0, 8))
        Tooltip(self._folder_label, lambda: str(self._cache.folder))
        self._show_folder()

    def _build_usage(self, rows: RowBuilder) -> None:
        row = rows.row()
        TextButton(row, texts.CACHE_CLEAR, self._clear, tooltip=texts.CACHE_CLEAR_TOOLTIP, variant="danger").pack(side="right")
        self._usage_label = tk.Label(row, font=theme.SMALL_FONT)
        theme.bind(self._usage_label, bg="surface", fg="muted")
        self._usage_label.pack(side="left")
        self._storage_bar = StorageBar(rows.row())
        self._storage_bar.pack(fill="x", expand=True)
        self._free_label = tk.Label(rows.row(), font=theme.SMALL_FONT)
        theme.bind(self._free_label, bg="surface", fg="muted")
        self._free_label.pack(side="left")
        self._usage_label.bind("<Map>", lambda _event: self._refresh_usage(reschedule=False))
        self._refresh_usage()

    def _show_folder(self) -> None:
        self._folder_label.configure(text=shorten(str(self._cache.folder), FOLDER_PREVIEW_LENGTH))

    def _set_limit(self, limit_gb: float) -> None:
        self._limit_gb = limit_gb
        self._update(cache_limit_gb=limit_gb)
        self._refresh_usage(reschedule=False)

    def _refresh_usage(self, reschedule: bool = True) -> None:
        if self._usage_label.winfo_viewable():
            self._show_usage()
        if reschedule:
            self._usage_label.after(USAGE_REFRESH_MS, self._refresh_usage)

    def _show_usage(self) -> None:
        usage = self._cache.usage()
        ratio = used_ratio(usage.bytes_used, limit_bytes(self._limit_gb))
        space = self._drive_space.read(self._cache.folder)
        low_space = bool(space and space.is_low)
        self._usage_label.configure(text=texts.cache_usage(usage.bytes_used, self._limit_gb, usage.songs))
        self._storage_bar.show(ratio, texts.cache_usage_tooltip(usage.bytes_used, self._limit_gb, used_percent(ratio)), low_space)
        self._free_label.configure(text=texts.drive_free(space.free_bytes, space.drive, low_space) if space else "")

    def _change_folder(self) -> None:
        if self._is_busy():
            return
        chosen = filedialog.askdirectory(initialdir=str(self._cache.folder), title=texts.CACHE_PICK_FOLDER, parent=self._usage_label.winfo_toplevel())
        if not chosen or Path(chosen) == self._cache.folder:
            return
        destination = Path(chosen)
        songs = self._cache.usage().songs
        move = False
        if songs:
            answer = messagebox.askyesnocancel(texts.APP_TITLE, texts.cache_move_question(songs), parent=self._usage_label.winfo_toplevel())
            if answer is None:
                return
            move = answer
        if move:
            self._start(lambda stop: self._cache.move_to(destination, stop), texts.CACHE_MOVING, lambda report: self._moved(destination, report))
        else:
            self._use_folder(destination)

    def _use_folder(self, destination: Path) -> None:
        self._update(cache_folder=str(destination))
        self._show_folder()
        self._refresh_usage(reschedule=False)

    def _moved(self, destination: Path, report: CacheReport | None) -> None:
        if report is None:
            self._status.show(texts.CACHE_MOVE_FAILED, "error")
            self._refresh_usage(reschedule=False)
            return
        self._use_folder(destination)
        self._status.show(texts.CACHE_MOVED_KEEPING_PLAYING if report.kept_playing else texts.CACHE_MOVED)

    def _clear(self) -> None:
        songs = self._cache.usage().songs
        if self._is_busy() or not songs or not messagebox.askyesno(texts.APP_TITLE, texts.cache_clear_question(songs), parent=self._usage_label.winfo_toplevel()):
            return
        self._start(self._cache.clear, texts.CACHE_CLEARING, self._cleared)

    def _cleared(self, report: CacheReport | None) -> None:
        if report is None or report.failed:
            self._status.show(texts.CACHE_CLEAR_FAILED, "error")
        else:
            self._status.show(texts.CACHE_CLEARED_KEEPING_PLAYING if report.kept_playing else texts.CACHE_CLEARED)
        self._refresh_usage(reschedule=False)

    def _is_busy(self) -> bool:
        if self._jobs.busy:
            self._status.show(texts.CACHE_BUSY, "error")
        return self._jobs.busy

    def _start(self, task: CacheTask, message: str, on_finished: Callable[[CacheReport | None], None]) -> None:
        self._status.show(message)
        self._jobs.submit(task, on_finished)
