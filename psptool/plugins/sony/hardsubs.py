"""Find burned-in subtitles of one movie version (e.g. a fan translation)
by comparing its frames with the original, and read them with OCR.

Frames are decoded with ffmpeg in decode order (no frame rate fixing),
so frame numbers match the access units of the PSMF video stream.
"""
import os
import subprocess
import tempfile
from typing import Dict, List

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from ...core import ffmpeg

W, H = 480, 272
STRONG = 60       # luma difference that is text, not re-encoding noise
MIN_PIXELS = 40   # strong pixels in a frame to count as "has subtitles"


def frames_gray(pmf: str) -> List[bytes]:
    raw = subprocess.run([ffmpeg.exe(), "-v", "error", "-skip_initial_bytes", "2048", "-f", "mpeg", "-i", pmf,
                          "-fps_mode", "passthrough", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    n = W * H
    return [raw[k * n:(k + 1) * n] for k in range(len(raw) // n)]


def frame_png(pmf: str, k: int, out: str):
    subprocess.run([ffmpeg.exe(), "-v", "error", "-y", "-skip_initial_bytes", "2048", "-f", "mpeg", "-i", pmf,
                    "-fps_mode", "passthrough", "-vf", "select=eq(n\\,%d)" % k, "-frames:v", "1", out],
                   check=True, capture_output=True)


def _mask(a: bytes, b: bytes) -> Image.Image:
    """1-bit image: where b has text (bright letters, dark outline) a lacks."""
    d = ImageChops.difference(Image.frombytes("L", (W, H), a), Image.frombytes("L", (W, H), b))
    return d.point(lambda v: 255 if v > STRONG else 0).convert("1")


def _letters(a: bytes, b: bytes, box) -> Image.Image:
    """The subtitle alone for Tesseract, black letters on white, 3x: the
    bright fill of b's letters is what their dark outline encloses, so
    flood the bright picture around the outlines away from the edges."""
    near = _mask(a, b).filter(ImageFilter.MaxFilter(5))
    bright = Image.frombytes("L", (W, H), b).point(lambda v: 255 if v > 140 else 0).convert("1")
    ink = ImageChops.logical_or(bright, ImageChops.invert(near))  # far from the subtitle: flooded too
    x0, y0, x1, y1 = box or (0, 0, W, H)
    ink = ink.crop((max(0, x0 - 8), max(0, y0 - 8), min(W, x1 + 8), min(H, y1 + 8)))
    big = Image.new("L", (ink.width + 2, ink.height + 2), 255)
    big.paste(ink.convert("L"), (1, 1))
    ImageDraw.floodfill(big, (0, 0), 0)
    letters = big.crop((1, 1, ink.width + 1, ink.height + 1))
    return ImageChops.invert(letters).resize((letters.width * 3, letters.height * 3), Image.LANCZOS)


def _count(m: Image.Image) -> int:
    return m.histogram()[-1]


def find_cues(orig: str, subbed: str, log=print) -> List[Dict]:
    """[{start, end, text}] in frames, end exclusive."""
    a, b = frames_gray(orig), frames_gray(subbed)
    if len(a) != len(b):
        raise ValueError("%s: %d frames, %s: %d" % (orig, len(a), subbed, len(b)))
    spans = []  # [start, end]
    prev = None
    for k in range(len(a)):
        m = _mask(a[k], b[k])
        n = _count(m)
        if n < MIN_PIXELS:
            prev = None
            continue
        # same text as the frame before: the masks overlap a lot
        if prev is not None and _count(ImageChops.logical_and(m, prev[0])) > 0.5 * min(n, prev[1]):
            spans[-1][1] = k + 1
        else:
            spans.append([k, k + 1])
        prev = (m, n)
    spans = [s for s in spans if s[1] - s[0] >= 6]  # flicker, not a line
    log("  %d subtitle spans" % len(spans))
    from ...core import ocr
    tess = ocr.engine() == "tesseract"
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for n, (s, e) in enumerate(spans):
            p = os.path.join(tmp, "%04d.png" % n)
            k = (s + e) // 2
            box = _mask(a[k], b[k]).getbbox()
            if tess:  # Tesseract reads clean pages: only the letters the subtitle added
                _letters(a[k], b[k], box).save(p)
                files.append(p)
                continue
            frame_png(subbed, k, p)
            # only the subtitle area: no signs or titles from the picture
            if box:
                Image.open(p).crop((0, max(0, box[1] - 6), W, min(H, box[3] + 6))).resize(
                    (W * 2, (min(H, box[3] + 6) - max(0, box[1] - 6)) * 2), Image.LANCZOS).save(p)
            files.append(p)
        found = ocr.recognize(files, sparse=False) if files else {}
    cues = []
    for (s, e), p in zip(spans, files):
        lines = [l["text"] for l in found.get(p, []) if l["conf"] > 0.3]
        text = "\n".join(lines).strip()
        if not text:
            continue
        if cues and cues[-1]["text"] == text and s - cues[-1]["end"] <= 3:
            cues[-1]["end"] = e
            continue
        cues.append({"start": s, "end": e, "text": text})
    return cues
