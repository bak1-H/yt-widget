import tkinter as tk
from dataclasses import dataclass
from typing import Callable

import texts
import theme
from playlists import FAVORITES, PlaylistLibrary
from track import Track


@dataclass(frozen=True)
class SongMenuActions:
    play_now: Callable[[Track], None]
    play_next: Callable[[Track], None]
    enqueue: Callable[[Track], None]
    set_membership: Callable[[str, Track, bool], None]
    new_playlist: Callable[[Track], None]
    set_favorite: Callable[[Track, bool], None]


@dataclass(frozen=True)
class MenuContext:
    remove: Callable[[], None] | None = None
    play_now: Callable[[], None] | None = None
    queue_entry: bool = False
    now_playing: bool = False


def styled_menu(parent: tk.Misc) -> tk.Menu:
    menu = tk.Menu(parent, tearoff=False, font=theme.TEXT_FONT)
    theme.bind_menu(menu)
    return menu


class SongMenu:
    def __init__(self, parent: tk.Misc, library: PlaylistLibrary, actions: SongMenuActions) -> None:
        self._library = library
        self._actions = actions
        self._menu = styled_menu(parent)
        self._playlists = styled_menu(self._menu)
        self._memberships: list[tk.BooleanVar] = []
        self._liked = tk.BooleanVar()

    def open(self, x: int, y: int, track: Track, context: MenuContext = MenuContext()) -> None:
        self._menu.delete(0, "end")
        self._liked.set(self._library.is_favorite(track.uri))
        self._menu.add_checkbutton(label=texts.FAVORITES, variable=self._liked, command=lambda: self._actions.set_favorite(track, self._liked.get()))
        self._menu.add_separator()
        if not context.now_playing:
            self._menu.add_command(label=texts.PLAY_NOW, command=context.play_now or (lambda: self._actions.play_now(track)))
        if not context.queue_entry:
            self._menu.add_command(label=texts.PLAY_NEXT, command=lambda: self._actions.play_next(track))
            self._menu.add_command(label=texts.ADD_TO_QUEUE, command=lambda: self._actions.enqueue(track))
        self._fill_playlists(track)
        self._menu.add_cascade(label=texts.ADD_TO_PLAYLIST, menu=self._playlists)
        if context.remove:
            self._menu.add_separator()
            self._menu.add_command(label=texts.REMOVE_FROM_LIST, command=context.remove)
        self._popup(self._menu, x, y)

    def _fill_playlists(self, track: Track) -> None:
        self._playlists.delete(0, "end")
        self._memberships = []
        for name in self._library.names():
            if name == FAVORITES:
                continue
            member = tk.BooleanVar(value=self._library.contains(name, track.uri))
            self._memberships.append(member)
            self._playlists.add_checkbutton(
                label=name,
                variable=member,
                command=lambda chosen=name, flag=member: self._actions.set_membership(chosen, track, flag.get()),
            )
        if self._memberships:
            self._playlists.add_separator()
        self._playlists.add_command(label=texts.NEW_PLAYLIST_ITEM, command=lambda: self._actions.new_playlist(track))

    @staticmethod
    def _popup(menu: tk.Menu, x: int, y: int) -> None:
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()
