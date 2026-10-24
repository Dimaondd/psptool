"""Typeset a translation into a texture: find the text (OCR), wipe it,
guess its colours, draw the new text with a TTF to fit the same box.

A layout (what the user can tweak) is plain JSON:
    {"font": "pt-sans-bold", "note": "...",
     "boxes": [{"x", "y", "w", "h", "src", "ref", "dst",
                "fill": "#rrggbb", "outline": "#rrggbb" | null, "ow": 1,
                "size": px | null (fit), "on": true}]}
"""
import os
import tempfile
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import fonts as fontfiles

FONTS = {
    "pt-sans-bold": ("/System/Library/Fonts/Supplemental/PTSans.ttc", 7, "PT Sans Bold"),
    "pt-sans-bold-italic": ("/System/Library/Fonts/Supplemental/PTSans.ttc", 6, "PT Sans Bold Italic"),
    "pt-sans": ("/System/Library/Fonts/Supplemental/PTSans.ttc", 0, "PT Sans"),
    "pt-sans-narrow-bold": ("/System/Library/Fonts/Supplemental/PTSans.ttc", 2, "PT Sans Narrow Bold"),
    "pt-sans-caption-bold": ("/System/Library/Fonts/Supplemental/PTSans.ttc", 4, "PT Sans Caption Bold"),
    "arial-black": ("/System/Library/Fonts/Supplemental/Arial Black.ttf", 0, "Arial Black"),
    "georgia-bold": ("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", 0, "Georgia Bold"),
}
SS = 4          # supersampling for smooth text
FAR = 48        # colour distance: text vs background


def fonts() -> List[Dict]:
    return [{"id": k, "name": v[2]} for k, v in FONTS.items() if fontfiles.exists(v[0], v[1])]


# --- finding text ----------------------------------------------------------

