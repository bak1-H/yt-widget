import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable, Literal

import texts
import theme
from media import fit_text
from shape_render import RoundPhotos, RoundSpec
from theme import Icon
from undo import UndoSlot

BUTTON_VARIANTS = {
    "primary": ("accent", "accent_hover", "on_accent", "on_accent"),
    "surface": ("surface", "surface_hover", "foreground", "foreground"),
    "ghost": ("background", "surface_hover", "muted", "muted"),
    "danger": ("surface", "surface_hover", "foreground", "danger"),
    "row": ("surface", "surface_hover", "muted", "foreground"),
}
SLIDER_HEIGHT = 8
SLIDER_KNOB_HEIGHT = 16
SLIDER_KNOB_RADIUS = 6
SLIDER_KNOB_SIZE = 2 * SLIDER_KNOB_RADIUS
SLIDER_TRACK = 4
KEYBOARD_STEP = 0.05
FOCUS_RING_THICKNESS = 2
TOOLTIP_DELAY_MS = 500
TOOLTIP_GAP = 6
TOOLTIP_WRAP_PIXELS = 320
STATUS_DURATION_MS = 6000
STATUS_HEIGHT = 22
STATUS_SPACING = 12
SCROLLBAR_STYLE = "Thin.Vertical.TScrollbar"
SCROLLBAR_WIDTH = 8
StatusKind = Literal["info", "error"]
TooltipText = str | Callable[[], str]


def add_focus_ring(widget: tk.Widget, background_role: str) -> None:
    widget.configure(highlightthickness=FOCUS_RING_THICKNESS, takefocus=True)
    theme.bind(widget, highlightcolor="accent", highlightbackground=background_role)


def enable_dragging(window: tk.Tk, *widgets: tk.Misc) -> None:
    offset = [0, 0]

    def start(event: tk.Event) -> None:
        offset[:] = [event.x_root - window.winfo_x(), event.y_root - window.winfo_y()]

    def drag(event: tk.Event) -> None:
        window.geometry(f"+{event.x_root - offset[0]}+{event.y_root - offset[1]}")

    for widget in widgets:
        widget.bind("<ButtonPress-1>", start, add="+")
        widget.bind("<B1-Motion>", drag, add="+")


class Tooltip:
    def __init__(self, widget: tk.Widget, text: TooltipText) -> None:
        self._widget = widget
        self._text = text if callable(text) else (lambda: text)
        self._window: tk.Toplevel | None = None
        self._pending: str | None = None
        widget.bind("<Enter>", lambda _event: self._schedule(), add="+")
        widget.bind("<FocusIn>", lambda _event: self.show(), add="+")
        for sequence in ("<Leave>", "<FocusOut>", "<ButtonPress>", "<Destroy>"):
            widget.bind(sequence, lambda _event: self.hide(), add="+")

    def show(self) -> None:
        self.hide()
        text = self._text()
        if not text:
            return
        window = tk.Toplevel(self._widget)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        tk.Label(
            window,
            text=text,
            bg=theme.color("surface_hover"),
            fg=theme.color("foreground"),
            font=theme.SMALL_FONT,
            wraplength=TOOLTIP_WRAP_PIXELS,
            justify="left",
            padx=8,
            pady=3,
            highlightthickness=1,
            highlightbackground=theme.color("border"),
        ).pack()
        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        x = min(self._widget.winfo_rootx(), self._widget.winfo_screenwidth() - width - TOOLTIP_GAP)
        below = self._widget.winfo_rooty() + self._widget.winfo_height() + TOOLTIP_GAP
        fits_below = below + height <= self._widget.winfo_screenheight()
        y = below if fits_below else self._widget.winfo_rooty() - height - TOOLTIP_GAP
        window.geometry(f"+{max(x, 0)}+{y}")
        window.deiconify()
        self._window = window

    def hide(self) -> None:
        if self._pending:
            self._widget.after_cancel(self._pending)
            self._pending = None
        if self._window:
            self._window.destroy()
            self._window = None

    def _schedule(self) -> None:
        self.hide()
        self._pending = self._widget.after(TOOLTIP_DELAY_MS, self.show)


