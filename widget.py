import time
import tkinter as tk
from dataclasses import replace
from typing import Callable

import texts
import theme
from autostart import Autostart
from cache_jobs import CacheJobs
from components import clamp_ratio
from controls_bar import ControlActions, ControlsBar
from history import History
from media import SEARCH_PREFIX, display_name, format_time, is_resolvable, shorten, video_id
from now_playing import NowPlayingHeader
from placement import WindowPlacement
from playback import EMPTY_SNAPSHOT, LoadTracker, PlaybackState, QueueSnapshot, take_snapshot, upcoming
from player import PlaybackStatus, Player, PlayerError, QueueItem
from playlist_panel import PlaylistEvents, PlaylistPanel
from playlists import FAVORITES, PlaylistLibrary
from prefetch import Prefetcher
from recommendations import Autoplay, Recommendation, pick_recommendations, queue_ended
from repeat import RepeatMode, next_repeat
from resolver import BackgroundResolver
from search_bar import SearchBar
from session_lists import HistoryList, QueueList
from settings import CloseAction, GlassStyle, Settings, SettingsStore
from settings_panel import SettingsPanel
from song_actions import SongActions
from song_cache import SongCache, configured_folder, limit_bytes
from song_downloads import SongDownloads
from song_menu import MenuContext, SongMenu, SongMenuActions
from thumbnail_view import decode_thumbnail
from thumbnails import ThumbnailFeed, ThumbnailLoader
from tabs import Tabs
from track import ResolvedTrack, Track
from window_style import apply_glass, is_covered, monitor_work_area, round_corners, work_area

POLL_INTERVAL_MS = 500
RESTART_RETRY_INTERVAL_MS = 3000
WINDOW_MARGIN = 12
TITLE_PREVIEW_LENGTH = 28
NAME_PREVIEW_LENGTH = 24
ACTIVE_STATES = {PlaybackState.PLAYING, PlaybackState.LOADING}
SETTLED_STATES = {PlaybackState.PLAYING, PlaybackState.PAUSED}
STOPPED_STATES = {PlaybackState.IDLE, PlaybackState.FAILED}


