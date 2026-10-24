"""Render glyphs from a TTF/OTF into small alpha cells (needs Pillow).

The cell metrics come from the game font, so new glyphs line up with the
old ones: cell size, baseline row, cap height, left bearing.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import fonts
from .image import Image, read_png_rgba


@dataclass
class CellSpec:
    size: int = 16        # cell is size x size
    baseline: int = 13    # last row of a capital letter
    cap: int = 12         # capital letter height in px
    left: int = 1         # ink starts at this column
    max_advance: int = 15


@dataclass
class Glyph:
    ch: str
    alpha: List[List[int]]   # size x size, 0..255
    advance: int


def _need_pillow():
    try:
        from PIL import Image as PImage, ImageDraw, ImageFont  # noqa: F401
    except ImportError:
        raise RuntimeError("font rendering needs Pillow: pip install pillow")


def find_font_size(path: str, cap: int, index: int = 0) -> int:
    """Pixel size at which a capital H is `cap` px tall."""
    _need_pillow()
    from PIL import ImageFont
    best = 12
    rp, ri = fonts.resolve(path, index)
    for px in range(8, 40):
        f = ImageFont.truetype(rp, px, index=ri)
        box = f.getbbox("H", anchor="ls")
        if -box[1] <= cap:
            best = px
    return best


def render(path: str, chars: str, spec: CellSpec, px: Optional[int] = None,
           index: int = 0, bold: int = 0) -> List[Glyph]:
    _need_pillow()
    from PIL import Image as PImage, ImageDraw, ImageFont
    px = px or find_font_size(path, spec.cap, index)
    rp, ri = fonts.resolve(path, index)
    font = ImageFont.truetype(rp, px, index=ri)
    # room for descenders: raise the baseline if g/p/у would be cut
    desc = max(font.getbbox(c, anchor="ls")[3] for c in "gjpqyруфдщ")
    baseline = min(spec.baseline, spec.size - 1 - desc)
    out = []
    for ch in chars:
        im = PImage.new("L", (spec.size * 2, spec.size), 0)
        d = ImageDraw.Draw(im)
        box = d.textbbox((0, 0), ch, font=font, anchor="ls", stroke_width=bold)
        # ink starts at `left`; baseline + 1 because pixel rows end there
        x = spec.left - box[0] if box[2] > box[0] else 0
        d.text((x, baseline + 1), ch, font=font, fill=255, anchor="ls",
               stroke_width=bold, stroke_fill=255)
        alpha = [[im.getpixel((c, r)) for c in range(spec.size)] for r in range(spec.size)]
        # as in the game font: advance = last ink column + 1; the next
        # glyph's left bearing gives the gap
        first, last = measure(alpha)
        adv = last + 1 if last >= 0 else round(font.getlength(ch))
        out.append(Glyph(ch, alpha, max(1, min(adv, spec.max_advance))))
    return out


def sheet(glyphs: List[Glyph], cols: int = 16, size: int = 16) -> Image:
    """All glyphs on one image (white on transparent), for editing."""
    rows = (len(glyphs) + cols - 1) // cols
    img = Image(cols * size, rows * size)
    for k, g in enumerate(glyphs):
        ox, oy = k % cols * size, k // cols * size
        for y in range(size):
            for x in range(size):
                img.put(ox + x, oy + y, bytes((255, 255, 255, g.alpha[y][x])))
    return img


def from_sheet(png: bytes, chars: str, advances: List[int], cols: int = 16, size: int = 16) -> List[Glyph]:
    """Read glyphs back from an edited sheet (alpha channel = ink)."""
    img = read_png_rgba(png)
    out = []
    for k, ch in enumerate(chars):
        ox, oy = k % cols * size, k // cols * size
        alpha = [[img.get(ox + x, oy + y)[3] for x in range(size)] for y in range(size)]
        out.append(Glyph(ch, alpha, advances[k]))
    return out


def measure(alpha: List[List[int]]) -> Tuple[int, int]:
    """(first, last) ink column, or (0, -1) when empty."""
    cols = [x for x in range(len(alpha[0])) if any(r[x] > 60 for r in alpha)]
    return (cols[0], cols[-1]) if cols else (0, -1)
