from enum import Enum


class RepeatMode(str, Enum):
    OFF = "off"
    QUEUE = "queue"
    SONG = "song"


_CYCLE = (RepeatMode.OFF, RepeatMode.QUEUE, RepeatMode.SONG)


def next_repeat(mode: RepeatMode) -> RepeatMode:
    return _CYCLE[(_CYCLE.index(mode) + 1) % len(_CYCLE)]
