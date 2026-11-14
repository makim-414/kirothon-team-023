"""Image helpers: numbered thumbnail grid and resized JPEG export."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

THUMB = 400
COLS = 4
PAD = 8


def _font(size: int):
    for f in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


def open_rgb(path: str | Path) -> Image.Image:
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def to_jpeg(path: str | Path, max_side: int | None = None, quality: int = 90) -> tuple[bytes, tuple[int, int]]:
    im = open_rgb(path)
    if max_side and max(im.size) > max_side:
        im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue(), im.size


def grid(paths: list[str | Path]) -> bytes:
    """Numbered grid (1..n), max 4 columns, each cell up to 400x400 keeping aspect."""
    if not paths:
        raise ValueError("no images")
    cols = min(COLS, len(paths))
    rows = (len(paths) + cols - 1) // cols
    cell = THUMB + PAD
    sheet = Image.new("RGB", (cols * cell + PAD, rows * cell + PAD), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    font = _font(44)
    for i, p in enumerate(paths):
        r, c = divmod(i, cols)
        x0, y0 = PAD + c * cell, PAD + r * cell
        try:
            im = open_rgb(p)
            im.thumbnail((THUMB, THUMB))
        except Exception:
            im = Image.new("RGB", (THUMB, THUMB), (90, 0, 0))
        ox = x0 + (THUMB - im.width) // 2
        oy = y0 + (THUMB - im.height) // 2
        sheet.paste(im, (ox, oy))
        label = str(i + 1)
        bx = draw.textbbox((0, 0), label, font=font)
        w, h = bx[2] - bx[0], bx[3] - bx[1]
        draw.rounded_rectangle((x0, y0, x0 + w + 24, y0 + h + 24), radius=10, fill=(255, 196, 0))
        draw.text((x0 + 12 - bx[0], y0 + 12 - bx[1]), label, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=85)
    return buf.getvalue()
