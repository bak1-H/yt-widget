import winreg
from contextlib import suppress
from pathlib import Path
from typing import Protocol

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "YT Widget"


class RunRegistry(Protocol):
    def read(self, name: str) -> str | None: ...

    def write(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class WindowsRunRegistry:
    def read(self, name: str) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value)

    def write(self, name: str, value: str) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        with suppress(FileNotFoundError):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)


def build_command(interpreter: Path, script: Path) -> str:
    return f'"{interpreter}" "{script}"'


class Autostart:
    def __init__(self, registry: RunRegistry, command: str) -> None:
        self._registry = registry
        self._command = command

    def is_enabled(self) -> bool:
        return self._registry.read(VALUE_NAME) is not None

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._registry.write(VALUE_NAME, self._command)
        else:
            self._registry.delete(VALUE_NAME)
