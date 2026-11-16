import ctypes
import msvcrt
import time
from ctypes import wintypes
from typing import BinaryIO

POLL_SECONDS = 0.002

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
_kernel32.PeekNamedPipe.restype = wintypes.BOOL


class NamedPipe:
    def __init__(self, path: str, read_timeout: float) -> None:
        self._file: BinaryIO = open(path, "r+b", buffering=0)
        self._handle = msvcrt.get_osfhandle(self._file.fileno())
        self._read_timeout = read_timeout

    def write(self, data: bytes) -> None:
        self._file.write(data)

    def read(self, size: int) -> bytes:
        deadline = time.monotonic() + self._read_timeout
        while True:
            available = wintypes.DWORD()
            if not _kernel32.PeekNamedPipe(self._handle, None, 0, None, ctypes.byref(available), None):
                return b""
            if available.value:
                return self._file.read(min(size, available.value))
            if time.monotonic() >= deadline:
                raise TimeoutError("mpv did not answer in time")
            time.sleep(POLL_SECONDS)

    def close(self) -> None:
        self._file.close()
