"""Sony GIM texture (MIG.00.1PSP): read images and write pixels back.

Blocks: u16 id, u16 _, u32 size, u32 next, u32 data_offset. Ids:
2 root, 3 picture, 4 image, 5 palette. Image/palette header (at data):
u16 hdr_len, u16 _, u16 format, u16 order, u16 width, u16 height, ...,
u32 at +0x1c = pixel offset from header start.
Formats: 0 RGB565, 1 RGBA5551, 2 RGBA4444, 3 RGBA8888, 4 idx4, 5 idx8.
Order 1 = PSP swizzle (16 bytes x 8 rows blocks).
"""
import struct
from dataclasses import dataclass
from typing import List, Tuple

from ...core.image import Image

MAGIC = b"MIG.00.1PSP\x00"
BPP = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}


@dataclass
class GimImage:
    fmt: int
    order: int
    w: int
    h: int
    pix_pos: int      # absolute offset of pixels in the GIM blob
    stride: int       # bytes per row, padded to 16
    rows: int         # rows, padded to 8 when swizzled


@dataclass
class GimPalette:
    fmt: int
    count: int
    pos: int


def _blocks(b: bytes, off: int, end: int, out_img, out_pal):
    while off + 16 <= end:
        bid, _, size, _nxt, doff = struct.unpack_from("<HHIII", b, off)
        if size == 0:
            break
        d = off + doff
        if bid in (4, 5):
            _hl, _, fmt, order, w, h = struct.unpack_from("<6H", b, d)
            pix = d + struct.unpack_from("<I", b, d + 0x1C)[0]
            if bid == 4:
                stride = (w * BPP[fmt] // 8 + 15) // 16 * 16
                rows = (h + 7) // 8 * 8 if order == 1 else h
                out_img.append(GimImage(fmt, order, w, h, pix, stride, rows))
            else:
                out_pal.append(GimPalette(fmt, w * h, pix))
        elif bid in (2, 3):
            _blocks(b, d, off + size, out_img, out_pal)
        off += size


def parse(b: bytes):
    if b[:12] != MAGIC:
        raise ValueError("not a GIM")
    imgs: List[GimImage] = []
    pals: List[GimPalette] = []
    _blocks(b, 0x10, len(b), imgs, pals)
    return imgs, pals


def unswizzle(data: bytes, stride: int, rows: int) -> bytes:
    out = bytearray(stride * rows)
    i = 0
    for by in range(0, rows, 8):
        for bx in range(0, stride, 16):
            for y in range(8):
                o = (by + y) * stride + bx
                out[o:o + 16] = data[i:i + 16]
                i += 16
    return bytes(out)


def swizzle(data: bytes, stride: int, rows: int) -> bytes:
    out = bytearray(stride * rows)
    i = 0
    for by in range(0, rows, 8):
        for bx in range(0, stride, 16):
            for y in range(8):
                o = (by + y) * stride + bx
                out[i:i + 16] = data[o:o + 16]
                i += 16
    return bytes(out)


def palette_rgba(b: bytes, p: GimPalette) -> List[bytes]:
    out = []
    for k in range(p.count):
        if p.fmt == 3:
            out.append(b[p.pos + 4 * k:p.pos + 4 * k + 4])
            continue
        v = struct.unpack_from("<H", b, p.pos + 2 * k)[0]
        if p.fmt == 2:
            out.append(bytes(((v & 15) * 17, (v >> 4 & 15) * 17, (v >> 8 & 15) * 17, (v >> 12) * 17)))
        elif p.fmt == 1:
            out.append(bytes(((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 255 * (v >> 15))))
        else:
            out.append(bytes(((v & 31) << 3, (v >> 5 & 63) << 2, (v >> 11) << 3, 255)))
    return out


def indices(b: bytes, im: GimImage) -> List[bytes]:
    """Rows of raw pixel bytes (unswizzled), `h` of them."""
    raw = b[im.pix_pos:im.pix_pos + im.stride * im.rows]
    if im.order == 1:
        raw = unswizzle(raw, im.stride, im.rows)
    return [raw[y * im.stride:(y + 1) * im.stride] for y in range(im.h)]


def decode(b: bytes, index: int = 0, palette: int = None) -> Image:
    imgs, pals = parse(b)
    im = imgs[index]
    if palette is None:
        palette = min(index, len(pals) - 1)
    pal = palette_rgba(b, pals[palette]) if pals else None
    out = Image(im.w, im.h)
    for y, row in enumerate(indices(b, im)):
        for x in range(im.w):
            if im.fmt == 4:
                i = (row[x >> 1] >> (4 * (x & 1))) & 15
            elif im.fmt == 5:
                i = row[x]
            elif im.fmt == 3:
                out.put(x, y, row[4 * x:4 * x + 4])
                continue
            else:
                raise NotImplementedError("GIM format %d" % im.fmt)
            out.put(x, y, pal[i] if pal and i < len(pal) else bytes((i, i, i, 255)))
    return out


def write_indices(b: bytearray, im: GimImage, rows: List[bytes]):
    """Put rows of raw pixel bytes back (swizzling if needed)."""
    raw = bytearray(im.stride * im.rows)
    for y, r in enumerate(rows):
        raw[y * im.stride:y * im.stride + len(r)] = r
    if im.order == 1:
        raw = swizzle(bytes(raw), im.stride, im.rows)
    b[im.pix_pos:im.pix_pos + len(raw)] = raw


def find(blob: bytes) -> List[Tuple[int, int]]:
    """GIMs inside a blob (also embedded in other containers):
    [(offset, length)]. Length comes from the root block size."""
    out = []
    pos = blob.find(MAGIC)
    while pos >= 0:
        if pos + 0x20 <= len(blob):
            bid, _, size = struct.unpack_from("<HHI", blob, pos + 0x10)
            if bid == 2 and 0 < size <= len(blob) - pos - 0x10:
                out.append((pos, 0x10 + size))
                pos = blob.find(MAGIC, pos + 0x10 + size)
                continue
        pos = blob.find(MAGIC, pos + 4)
    return out


def _nearest(pal: List[bytes]):
    cache = {}

    def pick(px: bytes) -> int:
        i = cache.get(px)
        if i is None:
            r, g, b, a = px
            best, i = None, 0
            for k, (pr, pg, pb, pa) in enumerate(pal):
                # alpha matters most: text edges over transparent backgrounds
                d = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2 + 3 * (pa - a) ** 2
                if best is None or d < best:
                    best, i = d, k
            cache[px] = i
        return i
    return pick


def encode(b: bytes, img: "Image", index: int = 0, palette: int = None) -> bytes:
    """New GIM bytes with image `index` replaced by `img` (same size).
    Indexed formats keep their palette: each pixel takes the nearest
    colour, so redraw text in the colours the texture already uses."""
    imgs, pals = parse(b)
    im = imgs[index]
    if (img.w, img.h) != (im.w, im.h):
        raise ValueError("image must be %dx%d, got %dx%d" % (im.w, im.h, img.w, img.h))
    out = bytearray(b)
    rows = []
    if im.fmt == 3:
        for y in range(im.h):
            rows.append(bytes(img.px[y * img.w * 4:(y + 1) * img.w * 4]))
    elif im.fmt in (4, 5):
        if palette is None:
            palette = min(index, len(pals) - 1)
        pick = _nearest(palette_rgba(b, pals[palette]))
        for y in range(im.h):
            idx = [pick(img.get(x, y)) for x in range(im.w)]
            if im.fmt == 5:
                rows.append(bytes(idx))
            else:
                rows.append(bytes((idx[x] & 15) | ((idx[x + 1] & 15) << 4 if x + 1 < im.w else 0)
                                  for x in range(0, im.w, 2)))
    else:
        raise NotImplementedError("GIM format %d" % im.fmt)
    write_indices(out, im, rows)
    return bytes(out)


_SWAP_NIBBLES = bytes(((v & 15) << 4) | (v >> 4) for v in range(256))


def to_pil(b: bytes, index: int = 0, palette: int = None):
    """Fast decode with Pillow -> RGBA PIL image (w x h)."""
    from PIL import Image as PImage
    imgs, pals = parse(b)
    im = imgs[index]
    raw = b[im.pix_pos:im.pix_pos + im.stride * im.rows]
    if im.order == 1:
        raw = unswizzle(raw, im.stride, im.rows)
    bpp = BPP[im.fmt]
    width = im.stride * 8 // bpp
    if im.fmt == 3:
        out = PImage.frombytes("RGBA", (width, im.rows), raw)
    elif im.fmt in (4, 5):
        if palette is None:
            palette = min(index, len(pals) - 1)
        pal = b"".join(palette_rgba(b, pals[palette])) if pals else bytes(range(256)) * 4
        pal = pal[:1024].ljust(1024, b"\0")
        if im.fmt == 4:  # PSP: low nibble first, Pillow: high nibble first
            out = PImage.frombytes("P", (width, im.rows), raw.translate(_SWAP_NIBBLES), "raw", "P;4")
        else:
            out = PImage.frombytes("P", (width, im.rows), raw)
        out.putpalette(pal, "RGBA")
        out = out.convert("RGBA")
    else:  # 16-bit direct colour: rare, the slow path is fine
        import io
        return PImage.open(io.BytesIO(decode(b, index, palette).png())).convert("RGBA")
    return out.crop((0, 0, im.w, im.h))