class StatusLine(tk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, height=STATUS_HEIGHT)
        theme.bind(self, bg="background")
        self.pack_propagate(False)
        self._clear_job: str | None = None
        self._action: Callable[[], None] | None = None
        self._pinned: tuple[str, StatusKind] | None = None
        self._showing_pinned = False
        self._dismiss_visible = False
        self._full = ""
        self._truncated = False
        self._undo = UndoSlot()
        self._font = tkfont.Font(font=theme.SMALL_FONT)
        self._message = tk.Label(self, anchor="w", font=theme.SMALL_FONT)
        theme.bind(self._message, bg="background", fg="foreground")
        Tooltip(self._message, lambda: self._full if self._truncated else "")
        self._link = self._build_link(theme.LINK_FONT, "accent", self._invoke)
        self._dismiss = self._build_link(theme.SMALL_FONT, "muted", self.dismiss)
        self._dismiss.configure(text="✕")
        Tooltip(self._dismiss, texts.DISMISS)
        self.bind("<Configure>", lambda _event: self._fit())

    @property
    def message(self) -> str:
        return self._full

    def show(
        self,
        message: str,
        kind: StatusKind = "info",
        action_label: str | None = None,
        action: Callable[[], None] | None = None,
        *,
        pinned: bool = False,
    ) -> None:
        if pinned:
            self._pinned = (message, kind)
        self._render(message, kind, action_label, action, showing_pinned=pinned)

    def show_undoable(self, message: str, undo: Callable[[], None]) -> None:
        self._render(message, "info", None, None, showing_pinned=False, undo=undo)

    def undo(self) -> None:
        action = self._undo.take()
        self.clear()
        if action:
            action()

    def clear(self) -> None:
        self._cancel_job("_clear_job")
        self._undo.discard()
        self._showing_pinned = False
        self._dismiss_visible = False
        self._action = None
        self._full = ""
        self._message.configure(text="")
        self._refresh_link()

    def dismiss(self) -> None:
        if self._showing_pinned:
            self._pinned = None
        self._expire()

    def _build_link(self, font: tuple, color_role: str, command: Callable[[], None]) -> tk.Label:
        link = tk.Label(self, font=font, cursor="hand2")
        theme.bind(link, bg="background", fg=color_role)
        add_focus_ring(link, "background")
        for sequence in ("<Button-1>", "<Return>", "<space>"):
            link.bind(sequence, lambda _event: command())
        return link

    def _render(
        self,
        message: str,
        kind: StatusKind,
        action_label: str | None,
        action: Callable[[], None] | None,
        *,
        showing_pinned: bool,
        undo: Callable[[], None] | None = None,
    ) -> None:
        self.clear()
        if undo:
            self._undo.keep(undo)
        self._showing_pinned = showing_pinned
        self._full = message
        self._action = action if action_label else None
        self._link.configure(text=action_label or "")
        theme.bind(self._message, fg="danger" if kind == "error" else "foreground")
        theme.bind(self._dismiss, fg="danger" if kind == "error" else "muted")
        self._dismiss_visible = kind == "error"
        self._refresh_link()
        if kind == "info":
            self._clear_job = self.after(self._lifetime_ms(), self._expire)

    def _lifetime_ms(self) -> int:
        return int(self._undo.remaining() * 1000) if self._undo.available() else STATUS_DURATION_MS

    def _refresh_link(self) -> None:
        if not self._action and self._undo.available():
            self._link.configure(text=texts.UNDO)
        elif not self._action:
            self._link.configure(text="")
        self._layout()

    def _layout(self) -> None:
        for widget in (self._dismiss, self._message, self._link):
            widget.pack_forget()
        if self._dismiss_visible:
            self._dismiss.pack(side="right", padx=(6, 0))
        self._message.pack(side="left")
        if self._link.cget("text"):
            self._link.pack(side="left", padx=(6, 0))
        self._fit()

    def _fit(self) -> None:
        available = self.winfo_width()
        if available <= 1 or not self._full:
            self._message.configure(text=self._full)
            self._truncated = False
            return
        reserved = sum(widget.winfo_reqwidth() + STATUS_SPACING for widget in (self._link, self._dismiss) if widget.winfo_manager())
        text = fit_text(self._full, available - reserved, self._font.measure)
        self._truncated = text != self._full
        self._message.configure(text=text)

    def _expire(self) -> None:
        self.clear()
        if self._pinned:
            self._render(*self._pinned, None, None, showing_pinned=True)

    def _cancel_job(self, name: str) -> None:
        job = getattr(self, name)
        if job:
            self.after_cancel(job)
            setattr(self, name, None)

    def _invoke(self) -> None:
        action = self._action
        if action is None:
            self.undo()
            return
        self.clear()
        action()


