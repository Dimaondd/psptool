"""Tiny RGBA image + PNG writer (stdlib only)."""
import struct
import zlib
from typing import List


class Image:
    def __init__(self, w: int, h: int, px: bytearray = None):
        self.w, self.h = w, h
        self.px = px if px is not None else bytearray(w * h * 4)

    def get(self, x: int, y: int) -> bytes:
        o = (y * self.w + x) * 4
        return bytes(self.px[o:o + 4])

    def put(self, x: int, y: int, rgba: bytes):
        o = (y * self.w + x) * 4
        self.px[o:o + 4] = rgba

    def crop(self, x0: int, y0: int, w: int, h: int) -> "Image":
        out = Image(w, h)
        for y in range(h):
            s = ((y0 + y) * self.w + x0) * 4
            out.px[y * w * 4:(y + 1) * w * 4] = self.px[s:s + w * 4]
        return out

    def scaled(self, k: int) -> "Image":
        out = Image(self.w * k, self.h * k)
        for y in range(self.h):
            row = bytearray()
            for x in range(self.w):
                row += self.get(x, y) * k
            for j in range(k):
                o = (y * k + j) * out.w * 4
                out.px[o:o + len(row)] = row
        return out

    def png(self) -> bytes:
        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        stride = self.w * 4
        raw = b"".join(b"\x00" + bytes(self.px[y * stride:(y + 1) * stride]) for y in range(self.h))
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def on_background(img: Image, bg=(40, 40, 44)) -> Image:
    """Composite over an opaque colour (keeps icon colours visible)."""
    out = Image(img.w, img.h)
    for i in range(img.w * img.h):
        r, g, b, a = img.px[i * 4:i * 4 + 4]
        out.px[i * 4:i * 4 + 4] = bytes((
            (r * a + bg[0] * (255 - a)) // 255, (g * a + bg[1] * (255 - a)) // 255,
            (b * a + bg[2] * (255 - a)) // 255, 255))
    return out


def alpha_as_ink(img: Image) -> Image:
    """White-with-alpha glyphs -> black ink on white, opaque."""
    out = Image(img.w, img.h)
    for i in range(img.w * img.h):
        v = 255 - img.px[i * 4 + 3]
        out.px[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    return out


def read_png_rgba(data: bytes) -> Image:
    """Decode 8-bit RGB/RGBA/grey PNG (no interlace) -> Image."""
    pos, idat, w = 8, b"", 0
    while pos + 8 <= len(data):  # files packed in archives may have padding after IEND
        ln, t = struct.unpack_from(">I4s", data, pos)
        if t == b"IEND":
            break
        body = data[pos + 8:pos + 8 + ln]
        if t == b"IHDR":
            w, h, depth, ctype, _c, _f, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or inter:
                raise ValueError("only 8-bit non-interlaced PNG")
        elif t == b"IDAT":
            idat += body
        pos += 12 + ln
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * ch
    prev = bytearray(stride)
    img = Image(w, h)
    p = 0
    for y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for x in range(w):
            px = line[x * ch:(x + 1) * ch]
            if ch == 1:
                rgba = bytes((px[0],) * 3 + (255,))
            elif ch == 2:
                rgba = bytes((px[0],) * 3 + (px[1],))
            elif ch == 3:
                rgba = bytes(px) + b"\xff"
            else:
                rgba = bytes(px)
            img.put(x, y, rgba)
        prev = line
    return img


__all__: List[str] = ["Image", "alpha_as_ink", "on_background", "read_png_rgba"]
