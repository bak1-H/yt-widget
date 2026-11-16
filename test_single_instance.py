import unittest
import uuid

from single_instance import SingleInstance


class SingleInstanceTest(unittest.TestCase):
    def setUp(self) -> None:
        token = uuid.uuid4().hex
        self.names = (f"Local-test-mutex-{token}", f"Local-test-event-{token}")

    def test_second_instance_is_refused_and_can_wake_the_first(self) -> None:
        first, second = SingleInstance(*self.names), SingleInstance(*self.names)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        self.assertFalse(first.show_requested())
        second.request_show()
        self.assertTrue(first.show_requested())
        self.assertFalse(first.show_requested())

    def test_releasing_lets_a_new_instance_start(self) -> None:
        first, second = SingleInstance(*self.names), SingleInstance(*self.names)
        self.assertTrue(first.acquire())
        first.release()
        self.assertTrue(second.acquire())
        second.release()
        second.release()


if __name__ == "__main__":
    unittest.main()
