from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    title: str
    uri: str


@dataclass(frozen=True)
class ResolvedTrack:
    title: str
    page_url: str
    stream_url: str


@dataclass(frozen=True)
class LocalSong:
    path: str
    title: str
