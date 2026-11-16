import os
import shutil
import sys
import sysconfig
import tkinter as tk
from contextlib import suppress
from pathlib import Path
from tkinter import messagebox

import texts
from autostart import Autostart, WindowsRunRegistry, build_command
from cache_jobs import CacheJobs
from history import History, JsonHistoryStore
from mpv_player import MpvPlayer
from player import PlayerError
from playlists import JsonPlaylistStore, PlaylistLibrary
from prefetch import Prefetcher
from processes import TrackedProcesses
from recommendations import Autoplay, YtDlpMixSource
from resolver import BackgroundResolver, YtDlpResolver
from settings import JsonSettingsStore
from single_instance import SingleInstance
from song_cache import SongCache, configured_folder, limit_bytes
from song_downloads import SongDownloads, YtDlpDownloader
from thumbnails import DiskThumbnails, ThumbnailLoader, fetch_thumbnail
from tray import TrayIcon
from widget import PlayerWidget

DEFAULT_MPV_PATH = Path(r"C:\Program Files\MPV Player\mpv.exe")
FALLBACK_YTDLP = Path("yt-dlp")


def find_mpv() -> Path:
    found = shutil.which("mpv")
    path = Path(found) if found else DEFAULT_MPV_PATH
    if not path.exists():
        raise PlayerError(texts.MPV_NOT_FOUND)
    return path


def find_ytdlp() -> Path | None:
    user_scripts = Path(sysconfig.get_path("scripts", f"{os.name}_user")) / "yt-dlp.exe"
    if user_scripts.exists():
        return user_scripts
    found = shutil.which("yt-dlp")
    return Path(found) if found else None


def data_path(file_name: str) -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "yt-widget" / file_name


def autostart_command() -> str:
    interpreter = Path(sys.executable).with_name("pythonw.exe")
    return build_command(interpreter, Path(__file__).resolve())


def main() -> int:
    instance = SingleInstance()
    if not instance.acquire():
        instance.request_show()
        return 0
    root = tk.Tk()
    ytdlp = find_ytdlp()
    settings_store = JsonSettingsStore(data_path("settings.json"))
    settings = settings_store.load()
    cache = SongCache(configured_folder(settings.cache_folder), limit_bytes(settings.cache_limit_gb), settings.cache_enabled)
    try:
        player = MpvPlayer(find_mpv(), settings.startup_volume, ytdlp, cache, settings.repeat_mode)
    except PlayerError as error:
        root.withdraw()
        messagebox.showerror(texts.APP_TITLE, str(error))
        return 1
    processes = TrackedProcesses()
    jobs = CacheJobs()
    downloads = SongDownloads(cache, YtDlpDownloader(ytdlp or FALLBACK_YTDLP, processes).download)
    resolver = BackgroundResolver(YtDlpResolver(ytdlp or FALLBACK_YTDLP, processes).resolve)
    autoplay = Autoplay(YtDlpMixSource(ytdlp or FALLBACK_YTDLP, processes))
    thumbnail_loader = ThumbnailLoader(fetch_thumbnail, DiskThumbnails(lambda: cache.folder if cache.enabled else None))
    try:
        widget = PlayerWidget(
            root,
            player,
            History(JsonHistoryStore(data_path("history.json"))),
            PlaylistLibrary(JsonPlaylistStore(data_path("playlists.json"))),
            resolver,
            Prefetcher(player, resolver, settings.prefetch_count, cache),
            settings,
            settings_store,
            Autostart(WindowsRunRegistry(), autostart_command()),
            cache,
            downloads,
            jobs,
            autoplay,
            thumbnail_loader,
            root.destroy,
        )
        tray = TrayIcon(
            on_toggle=widget.toggle_visibility,
            on_play_pause=widget.play_pause,
            on_next=widget.next_track,
            on_quit=root.destroy,
            schedule=lambda action: root.after(0, action),
        )
        tray.start()
        instance.listen(root, widget.show)
        try:
            root.mainloop()
        finally:
            tray.stop()
    finally:
        try:
            processes.close()
            jobs.close()
            downloads.close()
            resolver.close()
            autoplay.close()
            thumbnail_loader.close()
            with suppress(OSError):
                cache.flush()
            player.close()
        finally:
            instance.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
