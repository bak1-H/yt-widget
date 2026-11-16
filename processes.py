import subprocess
import threading
from contextlib import suppress

TASKKILL_TIMEOUT_SECONDS = 5


def kill_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    with suppress(OSError, subprocess.SubprocessError):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            timeout=TASKKILL_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    with suppress(OSError):
        process.kill()


class TrackedProcesses:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: set[subprocess.Popen[str]] = set()
        self._closed = False

    def run(self, command: list[str], timeout: float) -> str:
        with self._lock:
            if self._closed:
                raise OSError("The widget is shutting down")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._running.add(process)
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            with suppress(OSError, subprocess.SubprocessError):
                process.communicate(timeout=TASKKILL_TIMEOUT_SECONDS)
            raise
        finally:
            with self._lock:
                self._running.discard(process)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)
        return stdout

    def close(self) -> None:
        with self._lock:
            self._closed = True
            running = list(self._running)
        for process in running:
            kill_tree(process)
