import tkinter as tk
from dataclasses import dataclass
from typing import Callable

import texts
import theme
from components import IconButton, SearchEntry, StatusLine, add_focus_ring
from media import display_name, shorten
from playlists import PlaylistExistsError, PlaylistLibrary
from song_menu import SongMenu
from theme import Icon
from track import Track
from song_menu import MenuContext
from track_rows import RowHandlers, RowItem, TrackRows, locate

TRACK_ROWS = 5
PENDING_SUFFIX = " …"
NAME_PREVIEW_LENGTH = 24
TITLE_PREVIEW_LENGTH = 28
AWAITING_TIMEOUT_MS = 60000
HINT_WRAP_PIXELS = 330


@dataclass(frozen=True)
class PlaylistEvents:
    play: Callable[[str, int], None]
    deleted: Callable[[str], None]
    restored: Callable[[str], None]
    track_added: Callable[[str, Track], None]
    resized: Callable[[], None]


class PlaylistPanel(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        library: PlaylistLibrary,
        status: StatusLine,
        song_menu: SongMenu,
        events: PlaylistEvents,
        is_downloaded: Callable[[str], bool],
    ) -> None:
        super().__init__(parent)
        theme.bind(self, bg="background")
        self._library = library
        self._status = status
        self._song_menu = song_menu
        self._events = events
        self._names: list[str] | None = None
        self._selected = ""
        self._pending: set[str] = set()
        self._awaiting: Track | None = None
        self._awaiting_job: str | None = None
        self._offer_message: str | None = None
        self._creating = False
        self._build_hint()
        self._build_selector()
        self._tracks = TrackRows(self, texts.PLAYLIST_EMPTY, RowHandlers(self._play_row, self._open_menu, self._remove_row), is_downloaded, rows=TRACK_ROWS, numbered=True)
        self._tracks.pack(fill="x")
        footer = tk.Label(self, text=texts.PLAYLIST_HINT, font=theme.SMALL_FONT, anchor="w")
        theme.bind(footer, bg="background", fg="muted")
        footer.pack(fill="x", pady=(4, 0))
        self.winfo_toplevel().bind("<ButtonPress-1>", self._on_press, add="+")
        self.refresh()

    @property
    def selected(self) -> str | None:
        return self._selected or None

    def refresh(self, *, keep_view: bool = True) -> None:
        names = self._library.names()
        if names != self._names:
            self._names = names
            self._rebuild_menu()
        self._tracks.show([RowItem(self._row_title(track), track.uri) for track in self._library.tracks(self._selected)], keep_view=keep_view)

    def refresh_markers(self) -> None:
        self._tracks.refresh_markers()

    def mark_pending(self, uri: str) -> None:
        self._pending.add(uri)

    def clear_pending(self, uri: str) -> None:
        self._pending.discard(uri)

    def reveal_last(self) -> None:
        self._tracks.reveal(len(self._library.tracks(self._selected)) - 1)

    def await_new_playlist(self, track: Track) -> None:
        self._take_awaiting()
        self._awaiting = track
        self._awaiting_job = self.after(AWAITING_TIMEOUT_MS, self.cancel_awaiting)
        self._hint.pack(fill="x", pady=(0, 6), before=self._selector)
        self._open_creator()
        self._events.resized()

    def cancel_awaiting(self) -> None:
        if self._take_awaiting():
            if self._offer_message is not None and self._status.message == self._offer_message:
                self._status.clear()
            self._offer_message = None
            self._events.resized()

    def _take_awaiting(self) -> Track | None:
        track, self._awaiting = self._awaiting, None
        if self._awaiting_job:
            self.after_cancel(self._awaiting_job)
            self._awaiting_job = None
        self._hint.pack_forget()
        self._close_creator()
        return track

    def _build_hint(self) -> None:
        self._hint = tk.Frame(self)
        theme.bind(self._hint, bg="background")
        message = tk.Label(self._hint, text=texts.NEW_PLAYLIST_HINT, font=theme.SMALL_FONT, anchor="w", justify="left", wraplength=HINT_WRAP_PIXELS)
        theme.bind(message, bg="background", fg="foreground")
        message.pack(side="left")
        cancel = tk.Label(self._hint, text=texts.CANCEL, font=theme.LINK_FONT, cursor="hand2")
        theme.bind(cancel, bg="background", fg="accent")
        add_focus_ring(cancel, "background")
        for sequence in ("<Button-1>", "<Return>", "<space>"):
            cancel.bind(sequence, lambda _event: self.cancel_awaiting())
        cancel.pack(side="left", padx=(8, 0))

    def _row_title(self, track: Track) -> str:
        title = display_name(track.title, track.uri)
        return title + PENDING_SUFFIX if track.uri in self._pending else title

    def _open_creator(self) -> None:
        if not self._creating:
            self._creating = True
            self._menu_button.pack_forget()
            self._name_entry.pack(side="left", fill="x", expand=True, before=self._add_button)
            self._events.resized()
        self._name_entry.focus_input()

    def _close_creator(self) -> None:
        if not self._creating:
            return
        self._creating = False
        if self._name_entry.has_focus():
            self._menu_button.focus_set()
        self._name_entry.pack_forget()
        self._name_entry.clear()
        self._menu_button.pack(side="left", fill="x", expand=True, before=self._add_button)
        self._events.resized()

    def _dismiss_creator(self) -> None:
        self.cancel_awaiting()
        self._close_creator()

    def _on_name_focus_out(self) -> None:
        if self._creating and not self._awaiting and not self._name_entry.query:
            self._close_creator()

    def _on_press(self, event: tk.Event) -> None:
        target = str(event.widget)
        if not target.startswith(str(self._name_entry)) and target != str(self._add_button):
            self._on_name_focus_out()

    def _build_selector(self) -> None:
        row = tk.Frame(self)
        theme.bind(row, bg="background")
        row.pack(fill="x", pady=(0, 6))
        self._selector = row
        self._menu_button = tk.Menubutton(
            row,
            text=texts.NO_PLAYLIST,
            relief="flat",
            bd=0,
            font=theme.TITLE_FONT,
            anchor="w",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        theme.bind(self._menu_button, bg="surface", fg="foreground", activebackground="surface_hover", activeforeground="foreground")
        add_focus_ring(self._menu_button, "background")
        self._menu = tk.Menu(self._menu_button, tearoff=False, font=theme.TEXT_FONT)
        theme.bind_menu(self._menu)
        self._menu_button.configure(menu=self._menu)
        for key in ("<Return>", "<space>", "<Down>"):
            self._menu_button.bind(key, lambda _event: self._open_selector())
        self._menu_button.pack(side="left", fill="x", expand=True)
        self._name_entry = SearchEntry(row, placeholder=texts.NEW_PLAYLIST_PLACEHOLDER, icon=Icon.LIST)
        self._name_entry.bind_key("<Return>", self._create)
        self._name_entry.bind_key("<Escape>", self._dismiss_creator)
        self._name_entry.on_focus_out(self._on_name_focus_out)
        self._add_button = IconButton(row, Icon.ADD, self._open_creator, tooltip=texts.NEW_PLAYLIST_TOOLTIP)
        self._add_button.pack(side="left", padx=(6, 0), fill="y")
        IconButton(row, Icon.PLAY, lambda: self._play_selected(0), variant="primary", tooltip=texts.PLAY_PLAYLIST).pack(side="left", padx=(6, 0), fill="y")
        IconButton(row, Icon.DELETE, self._delete_selected, variant="danger", tooltip=texts.DELETE_PLAYLIST).pack(side="left", padx=(24, 0), fill="y")

    def _open_selector(self) -> None:
        self._menu.tk_popup(self._menu_button.winfo_rootx(), self._menu_button.winfo_rooty() + self._menu_button.winfo_height())

    def _rebuild_menu(self) -> None:
        self._menu.delete(0, "end")
        for name in self._names:
            self._menu.add_command(label=name, command=lambda chosen=name: self._select(chosen))
        if self._selected not in self._names:
            self._show_selection(self._names[0] if self._names else "")

    def _show_selection(self, name: str) -> None:
        self._selected = name
        self._menu_button.configure(text=f"{name}  ▾" if name else texts.NO_PLAYLIST)

    def _select(self, name: str) -> None:
        changed = name != self._selected
        self._show_selection(name)
        self.refresh(keep_view=not changed)

    def _create(self) -> None:
        try:
            name = self._library.create(self._name_entry.query)
        except PlaylistExistsError as error:
            existing = error.existing
            self._select(existing)
            if self._awaiting:
                self._offer_message = texts.already_exists(shorten(existing, NAME_PREVIEW_LENGTH))
                self._status.show(self._offer_message, "error", texts.ADD_THERE, lambda: self._add_awaiting(existing))
            else:
                self._status.show(texts.already_exists(shorten(existing, NAME_PREVIEW_LENGTH)), "error")
            return
        except ValueError as error:
            self._status.show(str(error), "error")
            self._name_entry.focus_input()
            return
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self._close_creator()
        self.refresh()
        self._select(name)
        self._status.show(texts.created(shorten(name, NAME_PREVIEW_LENGTH)))
        self._add_awaiting(name, created=True)

    def _add_awaiting(self, name: str, created: bool = False) -> None:
        track = self._take_awaiting()
        if track is None:
            self._status.show(texts.NOTHING_TO_ADD, "error")
            return
        self._offer_message = None
        self._events.resized()
        try:
            self._library.add(name, track)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self.refresh()
        self._events.track_added(name, track)
        preview = shorten(name, NAME_PREVIEW_LENGTH)
        self._status.show(texts.created_with_song(preview) if created else texts.added_to(preview))

    def _delete_selected(self) -> None:
        name = self.selected
        if not name:
            self._status.show(texts.CREATE_FIRST, "error")
            return
        tracks = self._library.tracks(name)
        try:
            self._library.delete(name)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self._events.deleted(name)
        self.refresh(keep_view=False)
        self._status.show_undoable(texts.deleted(shorten(name, NAME_PREVIEW_LENGTH)), lambda: self._restore(name, tracks))

    def _restore(self, name: str, tracks: tuple[Track, ...]) -> None:
        try:
            self._library.restore(name, tracks)
        except PlaylistExistsError as error:
            self._status.show(texts.already_exists(shorten(error.existing, NAME_PREVIEW_LENGTH)), "error")
            return
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        self.refresh()
        self._select(name)
        self._events.restored(name)
        self._status.show(texts.restored(shorten(name, NAME_PREVIEW_LENGTH)))

    def _position(self, name: str, row: int, uri: str) -> int | None:
        position = locate([track.uri for track in self._library.tracks(name)], row, uri)
        if position is None:
            self._status.show(texts.SONG_NOT_IN_LIST)
        return position

    def _open_menu(self, row: int, uri: str, x: int, y: int) -> None:
        name = self.selected
        position = self._position(name, row, uri) if name else None
        if position is not None:
            self._song_menu.open(x, y, self._library.tracks(name)[position], MenuContext(remove=lambda: self._remove_track(name, row, uri)))

    def _remove_row(self, row: int, uri: str) -> None:
        if self.selected:
            self._remove_track(self.selected, row, uri)

    def _remove_track(self, name: str, row: int, uri: str) -> None:
        position = self._position(name, row, uri)
        if position is None:
            return
        track = self._library.tracks(name)[position]
        try:
            self._library.remove(name, position)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        if name == self._selected:
            self.refresh()
        title = shorten(display_name(track.title, track.uri), TITLE_PREVIEW_LENGTH)
        self._status.show_undoable(texts.removed_track(title), lambda: self._restore_track(name, position, track))

    def _restore_track(self, name: str, row: int, track: Track) -> None:
        if name not in self._library.names():
            self._status.show(texts.no_longer_exists(shorten(name, NAME_PREVIEW_LENGTH)), "error")
            return
        try:
            self._library.insert(name, row, track)
        except OSError:
            self._status.show(texts.SAVE_FAILED, "error")
            return
        if name == self._selected:
            self.refresh()
            self._tracks.reveal(row)

    def _play_row(self, row: int, uri: str) -> None:
        if self.selected:
            position = self._position(self.selected, row, uri)
            if position is not None:
                self._play_selected(position)

    def _play_selected(self, start: int) -> None:
        if not self.selected:
            self._status.show(texts.CREATE_FIRST, "error")
        elif not self._library.tracks(self.selected):
            self._status.show(texts.ADD_SONGS_FIRST, "error")
        else:
            self._events.play(self.selected, start)