def detect(img: Image.Image, lang: str) -> List[Dict]:
    """Text lines: [{x, y, w, h, text}] in texture pixels."""
    from . import ocr
    rgba = img.convert("RGBA")
    # OCR wants big, opaque pictures: scale small textures up, put
    # transparent ones on a background that contrasts with their pixels
    k = max(1, -(-512 // max(rgba.size)))
    lum = [p[0] * 0.3 + p[1] * 0.59 + p[2] * 0.11 for p in rgba.getdata() if p[3] > 128]
    bg = (40, 40, 40) if not lum or sum(lum) / len(lum) > 110 else (220, 220, 220)
    flat = Image.new("RGB", rgba.size, bg)
    flat.paste(rgba, mask=rgba.getchannel("A"))
    if ocr.engine() == "tesseract":  # wants big, black-on-white letters
        k = max(k, min(4, 2048 // max(rgba.size)))
        flat = ImageOps.autocontrast(flat.convert("L"))
        if bg[0] < 128:
            flat = ImageOps.invert(flat)
    flat = flat.resize((rgba.width * k, rgba.height * k), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "t.png")
        flat.save(p)
        lines = ocr.recognize([p], lang).get(p, [])
    out = []
    for l in lines:
        x, y = l["x"] * rgba.width, l["y"] * rgba.height
        w, h = l["w"] * rgba.width, l["h"] * rgba.height
        box = {"x": max(0, int(x) - 1), "y": max(0, int(y) - 1),
               "w": min(rgba.width, int(x + w + 2.999)) - max(0, int(x) - 1),
               "h": min(rgba.height, int(y + h + 2.999)) - max(0, int(y) - 1),
               "text": l["text"]}
        out.append(box)
    return out


def overlap(a: Dict, b: Dict) -> float:
    """Intersection over the smaller box."""
    ix = max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return ix * iy / max(1, min(a["w"] * a["h"], b["w"] * b["h"]))


# --- colours ---------------------------------------------------------------

def _dist(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


def _median(px: List[Tuple]) -> Tuple:
    if not px:
        return (0, 0, 0, 0)
    return tuple(sorted(p[i] for p in px)[len(px) // 2] for i in range(4))


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(c[:3])


def _rgb(h: str) -> Tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _ring(img: Image.Image, b: Dict, d: int = 2) -> List[Tuple]:
    """Pixels just around the box: the background."""
    W, H = img.size
    px = img.load()
    out = []
    for y in range(b["y"] - d, b["y"] + b["h"] + d):
        for x in range(b["x"] - d, b["x"] + b["w"] + d):
            if 0 <= x < W and 0 <= y < H and not (b["x"] <= x < b["x"] + b["w"] and b["y"] <= y < b["y"] + b["h"]):
                out.append(px[x, y])
    return out


def _transparent(ring: List[Tuple]) -> bool:
    return bool(ring) and sum(1 for p in ring if p[3] < 64) > 0.6 * len(ring)


def text_mask(img: Image.Image, b: Dict) -> set:
    """Pixels of the box that are text, not background."""
    px = img.load()
    ring = _ring(img, b)
    clear = _transparent(ring)
    bg = _median([p for p in ring if p[3] >= 64]) if not clear else None
    out = set()
    for y in range(b["y"], b["y"] + b["h"]):
        for x in range(b["x"], b["x"] + b["w"]):
            p = px[x, y]
            if (p[3] > 128) if clear else (p[3] > 128 and _dist(p, bg) > FAR):
                out.add((x, y))
    return out


def _two_colours(px: List[Tuple]) -> Tuple[Tuple, Tuple, List[int]]:
    """k-means with k=2 on RGB: (centre a, centre b, label per pixel)."""
    lum = lambda p: p[0] * 0.3 + p[1] * 0.59 + p[2] * 0.11
    srt = sorted(px, key=lum)
    c = [srt[len(srt) // 10], srt[len(srt) * 9 // 10]]
    lab = [0] * len(px)
    for _ in range(8):
        lab = [0 if _dist(p, c[0]) <= _dist(p, c[1]) else 1 for p in px]
        for k in (0, 1):
            grp = [p for p, l in zip(px, lab) if l == k]
            if grp:
                c[k] = tuple(sum(p[i] for p in grp) // len(grp) for i in range(3))
    return c[0], c[1], lab


def guess_style(img: Image.Image, b: Dict) -> Dict:
    """Fill and outline colours of the text in the box. Text pixels split
    in two colours: the one touching the background is the outline."""
    img = img.convert("RGBA")
    px = img.load()
    mask = text_mask(img, b)
    if len(mask) < 4:
        return {"fill": "#ffffff", "outline": "#000000", "ow": 1}
    pts = list(mask)
    cols = [px[x, y] for x, y in pts]
    ca, cb, lab = _two_colours(cols)
    if _dist(ca, cb) < FAR:  # one colour: no outline
        return {"fill": _hex(_median(cols)), "outline": None, "ow": 1}
    touch = [0, 0]
    count = [lab.count(0), lab.count(1)]
    for (x, y), l in zip(pts, lab):
        if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            touch[l] += 1
    o = 0 if touch[0] / max(1, count[0]) > touch[1] / max(1, count[1]) else 1
    fill, line = (cb, ca) if o == 0 else (ca, cb)
    # outline thickness: its pixels over the pixels on the text's border
    ow = max(1.0, min(3.0, round(2 * count[o] / max(1, touch[o])) / 2))
    return {"fill": _hex(fill), "outline": _hex(line), "ow": ow}


def has_japanese(s: str) -> bool:
    return any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF for c in s)


# --- wiping ----------------------------------------------------------------

def erase(img: Image.Image, b: Dict) -> Image.Image:
    """Remove the text of a box: transparent background -> clear pixels;
    otherwise fill from the edges inwards and smooth (plates, gradients)."""
    img = img.convert("RGBA")
    px = img.load()
    W, H = img.size
    ring = _ring(img, b)
    x0, y0 = max(0, b["x"]), max(0, b["y"])
    x1, y1 = min(W, b["x"] + b["w"]), min(H, b["y"] + b["h"])
    if _transparent(ring):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (0, 0, 0, 0)
        return img
    hole = {(x, y) for y in range(y0, y1) for x in range(x0, x1)}
    val = {}
    # onion peel: each pass fills the hole pixels next to known ones
    while hole:
        step = {}
        for (x, y) in hole:
            ns = [val.get((x + dx, y + dy)) or (px[x + dx, y + dy] if (x + dx, y + dy) not in hole and 0 <= x + dx < W and 0 <= y + dy < H else None)
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
            ns = [n for n in ns if n is not None and (x, y) not in val]
            if ns:
                step[(x, y)] = tuple(sum(n[i] for n in ns) // len(ns) for i in range(4))
        if not step:
            break
        val.update(step)
        hole -= set(step)
    # smooth the streaks: average with the 4 neighbours, edges fixed
    pts = list(val)
    for _ in range(20):
        new = {}
        for (x, y) in pts:
            ns = [val.get((x + dx, y + dy)) or px[x + dx, y + dy]
                  for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x + dx < W and 0 <= y + dy < H]
            new[(x, y)] = tuple(sum(n[i] for n in ns) // len(ns) for i in range(4))
        val = new
    for (x, y), c in val.items():
        px[x, y] = c
    return img


# --- drawing ---------------------------------------------------------------

def _font(fid: str, size: float):
    path, index, _ = FONTS.get(fid) or FONTS["pt-sans-bold"]
    path, index = fontfiles.resolve(path, index)
    return ImageFont.truetype(path, max(1, int(size * SS)), index=index)


def _measure(font, lines: List[str], ow: float) -> Tuple[float, float]:
    asc, desc = font.getmetrics()
    w = max((font.getlength(l) for l in lines), default=0) + 2 * ow * SS
    return w, (asc + desc) * len(lines) + 2 * ow * SS


def fit_size(b: Dict, text: str, fid: str) -> float:
    """Biggest size that fits the box (a little over is fine: the
    original text box from OCR is tight)."""
    lines = text.split("\n")
    ow = b.get("ow", 1) if b.get("outline") else 0
    size = b["h"] * 1.25 / len(lines)
    while size > 5:
        w, h = _measure(_font(fid, size), lines, ow)
        if w <= b["w"] * SS * 1.04 and h <= b["h"] * SS * 1.3:
            break
        size -= 0.5
    return size


def draw(img: Image.Image, b: Dict, fid: str) -> Image.Image:
    """The box's dst, centred in the box."""
    text = b.get("dst", "")
    if not text:
        return img
    size = b.get("size") or fit_size(b, text, fid)
    font = _font(fid, size)
    lines = text.split("\n")
    ow = b.get("ow", 1) if b.get("outline") else 0
    W, H = img.size
    letters = Image.new("L", (W * SS, H * SS))
    stroke = Image.new("L", (W * SS, H * SS))
    dl, ds = ImageDraw.Draw(letters), ImageDraw.Draw(stroke)
    asc, desc = font.getmetrics()
    step = asc + desc
    tw, th = _measure(font, lines, 0)
    cy = (b["y"] + b["h"] / 2) * SS - th / 2
    for line in lines:
        lw = font.getlength(line)
        x = (b["x"] + b["w"] / 2) * SS - lw / 2
        dl.text((x, cy), line, font=font, fill=255)
        if ow:
            ds.text((x, cy), line, font=font, fill=255, stroke_width=max(1, round(ow * SS)), stroke_fill=255)
        cy += step
    small = lambda m: m.resize((W, H), Image.LANCZOS)
    out = img.convert("RGBA")
    if ow:
        layer = Image.new("RGBA", (W, H), _rgb(b["outline"]) + (0,))
        layer.putalpha(small(stroke))
        out = Image.alpha_composite(out, layer)
    layer = Image.new("RGBA", (W, H), _rgb(b.get("fill") or "#ffffff") + (0,))
    layer.putalpha(small(letters))
    return Image.alpha_composite(out, layer)


def render(orig: Image.Image, layout: Dict) -> Image.Image:
    """Original texture -> with the layout's boxes wiped and redrawn."""
    img = orig.convert("RGBA")
    boxes = [b for b in layout.get("boxes", []) if b.get("on", True)]
    for b in boxes:
        img = erase(img, b)
    for b in boxes:
        img = draw(img, b, layout.get("font", "pt-sans-bold"))
    return img