class IconButton(tk.Button):
    def __init__(
        self,
        parent: tk.Misc,
        icon: str,
        action: Callable[[], None],
        *,
        tooltip: TooltipText,
        variant: str = "surface",
        large: bool = False,
    ) -> None:
        background, hover, foreground, hover_foreground = BUTTON_VARIANTS[variant]
        super().__init__(
            parent,
            text=icon,
            command=action,
            relief="flat",
            bd=0,
            font=theme.ICON_FONT_LARGE if large else theme.ICON_FONT,
            padx=12 if large else 8,
            pady=6 if large else 4,
            cursor="hand2",
        )
        theme.bind(self, bg=background, fg=foreground, activebackground=hover, activeforeground=hover_foreground)
        add_focus_ring(self, theme.role_of(parent))
        self._rest_foreground = foreground
        self._hover_foreground = hover_foreground
        self.bind("<Enter>", lambda _event: theme.bind(self, bg=hover, fg=self._hover_foreground))
        self.bind("<Leave>", lambda _event: theme.bind(self, bg=background, fg=self._rest_foreground))
        self.bind("<Return>", lambda _event: self.invoke())
        Tooltip(self, tooltip)

    def set_icon(self, icon: str) -> None:
        if self.cget("text") != icon:
            self.configure(text=icon)

    def set_foreground(self, color_role: str) -> None:
        self._rest_foreground = color_role
        self._hover_foreground = color_role
        theme.bind(self, fg=color_role)


class TextButton(IconButton):
    def __init__(self, parent: tk.Misc, label: str, action: Callable[[], None], *, tooltip: TooltipText, variant: str = "surface") -> None:
        super().__init__(parent, label, action, tooltip=tooltip, variant=variant)
        self.configure(font=theme.TITLE_FONT, padx=12)


class SearchEntry(tk.Frame):
    def __init__(self, parent: tk.Misc, placeholder: str, icon: str = Icon.SEARCH) -> None:
        self._rest_ring = theme.role_of(parent)
        super().__init__(parent, padx=8, highlightthickness=FOCUS_RING_THICKNESS)
        theme.bind(self, bg="surface", highlightbackground=self._rest_ring)
        self._placeholder = placeholder
        self._showing_placeholder = False
        glyph = tk.Label(self, text=icon, font=theme.ICON_FONT)
        theme.bind(glyph, bg="surface", fg="muted")
        glyph.pack(side="left")
        self._entry = tk.Entry(
            self,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=theme.TEXT_FONT,
        )
        theme.bind(self._entry, bg="surface", fg="foreground", insertbackground="foreground")
        self._entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 0))
        self._entry.bind("<FocusIn>", lambda _event: self._on_focus_in())
        self._entry.bind("<FocusOut>", lambda _event: self._on_focus_out())
        self._show_placeholder()

    @property
    def query(self) -> str:
        return "" if self._showing_placeholder else self._entry.get()

    def bind_key(self, sequence: str, handler: Callable[[], None]) -> None:
        self._entry.bind(sequence, lambda _event: handler())

    def on_focus_out(self, handler: Callable[[], None]) -> None:
        self._entry.bind("<FocusOut>", lambda _event: handler(), add="+")

    def focus_input(self) -> None:
        self._entry.focus_set()

    def has_focus(self) -> bool:
        try:
            return self.focus_get() is self._entry
        except KeyError:
            return False

    def clear(self) -> None:
        self._entry.delete(0, "end")
        if self.focus_get() is not self._entry:
            self._show_placeholder()

    def set_placeholder(self, placeholder: str) -> None:
        if placeholder == self._placeholder:
            return
        self._placeholder = placeholder
        if self._showing_placeholder:
            self._entry.delete(0, "end")
            self._entry.insert(0, placeholder)

    def _on_focus_in(self) -> None:
        theme.bind(self, highlightbackground="accent")
        self._hide_placeholder()

    def _on_focus_out(self) -> None:
        theme.bind(self, highlightbackground=self._rest_ring)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        if self._entry.get():
            return
        self._showing_placeholder = True
        theme.bind(self._entry, fg="muted")
        self._entry.insert(0, self._placeholder)

    def _hide_placeholder(self) -> None:
        if not self._showing_placeholder:
            return
        self._showing_placeholder = False
        self._entry.delete(0, "end")
        theme.bind(self._entry, fg="foreground")


