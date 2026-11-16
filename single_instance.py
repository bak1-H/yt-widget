import ctypes
import tkinter as tk
from ctypes import wintypes
from typing import Callable

MUTEX_NAME = r"Local\yt-widget-single-instance"
EVENT_NAME = r"Local\yt-widget-show-request"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0
CHECK_INTERVAL_MS = 300

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]


class SingleInstance:
    def __init__(self, mutex_name: str = MUTEX_NAME, event_name: str = EVENT_NAME) -> None:
        self._mutex_name = mutex_name
        self._event = _kernel32.CreateEventW(None, False, False, event_name)
        self._mutex: int | None = None

    def acquire(self) -> bool:
        self._mutex = _kernel32.CreateMutexW(None, True, self._mutex_name)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(self._mutex)
            self._mutex = None
            return False
        return True

    def release(self) -> None:
        if self._mutex is not None:
            _kernel32.ReleaseMutex(self._mutex)
            _kernel32.CloseHandle(self._mutex)
            self._mutex = None

    def request_show(self) -> None:
        _kernel32.SetEvent(self._event)

    def show_requested(self) -> bool:
        return _kernel32.WaitForSingleObject(self._event, 0) == WAIT_OBJECT_0

    def listen(self, root: tk.Misc, on_show: Callable[[], None]) -> None:
        def check() -> None:
            if self.show_requested():
                on_show()
            root.after(CHECK_INTERVAL_MS, check)

        check()
