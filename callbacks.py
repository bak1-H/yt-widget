from typing import Callable, Iterable


def run_each(actions: Iterable[Callable[[], None]]) -> None:
    first_error: Exception | None = None
    for action in actions:
        try:
            action()
        except Exception as error:
            first_error = first_error or error
    if first_error:
        raise first_error