class SliderBar(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        on_change: Callable[[float], None],
        *,
        width: int = 0,
        show_knob: bool = False,
        live: bool = True,
        wheel: bool = False,
        background: str = "background",
    ) -> None:
        height = SLIDER_KNOB_HEIGHT if show_knob else SLIDER_HEIGHT
        super().__init__(parent, width=width, height=height, cursor="hand2")
        theme.bind(self, bg=background)
        add_focus_ring(self, theme.role_of(parent))
        theme.observe(self)
        self._on_change = on_change
        self._show_knob = show_knob
        self._live = live
        self._ratio = 0.0
        self._dragging = False
        self._enabled = True
        self._knobs = RoundPhotos(self)
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        if wheel:
            self.bind("<MouseWheel>", lambda event: self._step(KEYBOARD_STEP if event.delta > 0 else -KEYBOARD_STEP))
        self.bind("<Right>", lambda _event: self._step(KEYBOARD_STEP))
        self.bind("<Left>", lambda _event: self._step(-KEYBOARD_STEP))

    def apply_theme(self, _theme: theme.Theme) -> None:
        self._draw()

    def set_ratio(self, ratio: float) -> None:
        if self._dragging or ratio == self._ratio:
            return
        self._ratio = ratio
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow", takefocus=enabled)
        self._draw()

    def _press(self, event: tk.Event) -> None:
        if not self._enabled:
            return
        self._dragging = True
        self.focus_set()
        self._move(event)

    def _move(self, event: tk.Event) -> None:
        if not self._enabled:
            return
        self._ratio = clamp_ratio((event.x - FOCUS_RING_THICKNESS) / max(self._inner_width(), 1))
        self._draw()
        if self._live:
            self._on_change(self._ratio)

    def _release(self, _event: tk.Event) -> None:
        self._dragging = False
        if not self._live:
            self._on_change(self._ratio)

    def _step(self, delta: float) -> None:
        if not self._enabled:
            return
        self._ratio = clamp_ratio(self._ratio + delta)
        self._draw()
        self._on_change(self._ratio)

    def _inner_width(self) -> int:
        return self.winfo_width() - 2 * FOCUS_RING_THICKNESS

    def _draw(self) -> None:
        width = self._inner_width()
        left = self.canvasx(FOCUS_RING_THICKNESS)
        middle = self.canvasy(FOCUS_RING_THICKNESS) + int(self.cget("height")) / 2
        top, bottom = middle - SLIDER_TRACK / 2, middle + SLIDER_TRACK / 2
        filled = left + width * self._ratio
        palette = theme.current()
        self.delete("all")
        self.create_rectangle(left, top, left + width, bottom, fill=palette.slider_track, width=0)
        self.create_rectangle(left, top, filled, bottom, fill=palette.bar_fill if self._enabled else palette.muted, width=0)
        if self._show_knob:
            center = min(max(filled, left + SLIDER_KNOB_RADIUS), left + width - SLIDER_KNOB_RADIUS)
            knob = RoundSpec(SLIDER_KNOB_SIZE, SLIDER_KNOB_SIZE, (0, 0, SLIDER_KNOB_SIZE, SLIDER_KNOB_SIZE), palette.foreground if self._enabled else palette.muted)
            self.create_image(center, middle, image=self._knobs.get(knob))


def clamp_ratio(ratio: float) -> float:
    return min(max(ratio, 0.0), 1.0)


def thin_scrollbar_style() -> str:
    style = ttk.Style()
    style.theme_use("clam")
    style.layout(
        SCROLLBAR_STYLE,
        [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})],
    )
    palette = theme.current()
    style.configure(
        SCROLLBAR_STYLE,
        troughcolor=palette.surface,
        background=palette.surface_hover,
        bordercolor=palette.surface,
        lightcolor=palette.surface_hover,
        darkcolor=palette.surface_hover,
        arrowsize=SCROLLBAR_WIDTH,
        relief="flat",
    )
    style.map(SCROLLBAR_STYLE, background=[("active", palette.muted)])
    return SCROLLBAR_STYLE

