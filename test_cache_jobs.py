import threading
import time
import unittest

from cache_jobs import CacheJobs
from song_cache import CacheReport


def settle(jobs: CacheJobs) -> None:
    deadline = time.monotonic() + 2
    while jobs.busy and time.monotonic() < deadline:
        time.sleep(0.01)
        jobs.deliver()


class CacheJobsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = CacheJobs()

    def tearDown(self) -> None:
        self.jobs.close()

    def test_delivers_the_report_on_the_calling_thread(self) -> None:
        results: list[tuple[CacheReport | None, int]] = []
        self.jobs.submit(lambda stop: CacheReport(kept_playing=True), lambda report: results.append((report, threading.get_ident())))
        self.assertTrue(self.jobs.busy)
        settle(self.jobs)
        self.assertEqual(results, [(CacheReport(kept_playing=True), threading.get_ident())])
        self.assertFalse(self.jobs.busy)

    def test_a_failing_task_delivers_none(self) -> None:
        def explode(stop: threading.Event) -> CacheReport:
            raise OSError("boom")

        results: list[CacheReport | None] = []
        self.jobs.submit(explode, results.append)
        settle(self.jobs)
        self.assertEqual(results, [None])

    def test_close_asks_running_tasks_to_stop(self) -> None:
        seen: list[threading.Event] = []
        self.jobs.submit(lambda stop: seen.append(stop) or CacheReport(), lambda report: None)
        settle(self.jobs)
        self.jobs.close()
        self.assertTrue(seen[0].is_set())


if __name__ == "__main__":
    unittest.main()
