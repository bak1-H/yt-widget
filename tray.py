from typing import Callable

import pystray
from PIL import Image, ImageDraw

import texts
import theme

ICON_SIZE = 64
ICON_RADIUS = 14
PLAY_TRIANGLE = [(24, 18), (24, 46), (48, 32)]

Action = Callable[[], None]


class TrayIcon:
    def __init__(
        self,
        *,
        on_toggle: Action,
        on_play_pause: Action,
        on_next: Action,
        on_quit: Action,
        schedule: Callable[[Action], None],
    ) -> None:
        self._schedule = schedule
        menu = pystray.Menu(
            pystray.MenuItem(texts.TRAY_TOGGLE, self._dispatch(on_toggle), default=True),
            pystray.MenuItem(texts.TRAY_PLAY_PAUSE, self._dispatch(on_play_pause)),
            pystray.MenuItem(texts.TRAY_NEXT, self._dispatch(on_next)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(texts.TRAY_QUIT, self._dispatch(on_quit)),
        )
        self._icon = pystray.Icon("yt-widget", draw_icon(theme.current()), texts.APP_TITLE, menu)
        theme.observe(self)

    def start(self) -> None:
        self._icon.run_detached()

    def stop(self) -> None:
        self._icon.stop()

    def apply_theme(self, palette: theme.Theme) -> None:
        self._icon.icon = draw_icon(palette)

    def _dispatch(self, action: Action) -> Callable[[pystray.Icon, pystray.MenuItem], None]:
        return lambda _icon, _item: self._schedule(action)


def draw_icon(palette: theme.Theme) -> Image.Image:
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    canvas.rounded_rectangle((0, 0, ICON_SIZE - 1, ICON_SIZE - 1), radius=ICON_RADIUS, fill=palette.accent)
    canvas.polygon(PLAY_TRIANGLE, fill=palette.background)
    return image
