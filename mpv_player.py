import json
import os
import subprocess
import time
from contextlib import suppress
from itertools import count
from pathlib import Path
from typing import Any, Mapping

import texts
from named_pipe import NamedPipe
from player import NO_LOCAL_SONGS, LocalSongs, Observation, PlaybackStatus, PlayerError, QueueItem
from repeat import RepeatMode
from track import LocalSong, ResolvedTrack, Track

PIPE_TIMEOUT_SECONDS = 5.0
PIPE_RETRY_SECONDS = 0.1
READ_CHUNK_BYTES = 4096
SHUTDOWN_TIMEOUT_SECONDS = 3.0
BATCH_SIZE = 20
READ_TIMEOUT_SECONDS = 3.0
OBSERVED_PROPERTIES = ("path", "media-title", "time-pos", "duration", "pause", "idle-active", "core-idle", "playlist")
UNPAUSE = ("set_property", "pause", False)
REPEAT_LOOPS = {
    RepeatMode.OFF: ("no", "no"),
    RepeatMode.QUEUE: ("inf", "no"),
    RepeatMode.SONG: ("no", "inf"),
}


class MpvPlayer:
    def __init__(
        self,
        executable: Path,
        volume: int,
        ytdl_path: Path | None = None,
        local_songs: LocalSongs = NO_LOCAL_SONGS,
        repeat: RepeatMode = RepeatMode.OFF,
    ) -> None:
        self._executable = executable
        self._volume = volume
        self._repeat = repeat
        self._ytdl_path = ytdl_path
        self._local_songs = local_songs
        self._pipe_path = rf"\\.\pipe\yt-widget-{os.getpid()}"
        self._request_ids = count(1)
        self._aliases: dict[str, Track] = {}
        self._local_paths: set[str] = set()
        self._start()

    def restart(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
        with suppress(subprocess.TimeoutExpired):
            self._process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        with suppress(OSError):
            self._pipe.close()
        self._aliases.clear()
        self._local_paths.clear()
        self._start()

    def _arguments(self) -> list[str]:
        loop_playlist, loop_file = REPEAT_LOOPS[self._repeat]
        arguments = [
            str(self._executable),
            "--idle=yes",
            "--no-video",
            "--vo=null",
            "--force-window=no",
            "--no-terminal",
            "--ytdl-format=bestaudio/best",
            f"--volume={self._volume}",
            f"--loop-playlist={loop_playlist}",
            f"--loop-file={loop_file}",
            f"--input-ipc-server={self._pipe_path}",
        ]
        if self._ytdl_path:
            arguments.append(f"--script-opts=ytdl_hook-ytdl_path={self._ytdl_path}")
        return arguments

    def _start(self) -> None:
        self._buffer = b""
        self._process = subprocess.Popen(self._arguments(), creationflags=subprocess.CREATE_NO_WINDOW)
        self._pipe = self._connect()

    def load(self, uri: str) -> None:
        was_idle = bool(self._property("idle-active"))
        commands = [UNPAUSE, ("loadfile", self._source(uri), "insert-next-play")]
        if not was_idle:
            commands.append(("playlist-next",))
        self._exchange(commands)

    def enqueue(self, uri: str) -> None:
        self._add(uri, "append-play")

    def play_next(self, uri: str) -> None:
        self._add(uri, "insert-next-play")

    def _add(self, uri: str, mode: str) -> None:
        was_idle = bool(self._property("idle-active"))
        commands = [("loadfile", self._source(uri), mode)]
        self._exchange([UNPAUSE, *commands] if was_idle else commands)

    def remove(self, index: int) -> None:
        self._command("playlist-remove", index)

    def insert(self, uri: str, index: int) -> None:
        self._command("loadfile", self._source(uri), "insert-at", index)

    def play_all(self, uris: list[str], start: int = 0) -> None:
        commands = [("stop",), UNPAUSE, *(("loadfile", self._source(uri), "append") for uri in uris), ("set_property", "playlist-pos", start)]
        for first in range(0, len(commands), BATCH_SIZE):
            self._exchange(commands[first : first + BATCH_SIZE])

    def attach_stream(self, uri: str, resolved: ResolvedTrack) -> None:
        self._replace_upcoming(uri, resolved.stream_url, Track(resolved.title, resolved.page_url))

    def attach_local(self, uri: str, local: LocalSong) -> None:
        self._local_paths.add(local.path)
        self._replace_upcoming(uri, local.path, Track(local.title, uri))

    def relocate_local(self, changes: Mapping[str, str | None]) -> None:
        entries = self._property("playlist") or []
        commands: list[tuple[Any, ...]] = []
        relocated: set[str] = set()
        for index, entry in enumerate(entries):
            old = entry["filename"]
            alias = self._aliases.get(old)
            if entry.get("current") or old not in changes or alias is None:
                continue
            new = changes[old]
            if new:
                self._aliases[new] = alias
                self._local_paths.add(new)
            relocated.add(old)
            commands += [("loadfile", new or alias.uri, "insert-at", index), ("playlist-remove", index + 1)]
        for old in relocated:
            del self._aliases[old]
            self._local_paths.discard(old)
        for first in range(0, len(commands), BATCH_SIZE):
            self._exchange(commands[first : first + BATCH_SIZE])

    def _source(self, uri: str) -> str:
        local = self._local_songs.find(uri)
        if local is None:
            return uri
        self._aliases[local.path] = Track(local.title, uri)
        self._local_paths.add(local.path)
        return local.path

    def _replace_upcoming(self, uri: str, source: str, track: Track) -> None:
        entries = self._property("playlist") or []
        current = next((index for index, entry in enumerate(entries) if entry.get("current")), -1)
        order = [*range(current + 1, len(entries)), *range(max(current, 0))]
        target = next((index for index in order if entries[index]["filename"] == uri), None)
        if target is None:
            return
        self._aliases[source] = track
        self._command("loadfile", source, "insert-at", target)
        self._command("playlist-remove", target + 1)

    def play_at(self, index: int) -> None:
        self._exchange([UNPAUSE, ("set_property", "playlist-pos", index)])

    def toggle_pause(self) -> None:
        if not self._property("idle-active"):
            self._command("cycle", "pause")

    def next(self) -> None:
        self._command("playlist-next")

    def previous(self) -> None:
        self._command("playlist-prev")

    def seek(self, seconds: float) -> None:
        self._command("seek", seconds, "absolute")

    def set_volume(self, volume: int) -> None:
        self._volume = volume
        self._command("set_property", "volume", volume)

    def set_repeat(self, mode: RepeatMode) -> None:
        loop_playlist, loop_file = REPEAT_LOOPS[mode]
        self._exchange([("set_property", "loop-playlist", loop_playlist), ("set_property", "loop-file", loop_file)])
        self._repeat = mode

    def observe(self) -> Observation:
        replies = self._exchange([("get_property", name) for name in OBSERVED_PROPERTIES])
        values = {name: reply.get("data") if reply.get("error") == "success" else None for name, reply in zip(OBSERVED_PROPERTIES, replies)}
        path = values["path"]
        stream = self._aliases.get(path)
        status = PlaybackStatus(
            title=stream.title if stream else values["media-title"],
            path=stream.uri if stream else path,
            position=values["time-pos"],
            duration=values["duration"],
            paused=bool(values["pause"]),
            idle=bool(values["idle-active"]),
            buffering=bool(values["core-idle"]),
            local_file=path if path in self._local_paths else None,
        )
        return Observation(status, [self._queue_item(entry) for entry in values["playlist"] or []])

    def _queue_item(self, entry: dict[str, Any]) -> QueueItem:
        stream = self._aliases.get(entry["filename"])
        title, uri = (stream.title, stream.uri) if stream else (entry.get("title"), entry["filename"])
        return QueueItem(title=title, uri=uri, current=bool(entry.get("current")))

    def close(self) -> None:
        try:
            self._command("quit")
        except PlayerError:
            pass
        with suppress(OSError):
            self._pipe.close()
        try:
            self._process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def _connect(self) -> NamedPipe:
        deadline = time.monotonic() + PIPE_TIMEOUT_SECONDS
        while True:
            try:
                return NamedPipe(self._pipe_path, READ_TIMEOUT_SECONDS)
            except FileNotFoundError:
                if self._process.poll() is not None or time.monotonic() > deadline:
                    self._process.kill()
                    raise PlayerError(texts.MPV_DID_NOT_START)
                time.sleep(PIPE_RETRY_SECONDS)

    def _property(self, name: str) -> Any:
        reply = self._command("get_property", name)
        return reply.get("data") if reply.get("error") == "success" else None

    def _command(self, *args: Any) -> dict[str, Any]:
        return self._exchange([args])[0]

    def _exchange(self, commands: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        request_ids = [next(self._request_ids) for _ in commands]
        message = "".join(json.dumps({"command": list(command), "request_id": request_id}) + "\n" for command, request_id in zip(commands, request_ids))
        replies: dict[int, dict[str, Any]] = {}
        try:
            self._pipe.write(message.encode())
            while len(replies) < len(request_ids):
                reply = json.loads(self._read_line())
                if reply.get("request_id") in request_ids:
                    replies[reply["request_id"]] = reply
        except (OSError, ValueError) as error:
            raise PlayerError(texts.MPV_CONNECTION_LOST) from error
        return [replies[request_id] for request_id in request_ids]

    def _read_line(self) -> bytes:
        while b"\n" not in self._buffer:
            chunk = self._pipe.read(READ_CHUNK_BYTES)
            if not chunk:
                raise PlayerError(texts.MPV_CONNECTION_CLOSED)
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line