class PlayerWidget:
    def __init__(
        self,
        root: tk.Tk,
        player: Player,
        history: History,
        library: PlaylistLibrary,
        resolver: BackgroundResolver,
        prefetcher: Prefetcher,
        settings: Settings,
        settings_store: SettingsStore,
        autostart: Autostart,
        cache: SongCache,
        downloads: SongDownloads,
        cache_jobs: CacheJobs,
        autoplay: Autoplay,
        thumbnail_loader: ThumbnailLoader,
        on_quit: Callable[[], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._root = root
        self._player = player
        self._history = history
        self._library = library
        self._resolver = resolver
        self._prefetcher = prefetcher
        self._settings = settings
        self._settings_store = settings_store
        self._autostart = autostart
        self._cache = cache
        self._downloads = downloads
        self._cache_jobs = cache_jobs
        self._autoplay = autoplay
        self._thumbnail_loader = thumbnail_loader
        self._on_quit = on_quit
        self._playing_playlist: str | None = None
        self._paused_playing_playlist: str | None = None
        self._history_error_shown = False
        self._last_recorded: tuple[str | None, str] | None = None
        self._now: Track | None = None
        self._last_played: Track | None = None
        self._state = PlaybackState.IDLE
        self._clock = clock
        self._load_tracker = LoadTracker()
        self._duration: float | None = None
        self._snapshot = EMPTY_SNAPSHOT
        self._pending_seek: float | None = None
        self._commanded = False
        self._queue_ended = False
        self._page_urls: dict[str, str] = {}
        self._synced_favorites: tuple[str, ...] | None = None
        theme.select(settings.theme)
        self._configure_window()
        self._placement = WindowPlacement(root)
        self._build_header()
        self._build_controls()
        self._build_search()
        self._build_song_tools()
        self._build_panel()
        round_corners(self._root)
        self._apply_settings()
        self._dock_near_tray()
        if self._library.load_warning:
            self._status.show(self._library.load_warning, "error", pinned=True)
        self._poll()

    def toggle_visibility(self) -> None:
        if self._root.state() == "withdrawn" or is_covered(self._root):
            self.show()
        else:
            self._hide()

    def show(self) -> None:
        if self._root.state() == "withdrawn":
            self._root.deiconify()
            self._header.set_visible(True)
        self._placement.bring_to_front()
        self._root.focus_force()
        self._search.focus_input()

    def play_pause(self) -> None:
        if self._state in STOPPED_STATES:
            self._replay()
        else:
            self._run(self._player.toggle_pause)

    def next_track(self) -> None:
        self._run(self._player.next)

    def previous_track(self) -> None:
        self._run(self._player.previous)

    def _replay(self) -> None:
        uris = list(self._snapshot.uris)
        last = self._last_played
        if uris:
            self._begin_playback(lambda: self._player.play_all(uris, 0))
        elif last:
            self._begin_playback(lambda: self._player.load(last.uri))
        else:
            self._status.show(texts.NOTHING_TO_PLAY)

    def _cycle_repeat(self) -> None:
        mode = next_repeat(self._settings.repeat_mode)
        if self._run(lambda: self._player.set_repeat(mode)):
            self._controls.set_repeat(mode)
            self._settings_panel.show_repeat(mode)
            self._change_settings(repeat_mode=mode)

    def _hide(self) -> None:
        self._root.withdraw()
        self._header.set_visible(False)

    def _close(self) -> None:
        if self._settings.close_action is CloseAction.QUIT:
            self._on_quit()
        else:
            self._hide()

    def _close_tooltip(self) -> str:
        return texts.CLOSE_TOOLTIPS[self._settings.close_action]

    def _dock_near_tray(self) -> None:
        self._root.update_idletasks()
        _, _, right, bottom = work_area()
        x = right - self._root.winfo_reqwidth() - WINDOW_MARGIN
        y = bottom - self._root.winfo_reqheight() - WINDOW_MARGIN
        self._root.geometry(f"+{x}+{y}")

    def _configure_window(self) -> None:
        self._root.title(texts.APP_TITLE)
        self._root.overrideredirect(True)
        self._root.configure(padx=14, pady=12, highlightthickness=1)
        theme.bind(self._root, bg="background", highlightbackground="border")

    def _apply_theme(self) -> None:
        if theme.current().name is not self._settings.theme:
            theme.select(self._settings.theme)
            self._reanchor()

    def _apply_settings(self) -> None:
        self._apply_theme()
        self._placement.apply(self._settings.window_position)
        apply_glass(self._root, theme.glass_tint(self._settings.glass_opacity), self._active_glass_style())
        self._header.set_thumbnail_enabled(self._settings.show_thumbnail)
        self._prefetcher.depth = self._settings.prefetch_count
        self._downloads.quality = self._settings.cache_quality
        self._apply_cache_settings()

    def _apply_cache_settings(self) -> None:
        settings = self._settings
        try:
            self._cache.configure(settings.cache_enabled, configured_folder(settings.cache_folder), limit_bytes(settings.cache_limit_gb))
        except OSError:
            self._status.show(texts.CACHE_UPDATE_FAILED, "error")

    def _show_download_failed(self) -> None:
        self._status.show(texts.CACHE_DOWNLOAD_FAILED, "error")

    def _show_favorites_no_space(self) -> None:
        self._status.show(texts.FAVORITES_NO_SPACE, "error")

    def _active_glass_style(self) -> GlassStyle | None:
        return self._settings.glass_style if self._settings.glass else None

    def _preview_opacity(self, opacity: int) -> None:
        if self._settings.glass:
            apply_glass(self._root, theme.glass_tint(opacity), self._settings.glass_style)

    def _change_settings(self, **changes: object) -> None:
        self._settings = replace(self._settings, **changes)
        self._apply_settings()
        try:
            self._settings_store.save(self._settings)
        except OSError:
            self._status.show(texts.SETTINGS_SAVE_FAILED, "error")

    def _build_header(self) -> None:
        self._header = NowPlayingHeader(self._root, self._close, self._close_tooltip, self._open_now_playing_menu, self._toggle_now_playing_favorite, self._seek_to)
        self._header.pack(fill="x")
        self._thumbnails = ThumbnailFeed(self._thumbnail_loader, decode_thumbnail, self._header.show_thumbnail)

    def _build_controls(self) -> None:
        actions = ControlActions(
            previous=self.previous_track,
            toggle=self.play_pause,
            next=self.next_track,
            cycle_repeat=self._cycle_repeat,
            toggle_panel=self._toggle_panel,
            set_volume=lambda volume: self._run(lambda: self._player.set_volume(volume)),
        )
        self._controls = ControlsBar(self._root, self._settings.startup_volume, self._settings.repeat_mode, actions)
        self._controls.pack(fill="x")

    def _build_search(self) -> None:
        self._search = SearchBar(self._root, self._play_uri, self._enqueue_uri)
        self._search.pack(fill="x")
        self._status = self._search.status

    def _build_song_tools(self) -> None:
        self._actions = SongActions(
            self._player,
            self._library,
            self._status,
            self._begin_playback,
            self._start_loading,
            self._run,
            self._playlist_changed,
            self._request_new_playlist,
        )
        menu_actions = SongMenuActions(
            self._actions.play_now, self._actions.play_next, self._actions.enqueue, self._actions.set_membership, self._actions.new_playlist, self._set_favorite
        )
        self._song_menu = SongMenu(self._root, self._library, menu_actions)

    def _build_panel(self) -> None:
        self._panel = tk.Frame(self._root, pady=12)
        theme.bind(self._panel, bg="background")
        self._tabs = Tabs(self._panel, on_change=self._on_tab_change)
        self._tabs.pack(fill="x")
        self._tabs.add(texts.QUEUE_TAB, self._build_queue)
        self._tabs.add(texts.HISTORY_TAB, self._build_history)
        self._tabs.add(texts.PLAYLISTS_TAB, self._build_playlists)
        self._tabs.add(texts.SETTINGS_TAB, self._build_settings)
        self._tabs.select(texts.QUEUE_TAB)

    def _build_queue(self, parent: tk.Misc) -> tk.Widget:
        self._queue_list = QueueList(parent, self._player, self._song_menu, self._status, self._begin_playback, self._run, self._cache.is_stored, self._autoplay.is_suggested)
        return self._queue_list

    def _build_history(self, parent: tk.Misc) -> tk.Widget:
        self._history_list = HistoryList(parent, self._history, self._song_menu, self._status, self._actions.play_now, self._cache.is_stored)
        return self._history_list

    def _build_playlists(self, parent: tk.Misc) -> tk.Widget:
        events = PlaylistEvents(
            self._play_playlist, self._forget_deleted_playlist, self._remember_restored_playlist, self._playlist_changed, self._reanchor
        )
        self._playlist_panel = PlaylistPanel(parent, self._library, self._status, self._song_menu, events, self._cache.is_stored)
        return self._playlist_panel

    def _build_settings(self, parent: tk.Misc) -> tk.Widget:
        self._settings_panel = SettingsPanel(
            parent, self._settings, self._autostart, self._status, self._change_settings, self._clear_history, self._preview_opacity, self._cache, self._cache_jobs
        )
        return self._settings_panel

    def _on_tab_change(self, name: str) -> None:
        if name != texts.PLAYLISTS_TAB:
            self._playlist_panel.cancel_awaiting()
        self._reanchor()

    def _open_tab(self, index: int) -> None:
        if not self._panel.winfo_ismapped():
            self._toggle_panel()
        self._tabs.select(self._tabs.names[index])

    def _request_new_playlist(self, track: Track) -> None:
        self._open_tab(self._tabs.names.index(texts.PLAYLISTS_TAB))
        self._playlist_panel.await_new_playlist(track)

    def _open_now_playing_menu(self, x: int, y: int) -> None:
        if self._now:
            self._song_menu.open(x, y, self._now, MenuContext(now_playing=True))
        else:
            self._status.show(texts.NOTHING_PLAYING_YET)

    def _toggle_now_playing_favorite(self) -> None:
        if self._now:
            self._set_favorite(self._now, not self._library.is_favorite(self._now.uri))
        else:
            self._status.show(texts.NOTHING_PLAYING_YET)

    def _set_favorite(self, track: Track, liked: bool) -> None:
        page_url = self._page_urls.get(track.uri)
        if liked and track.uri.startswith(SEARCH_PREFIX) and not page_url:
            self._resolver.submit(track.uri, lambda resolved: self._like_resolved(track, resolved))
        else:
            self._actions.set_membership(FAVORITES, Track(track.title, page_url or track.uri), liked)

    def _like_resolved(self, track: Track, resolved: ResolvedTrack | None) -> None:
        if resolved is None:
            self._status.show(texts.not_found(display_name(None, track.uri)[:TITLE_PREVIEW_LENGTH]), "error")
            return
        self._page_urls[track.uri] = resolved.page_url
        if not self._library.is_favorite(resolved.page_url):
            self._actions.set_membership(FAVORITES, Track(resolved.title, resolved.page_url), True)

    def _sync_favorites(self) -> None:
        tracks = self._library.tracks(FAVORITES)
        uris = tuple(track.uri for track in tracks)
        if uris == self._synced_favorites:
            return
        self._synced_favorites = uris
        self._cache.set_favorites({song_id for uri in uris if (song_id := video_id(uri))})
        for track in tracks:
            self._downloads.request(track.uri, track.title)

    def _playlist_changed(self, name: str, track: Track | None) -> None:
        self._sync_favorites()
        self._header.show_favorite(self._is_now_favorite())
        if track:
            self._sync_added_track(name, track)
        self._playlist_panel.refresh()
        if track:
            self._playlist_panel.reveal_last()

    def _sync_added_track(self, name: str, track: Track) -> None:
        if name == self._playing_playlist:
            self._run(lambda: self._player.enqueue(track.uri))
        needs_resolving = track.uri.startswith(SEARCH_PREFIX) or (is_resolvable(track.uri) and track.title == display_name(None, track.uri))
        if needs_resolving:
            self._playlist_panel.mark_pending(track.uri)
            self._resolver.submit(track.uri, lambda resolved: self._store_resolved(track.uri, resolved))
        else:
            self._downloads.request(track.uri, track.title)

    def _store_resolved(self, uri: str, resolved: ResolvedTrack | None) -> None:
        self._playlist_panel.clear_pending(uri)
        if resolved is None:
            self._playlist_panel.refresh()
            self._status.show(texts.not_found(display_name(None, uri)[:TITLE_PREVIEW_LENGTH]), "error")
            return
        try:
            self._library.replace(uri, Track(resolved.title, resolved.page_url))
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
        self._playlist_panel.refresh()
        self._downloads.request(resolved.page_url, resolved.title)

    def _forget_deleted_playlist(self, name: str) -> None:
        if name == self._playing_playlist:
            self._paused_playing_playlist = name
            self._playing_playlist = None

    def _remember_restored_playlist(self, name: str) -> None:
        if name == self._paused_playing_playlist:
            self._playing_playlist = name
        self._paused_playing_playlist = None

    def _toggle_panel(self) -> None:
        if self._panel.winfo_ismapped():
            self._playlist_panel.cancel_awaiting()
            self._panel.pack_forget()
        else:
            self._panel.pack(fill="x")
        self._reanchor()

    def _reanchor(self) -> None:
        if not self._root.winfo_viewable():
            return
        top = self._root.winfo_y()
        bottom = top + self._root.winfo_height()
        self._root.update_idletasks()
        left, area_top, right, area_bottom = monitor_work_area(self._root)
        width, height = self._root.winfo_reqwidth(), self._root.winfo_reqheight()
        docked_low = bottom > (area_top + area_bottom) // 2
        y = max(area_top, min(bottom - height if docked_low else top, area_bottom - height))
        x = max(left, min(self._root.winfo_x(), right - width))
        self._root.geometry(f"+{x}+{y}")

    def _play_uri(self, uri: str) -> bool:
        return self._begin_playback(lambda: self._player.load(uri))

    def _enqueue_uri(self, uri: str) -> bool:
        started = self._start_loading(lambda: self._player.enqueue(uri))
        if started:
            self._status.show(texts.ADDED_TO_QUEUE)
        return started

    def _play_playlist(self, name: str, start: int) -> None:
        uris = [track.uri for track in self._library.tracks(name)]
        previous = EMPTY_SNAPSHOT if self._state in STOPPED_STATES else self._snapshot
        if self._begin_playback(lambda: self._player.play_all(uris, start), name):
            self._status.show_undoable(texts.playing_playlist(shorten(name, NAME_PREVIEW_LENGTH)), lambda: self._restore_queue(previous))

    def _restore_queue(self, snapshot: QueueSnapshot) -> bool:
        uris = list(snapshot.uris)
        if not uris:
            self._playing_playlist = None
            return self._run(lambda: self._player.play_all([], 0))
        if not self._begin_playback(lambda: self._player.play_all(uris, snapshot.index), snapshot.playlist):
            return False
        self._pending_seek = snapshot.position
        return True

    def _clear_history(self) -> None:
        try:
            previous = self._history.clear()
        except OSError:
            self._status.show(texts.HISTORY_SAVE_FAILED, "error")
            return
        self._history_list.refresh()
        self._status.show_undoable(texts.HISTORY_CLEARED, lambda: self._restore_history(previous))

    def _restore_history(self, entries: tuple[Track, ...]) -> None:
        try:
            self._history.restore(entries)
        except OSError:
            self._status.show(texts.HISTORY_SAVE_FAILED, "error")
            return
        self._history_list.refresh()

    def _seek_to(self, ratio: float) -> None:
        if self._duration:
            duration = self._duration
            self._run(lambda: self._player.seek(duration * ratio))

    def _begin_playback(self, action: Callable[[], None], playlist: str | None = None) -> bool:
        self._pending_seek = None
        started = self._start_loading(action)
        if started:
            self._playing_playlist = playlist
        return started

    def _start_loading(self, action: Callable[[], None]) -> bool:
        self._show_loading()
        return self._run(action)

    def _show_loading(self) -> None:
        self._load_tracker.request(self._clock())
        self._header.show_state(PlaybackState.LOADING, texts.STATE_MESSAGES[PlaybackState.LOADING])

    def _run(self, action: Callable[[], None]) -> bool:
        self._commanded = True
        return self._execute(action)

    def _execute(self, action: Callable[[], None]) -> bool:
        try:
            action()
        except PlayerError:
            self._show_stopped()
            return False
        return True

    def _poll(self) -> None:
        delay = POLL_INTERVAL_MS
        try:
            self._tick()
        except PlayerError:
            delay = self._recover_player()
        finally:
            self._root.after(delay, self._poll)

    def _tick(self) -> None:
        self._resolver.deliver()
        self._downloads.deliver(self._show_download_failed, self._show_favorites_no_space)
        self._sync_favorites()
        self._cache_jobs.deliver()
        self._thumbnails.deliver()
        observation = self._player.observe()
        status, queue = observation.status, observation.queue
        self._cache.playing_file = status.local_file
        self._relocate_cached_songs()
        self._prefetcher.update(queue, self._wraps_queue())
        state = self._load_tracker.state(status, self._clock())
        self._queue_ended = queue_ended(was_ended=self._queue_ended, previous=self._state, state=state, user_acted=self._commanded)
        self._commanded = False
        self._state = state
        if state in STOPPED_STATES:
            self._playing_playlist = None
        self._snapshot = take_snapshot(queue, status.position, self._playing_playlist)
        self._render(status, state, queue)
        self._apply_pending_seek(status, state)
        if state is PlaybackState.PLAYING:
            self._remember(status)
            self._autoplay.played(status.path or "")
        seed = self._autoplay_seed()
        self._autoplay.follow(seed)
        self._autoplay.deliver(self._enqueue_recommendations, self._show_autoplay_unavailable)
        self._request_recommendations(state, queue, seed)

    def _autoplay_seed(self) -> str | None:
        return video_id(self._last_played.uri) if self._last_played else None

    def _request_recommendations(self, state: PlaybackState, queue: list[QueueItem], seed: str | None) -> None:
        if seed and self._autoplay.wants(self._settings.autoplay, self._settings.repeat_mode, state, len(upcoming(queue)), self._queue_ended, seed):
            self._autoplay.request(seed)

    def _enqueue_recommendations(self, seed_id: str, candidates: list[Recommendation]) -> None:
        if not self._settings.autoplay or self._settings.repeat_mode is not RepeatMode.OFF:
            return
        if self._state is PlaybackState.IDLE and not self._queue_ended:
            return
        known_uris = (*self._snapshot.uris, *(entry.uri for entry in self._history.entries))
        excluded = {song_id for uri in known_uris if (song_id := video_id(uri))}
        tracks = [recommendation.track for recommendation in pick_recommendations(candidates, seed_id, excluded)]
        if not tracks:
            return
        self._autoplay.remember(tracks)
        if self._state is PlaybackState.IDLE:
            self._show_loading()
        self._execute(lambda: self._enqueue_all([track.uri for track in tracks]))

    def _enqueue_all(self, uris: list[str]) -> None:
        for uri in uris:
            self._player.enqueue(uri)

    def _show_autoplay_unavailable(self) -> None:
        self._status.show(texts.AUTOPLAY_UNAVAILABLE)

    def _wraps_queue(self) -> bool:
        return self._settings.repeat_mode is RepeatMode.QUEUE

    def _relocate_cached_songs(self) -> None:
        changes = self._cache.take_relocations()
        if changes:
            self._player.relocate_local(changes)
            self._prefetcher.reset()

    def _apply_pending_seek(self, status: PlaybackStatus, state: PlaybackState) -> None:
        position = self._pending_seek
        if position is None:
            return
        if state is PlaybackState.FAILED:
            self._pending_seek = None
        elif state in SETTLED_STATES and status.duration:
            self._pending_seek = None
            self._execute(lambda: self._player.seek(position))

    def _recover_player(self) -> int:
        snapshot = self._snapshot
        try:
            self._player.restart()
        except PlayerError:
            self._show_stopped()
            self._status.show(texts.RESTART_FAILED, "error")
            return RESTART_RETRY_INTERVAL_MS
        self._prefetcher.reset()
        self._playing_playlist = None
        self._pending_seek = None
        self._commanded = True
        if not snapshot.uris:
            self._status.show(texts.PLAYER_RESTARTED)
        elif self._restore_queue(snapshot):
            self._status.show(texts.PLAYER_RESTARTED_QUEUE_RESTORED)
        else:
            self._status.show(texts.PLAYER_RESTARTED_QUEUE_LOST, "error")
        return POLL_INTERVAL_MS

    def _render(self, status: PlaybackStatus, state: PlaybackState, queue: list[QueueItem]) -> None:
        title = display_name(status.title, status.path) if status.path else texts.NOTHING_PLAYING
        path = self._page_url(status.path)
        self._now = Track(title, path) if path else None
        self._last_played = self._now or self._last_played
        self._duration = status.duration
        has_progress = status.position is not None and bool(status.duration)
        ratio = clamp_ratio(status.position / status.duration) if has_progress else 0.0
        downloaded = bool(path) and self._cache.is_stored(path)
        self._thumbnails.select(self._thumbnail_id(path))
        self._header.render(state, title, self._detail_text(status, state), ratio, downloaded)
        self._header.show_favorite(self._is_now_favorite())
        self._controls.set_playing(state in ACTIVE_STATES)
        known_titles = self._known_titles()
        self._queue_list.show([(index, Track(display_name(item.title or known_titles.get(item.uri), item.uri), item.uri)) for index, item in upcoming(queue, self._wraps_queue())])
        self._history_list.refresh()
        self._queue_list.refresh_markers()
        self._history_list.refresh_markers()
        self._playlist_panel.refresh_markers()

    def _is_now_favorite(self) -> bool:
        return self._now is not None and self._library.is_favorite(self._now.uri)

    def _page_url(self, path: str | None) -> str | None:
        return self._page_urls.get(path, path) if path else None

    def _thumbnail_id(self, path: str | None) -> str | None:
        return video_id(path) if path and self._settings.show_thumbnail else None

    def _known_titles(self) -> dict[str, str]:
        playlist_tracks = self._library.tracks(self._playing_playlist) if self._playing_playlist else ()
        known = {track.uri: track.title for track in (*self._history.entries, *playlist_tracks)}
        return {**self._autoplay.titles, **known}

    def _detail_text(self, status: PlaybackStatus, state: PlaybackState) -> str:
        elapsed = f"{format_time(status.position)} / {format_time(status.duration)}"
        if state is PlaybackState.PLAYING:
            return elapsed
        if state is PlaybackState.PAUSED:
            return texts.paused(elapsed)
        return texts.STATE_MESSAGES[state]

    def _remember(self, status: PlaybackStatus) -> None:
        if not status.path:
            return
        path = status.path
        title = display_name(status.title, path)
        if self._last_recorded == (title, path):
            return
        if path.startswith(SEARCH_PREFIX):
            self._last_recorded = (title, path)
            self._page_urls.pop(path, None)
            self._resolver.submit(path, lambda resolved: self._record_search(path, title, resolved))
        elif self._record(Track(title, path)):
            self._last_recorded = (title, path)

    def _record_search(self, path: str, title: str, resolved: ResolvedTrack | None) -> None:
        if resolved:
            self._page_urls[path] = resolved.page_url
        self._record(Track(title, resolved.page_url if resolved else path))

    def _record(self, track: Track) -> bool:
        try:
            self._history.record(track)
        except OSError:
            if not self._history_error_shown:
                self._status.show(texts.HISTORY_SAVE_FAILED, "error")
            self._history_error_shown = True
            return False
        self._history_error_shown = False
        self._downloads.request(track.uri, track.title)
        return True

    def _show_stopped(self) -> None:
        self._header.show_state(PlaybackState.FAILED, texts.PLAYER_STOPPED)
