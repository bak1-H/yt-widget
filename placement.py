import time
import tkinter as tk

from settings import WindowPosition
from window_style import activate, bring_to_top, is_foreground, send_to_bottom

KEEP_BEHIND_INTERVAL_MS = 1000
FOCUS_LOSS_DELAY_MS = 80
SHOW_GRACE_SECONDS = 8.0


class WindowPlacement:
    def __init__(self, window: tk.Tk) -> None:
        self._window = window
        self._position = WindowPosition.TOPMOST
        self._job: str | None = None
        self._held_until = 0.0
        window.bind("<FocusOut>", self._on_focus_out, add="+")

    def apply(self, position: WindowPosition) -> None:
        self._position = position
        self._window.attributes("-topmost", position is WindowPosition.TOPMOST)
        if self._job:
            self._window.after_cancel(self._job)
            self._job = None
        if position is WindowPosition.DESKTOP:
            self._keep_behind()

    def bring_to_front(self) -> None:
        self._held_until = time.monotonic() + SHOW_GRACE_SECONDS
        self._window.lift()
        bring_to_top(self._window, self._position is WindowPosition.TOPMOST)
        activate(self._window)

    def _on_focus_out(self, _event: tk.Event) -> None:
        if self._position is WindowPosition.DESKTOP:
            self._window.after(FOCUS_LOSS_DELAY_MS, self._send_back)

    def _keep_behind(self) -> None:
        self._send_back()
        self._job = self._window.after(KEEP_BEHIND_INTERVAL_MS, self._keep_behind)

    def _send_back(self) -> None:
        if self._window.state() != "withdrawn" and time.monotonic() >= self._held_until and not is_foreground(self._window):
            send_to_bottom(self._window)
