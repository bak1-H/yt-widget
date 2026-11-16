import io
import tkinter as tk

from PIL import Image, ImageTk

import theme
from thumbnails import ThumbnailError

ThumbnailImage = ImageTk.PhotoImage

WIDTH = 96
HEIGHT = 54


def decode_thumbnail(data: bytes) -> ImageTk.PhotoImage:
    try:
        with Image.open(io.BytesIO(data)) as source:
            return ImageTk.PhotoImage(source.convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS))
    except (OSError, ValueError, tk.TclError, Image.DecompressionBombError) as error:
        raise ThumbnailError("Could not decode the thumbnail") from error


class ThumbnailBox(tk.Canvas):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, width=WIDTH, height=HEIGHT, highlightthickness=0)
        theme.bind(self, bg="surface")
        self._image: ImageTk.PhotoImage | None = None
        self.show(None)
        theme.observe(self)

    def apply_theme(self, _theme: theme.Theme) -> None:
        self.show(self._image)

    def show(self, image: ImageTk.PhotoImage | None) -> None:
        self._image = image
        self.delete("all")
        if image is None:
            self.create_text(WIDTH // 2, HEIGHT // 2, text=theme.NOTE_GLYPH, fill=theme.color("muted"), font=theme.NOTE_FONT)
        else:
            self.create_image(0, 0, anchor="nw", image=image)
