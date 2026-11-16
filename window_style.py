import ctypes
import tkinter as tk
from ctypes import wintypes

from settings import GlassStyle

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
ACCENT_DRAW_ALL_BORDERS = 2
SPI_GETWORKAREA = 0x0030
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
MONITOR_DEFAULTTONEAREST = 2
GW_HWNDPREV = 3
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14
IGNORED_OVERLAY_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow"}
Rect = tuple[int, int, int, int]
GLASS_ACCENT_STATES = {
    GlassStyle.BLUR: ACCENT_ENABLE_ACRYLICBLURBEHIND,
    GlassStyle.CLEAR: ACCENT_ENABLE_TRANSPARENTGRADIENT,
}


class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("accent_state", ctypes.c_int),
        ("accent_flags", ctypes.c_int),
        ("gradient_color", ctypes.c_uint),
        ("animation_id", ctypes.c_int),
    ]


class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("attribute", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("size_of_data", ctypes.c_size_t),
    ]


def round_corners(window: tk.Tk) -> None:
    preference = ctypes.c_int(DWMWCP_ROUND)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        _window_handle(window), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference), ctypes.sizeof(preference)
    )


def accent_for(style: GlassStyle | None) -> tuple[int, int]:
    if style is None:
        return ACCENT_DISABLED, 0
    return GLASS_ACCENT_STATES[style], ACCENT_DRAW_ALL_BORDERS


def apply_glass(window: tk.Tk, tint_abgr: int, style: GlassStyle | None) -> bool:
    state, flags = accent_for(style)
    policy = AccentPolicy(state, flags, tint_abgr, 0)
    data = WindowCompositionAttributeData(
        WCA_ACCENT_POLICY, ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p), ctypes.sizeof(policy)
    )
    try:
        return bool(ctypes.windll.user32.SetWindowCompositionAttribute(_window_handle(window), ctypes.byref(data)))
    except AttributeError:
        return False


def send_to_bottom(window: tk.Tk) -> None:
    _set_z_order(window, HWND_BOTTOM)


def bring_to_top(window: tk.Tk, stay_on_top: bool) -> None:
    _set_z_order(window, HWND_TOPMOST)
    if not stay_on_top:
        _set_z_order(window, HWND_NOTOPMOST)


def activate(window: tk.Tk) -> None:
    ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(_window_handle(window)))


def is_foreground(window: tk.Tk) -> bool:
    return ctypes.windll.user32.GetForegroundWindow() == _window_handle(window)


def _set_z_order(window: tk.Tk, anchor: int) -> None:
    ctypes.windll.user32.SetWindowPos(
        ctypes.c_void_p(_window_handle(window)), ctypes.c_void_p(anchor), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )


class MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT), ("work", wintypes.RECT), ("flags", wintypes.DWORD)]


def rects_intersect(first: Rect, second: Rect) -> bool:
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


def monitor_work_area(window: tk.Tk) -> Rect:
    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    monitor = user32.MonitorFromWindow(ctypes.c_void_p(_window_handle(window)), MONITOR_DEFAULTTONEAREST)
    info = MonitorInfo(ctypes.sizeof(MonitorInfo))
    if not user32.GetMonitorInfoW(ctypes.c_void_p(monitor), ctypes.byref(info)):
        return work_area()
    return info.work.left, info.work.top, info.work.right, info.work.bottom


def is_covered(window: tk.Tk) -> bool:
    user32 = ctypes.windll.user32
    user32.GetWindow.restype = wintypes.HWND
    own = _window_handle(window)
    own_rect = _window_rect(own)
    other = user32.GetWindow(ctypes.c_void_p(own), GW_HWNDPREV)
    while other:
        if _is_overlay(other) and rects_intersect(own_rect, _window_rect(other)):
            return True
        other = user32.GetWindow(ctypes.c_void_p(other), GW_HWNDPREV)
    return False


def _is_overlay(handle: int) -> bool:
    user32 = ctypes.windll.user32
    if not user32.IsWindowVisible(ctypes.c_void_p(handle)) or user32.IsIconic(ctypes.c_void_p(handle)):
        return False
    cloaked = wintypes.DWORD()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(handle), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    style = user32.GetWindowLongW(ctypes.c_void_p(handle), GWL_EXSTYLE)
    name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(ctypes.c_void_p(handle), name, len(name))
    return not cloaked.value and not style & (WS_EX_TRANSPARENT | WS_EX_NOACTIVATE) and name.value not in IGNORED_OVERLAY_CLASSES


def _window_rect(handle: int) -> Rect:
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(ctypes.c_void_p(handle), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def work_area() -> Rect:
    area = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0)
    return area.left, area.top, area.right, area.bottom


def _window_handle(window: tk.Tk) -> int:
    window.update_idletasks()
    return ctypes.windll.user32.GetParent(window.winfo_id())
