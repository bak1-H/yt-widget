import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from processes import TrackedProcesses, kill_tree

SLEEP_FOREVER = [sys.executable, "-c", "import time; time.sleep(60)"]
PRINT_HELLO = [sys.executable, "-c", "print('hello')"]
FAIL = [sys.executable, "-c", "raise SystemExit(3)"]
LAUNCHER = (
    "import subprocess, sys, time; "
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
    "open({marker!r}, 'w').write(str(child.pid)); "
    "time.sleep(60)"
)


class TrackedProcessesTest(unittest.TestCase):
    def test_returns_stdout_and_raises_on_failure(self) -> None:
        processes = TrackedProcesses()
        self.assertEqual(processes.run(PRINT_HELLO, 10).strip(), "hello")
        with self.assertRaises(subprocess.CalledProcessError):
            processes.run(FAIL, 10)

    def test_close_kills_the_running_process_so_the_caller_returns_quickly(self) -> None:
        processes = TrackedProcesses()
        outcome: list[BaseException | None] = []

        def work() -> None:
            try:
                processes.run(SLEEP_FOREVER, 60)
                outcome.append(None)
            except subprocess.SubprocessError as error:
                outcome.append(error)

        worker = threading.Thread(target=work)
        worker.start()
        time.sleep(0.5)
        processes.close()
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(outcome[0], subprocess.CalledProcessError)

    def test_kill_tree_ignores_a_process_that_already_finished(self) -> None:
        process = subprocess.Popen(PRINT_HELLO, stdout=subprocess.DEVNULL)
        process.wait()
        kill_tree(process)
        self.assertEqual(process.returncode, 0)

    def test_nothing_starts_after_close(self) -> None:
        processes = TrackedProcesses()
        processes.close()
        with self.assertRaises(OSError):
            processes.run(PRINT_HELLO, 10)

    def test_close_also_kills_children_of_the_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "child.pid"
            script = LAUNCHER.format(marker=str(marker))
            processes = TrackedProcesses()
            worker = threading.Thread(target=lambda: self._swallow(processes, [sys.executable, "-c", script]))
            worker.start()
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            child_pid = int(marker.read_text())
            processes.close()
            worker.join(timeout=10)
            time.sleep(0.5)
            listing = subprocess.run(["tasklist", "/FI", f"PID eq {child_pid}", "/NH"], capture_output=True, text=True).stdout
            self.assertNotIn(str(child_pid), listing)

    @staticmethod
    def _swallow(processes: TrackedProcesses, command: list[str]) -> None:
        try:
            processes.run(command, 60)
        except subprocess.SubprocessError:
            pass


if __name__ == "__main__":
    unittest.main()
