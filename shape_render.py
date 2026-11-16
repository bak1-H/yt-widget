import tkinter as tk
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageTk

from thumbnails import LruCache

SUPERSAMPLE = 4
IMAGE_CAPACITY = 128
PHOTO_CAPACITY = 24
TRANSPARENT = (0, 0, 0, 0)


@dataclass(frozen=True)
class RoundSpec:
    width: int
    height: int
    box: tuple[float, float, float, float]
    fill: str = ""
    outline: str = ""
    outline_width: int = 0
    ring: str = ""
    ring_width: int = 0


_images: LruCache[RoundSpec, Image.Image] = LruCache(IMAGE_CAPACITY)


def round_image(spec: RoundSpec) -> Image.Image:
    cached = _images.get(spec)
    if cached is None:
        cached = _render(spec)
        _images.put(spec, cached)
    return cached


def _render(spec: RoundSpec) -> Image.Image:
    scale = SUPERSAMPLE
    canvas = Image.new("RGBA", (spec.width * scale, spec.height * scale), TRANSPARENT)
    draw = ImageDraw.Draw(canvas)
    if spec.fill:
        _round_box(draw, spec.box, scale, fill=spec.fill)
    if spec.outline:
        _round_box(draw, spec.box, scale, outline=spec.outline, width=spec.outline_width * scale)
    if spec.ring:
        _round_box(draw, (0, 0, spec.width, spec.height), scale, outline=spec.ring, width=spec.ring_width * scale)
    return canvas.resize((spec.width, spec.height), Image.Resampling.LANCZOS)


def _round_box(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], scale: int, **style: object) -> None:
    left, top, right, bottom = (value * scale for value in box)
    draw.rounded_rectangle((left, top, right - 1, bottom - 1), radius=(bottom - top) / 2, **style)


class RoundPhotos:
    def __init__(self, owner: tk.Misc) -> None:
        self._owner = owner
        self._photos: LruCache[RoundSpec, ImageTk.PhotoImage] = LruCache(PHOTO_CAPACITY)

    def get(self, spec: RoundSpec) -> ImageTk.PhotoImage:
        photo = self._photos.get(spec)
        if photo is None:
            photo = ImageTk.PhotoImage(round_image(spec), master=self._owner)
            self._photos.put(spec, photo)
        return photo
