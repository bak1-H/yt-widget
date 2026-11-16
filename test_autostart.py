import unittest
from pathlib import Path

from autostart import VALUE_NAME, Autostart, build_command


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.values.get(name)

    def write(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


class BuildCommandTest(unittest.TestCase):
    def test_quotes_both_paths(self) -> None:
        command = build_command(Path(r"C:\Program Files\Python\pythonw.exe"), Path(r"P:\yt-widget\main.py"))
        self.assertEqual(command, r'"C:\Program Files\Python\pythonw.exe" "P:\yt-widget\main.py"')


class AutostartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = FakeRegistry()
        self.autostart = Autostart(self.registry, "cmd")

    def test_reflects_registry_state(self) -> None:
        self.assertFalse(self.autostart.is_enabled())
        self.registry.values[VALUE_NAME] = "anything"
        self.assertTrue(self.autostart.is_enabled())

    def test_enable_writes_command_and_disable_removes_it(self) -> None:
        self.autostart.set_enabled(True)
        self.assertEqual(self.registry.values, {VALUE_NAME: "cmd"})
        self.autostart.set_enabled(False)
        self.assertEqual(self.registry.values, {})
        self.autostart.set_enabled(False)


if __name__ == "__main__":
    unittest.main()
