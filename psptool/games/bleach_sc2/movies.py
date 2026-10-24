"""Movie subtitles: burned into the video, like the English patch did.

    texts/90NN.json            lines of movieNN.pmf: src = English (OCR of
                               the reference), start/end in frames
    movies/frames/NN_<f>.png   a clean frame of each line (preview)
    movies/built.json          what was encoded, to skip unchanged movies

Build: segments (~2 s) that show a translated line are decoded from the
original, get the text drawn on and are encoded again (x264, the same
settings as the English patch) small enough for their packs.
"""
import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ...core import ffmpeg, fonts, hdtex
from ...core.iso import IsoImage
from ...plugins.sony import hardsubs
from ...plugins.sony.psmf import Psmf

BASE = 9000                     # text entry = BASE + movie number
DIR = "/PSP_GAME/USRDIR/"
W, H = hardsubs.W, hardsubs.H
FPS = 30000 / 1001

# like the English patch: bold sans, thin outline, soft shadow
STYLE = {"ttf": "/System/Library/Fonts/Supplemental/PTSans.ttc", "index": 7, "px": 18,
         "outline": 1.25, "shadow": 1.5, "tracking": 0.5, "bottom": 8, "max_width": 450,
         "lead": 5, "tail": 5}   # frames shown before / after the English timing
SS = 4  # text is drawn this much bigger and scaled down: smooth edges
X264 = ("bframes=0:ref=1:keyint=9999:min-keyint=1:scenecut=0:8x8dct=0:aud=1:"
        "nal-hrd=vbr:vbv-maxrate=2500:vbv-bufsize=2500:chroma-qp-offset=-2")


def is_movie(entry: int) -> bool:
    return entry >= BASE


def name(entry: int) -> str:
    return "movie%02d" % (entry - BASE)


def path(entry: int) -> str:
    return DIR + name(entry) + ".pmf"


def movie_paths(iso: IsoImage) -> List[str]:
    return sorted(p for p in iso.entries if p.startswith(DIR + "movie") and p.endswith(".pmf"))


def timecode(frame: int) -> str:
    s = frame / FPS
    return "%d:%05.2f" % (s // 60, s % 60)


# --- import ------------------------------------------------------------------

def import_lines(game, ref_iso: str, log=print) -> int:
    """Lines of every movie the reference changed, read from its frames."""
    p = game.project
    total = 0
    os.makedirs(p.path("movies", "frames"), exist_ok=True)
    with IsoImage(p.iso_path) as a, IsoImage(ref_iso) as b, tempfile.TemporaryDirectory() as tmp:
        for mp in movie_paths(a):
            if mp not in b.entries:
                continue
            ja, en = a.read(mp), b.read(mp)
            if ja == en:
                continue
            entry = BASE + int(os.path.basename(mp)[5:7])
            fa, fb = os.path.join(tmp, "jp.pmf"), os.path.join(tmp, "en.pmf")
            with open(fa, "wb") as f:
                f.write(ja)
            with open(fb, "wb") as f:
                f.write(en)
            cues = hardsubs.find_cues(fa, fb, log=lambda *_: None)
            rows = []
            for c in cues:
                rid = "f%d" % c["start"]
                rows.append({"id": rid, "src": c["text"], "ref": "", "dst": "", "sub": True,
                             "start": c["start"], "end": c["end"]})
                hardsubs.frame_png(fa, (c["start"] + c["end"]) // 2, _frame_path(game, entry, rid))
            old = {r["id"]: r for r in game.load_texts(entry)} if os.path.exists(game._texts_path(entry)) else {}
            for r in rows:
                o = old.get(r["id"])
                if o:
                    r.update({k: v for k, v in o.items() if k in ("dst", "checked", "mt")})
            game._set_aside(entry, [r for k, r in old.items() if r.get("dst") and k not in {x["id"] for x in rows}])
            if rows:
                game.save_texts(entry, rows)
            log("%s: %d lines" % (name(entry), len(rows)))
            total += len(rows)
    return total


def _frame_path(game, entry: int, rid: str) -> str:
    return game.project.path("movies", "frames", "%02d_%s.png" % (entry - BASE, rid))


# --- drawing -----------------------------------------------------------------

def style(game) -> Dict:
    return dict(STYLE, **game.project.meta.get("subs_style", {}))


def _width(font, text: str, tracking: float) -> float:
    return font.getlength(text) + tracking * max(0, len(text) - 1)


def _wrap(text: str, font, width: float, tracking: float) -> List[str]:
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            t = (line + " " + word).strip()
            if line and _width(font, t, tracking) > width:
                out.append(line)
                line = word
            else:
                line = t
        out.append(line)
    return out


def draw(img: Image.Image, text: str, st: Dict) -> Image.Image:
    """Subtitle at the bottom centre: white, thin black outline, soft shadow."""
    shadow, edge, letters = _masks(text, json.dumps(st, sort_keys=True))
    if shadow:
        img.paste((0, 0, 0), mask=shadow)
    img.paste((0, 0, 0), mask=edge)
    img.paste((255, 255, 255), mask=letters)
    return img


@functools.lru_cache(maxsize=16)
def _masks(text: str, st_json: str):
    """(shadow, outline, letters) masks, drawn SS times bigger and scaled
    down for smooth edges. Cached: a line stays on screen for many frames."""
    st = json.loads(st_json)
    path, index = fonts.resolve(st["ttf"], st["index"])
    font = ImageFont.truetype(path, int(st["px"] * SS), index=index)
    track = st["tracking"] * SS
    lines = _wrap(text, font, st["max_width"] * SS, track)
    asc, desc = font.getmetrics()
    step = int((asc + desc) * 0.92)
    w, h = W * SS, H * SS
    layer = Image.new("L", (w, h))        # letters
    outline = Image.new("L", (w, h))      # letters + stroke
    dl, do = ImageDraw.Draw(layer), ImageDraw.Draw(outline)
    stroke = max(1, round(st["outline"] * SS))
    y = h - st["bottom"] * SS - step * len(lines)
    for line in lines:
        x = (w - _width(font, line, track)) / 2
        for ch in line:  # by hand: tracking
            dl.text((x, y), ch, font=font, fill=255)
            do.text((x, y), ch, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
            x += font.getlength(ch) + track
        y += step
    small = lambda im: im.resize((W, H), Image.LANCZOS)
    shadow = None
    if st.get("shadow"):
        off = round(st["shadow"] * SS)
        sh = Image.new("L", (w, h))
        sh.paste(outline, (off, off))
        shadow = small(sh).filter(ImageFilter.GaussianBlur(st["shadow"])).point(lambda v: v * 6 // 10)
    return shadow, small(outline), small(layer)


def timing(lines: List[Dict], st: Dict) -> List[Dict]:
    """Show each line a bit before / after the English timing (people
    read a moment behind the voice), never over the next / previous line."""
    out = sorted((dict(r) for r in lines), key=lambda r: r["start"])
    for k, r in enumerate(out):
        lo = out[k - 1]["end"] if k else 0
        r["start"] = max(lo, r["start"] - st.get("lead", 0))
        hi = out[k + 1]["start"] if k + 1 < len(out) else r["end"] + st.get("tail", 0)
        r["end"] = min(hi, r["end"] + st.get("tail", 0))
    return out


def preview_png(game, entry: int, rid: str, text: str) -> bytes:
    img = Image.open(_frame_path(game, entry, rid)).convert("RGB")
    if text:
        draw(img, text, style(game))
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --- build -------------------------------------------------------------------

# --- AI clean-up (Real-CUGAN): the movies stay 480x272 -------------------
# Frames go through the model at 2x and come back down: cleaner lines and
# flat fills, fewer compression blocks. Kept per mode as a near-lossless
# intermediate video, from which the build encodes the PMF.

MODES = {  # id: (label, realcugan -n)
    "conservative": ("Бережно", -1),
    "no-denoise": ("Без шумоподавления", 0),
    "denoise1x": ("Шумоподавление 1", 1),
    "denoise2x": ("Шумоподавление 2", 2),
    "denoise3x": ("Шумоподавление 3", 3),
}
CUGAN = os.path.join(os.path.expanduser("~"), ".cache", "psptool", "realcugan")


def enhance_settings(game) -> Dict:
    return dict({"on": False, "mode": "denoise1x"}, **game.project.meta.get("movie_enhance", {}))


def number(mp: str) -> int:
    return int(os.path.basename(mp)[5:7])


def enhanced_path(game, n: int, mode: str) -> str:
    return game.project.path("movies", "enhanced", mode, "movie%02d.mkv" % n)


def _cugan(src_dir: str, dst_dir: str, mode: str):
    exe = hdtex.tool_path("realcugan", "realcugan-ncnn-vulkan")
    if not os.path.exists(exe):
        raise RuntimeError("Real-CUGAN not found in " + CUGAN)
    subprocess.run([exe, "-i", src_dir, "-o", dst_dir, "-s", "2", "-n", str(MODES[mode][1]), "-m", "models-se", "-f", "png"],
                   cwd=CUGAN, check=True, capture_output=True)


def _decode(path_: str, out_pattern: str, select: str = ""):
    args = [ffmpeg.exe(), "-v", "error", "-y"]
    if path_.endswith(".pmf"):
        args += ["-skip_initial_bytes", "2048", "-f", "mpeg"]
    args += ["-i", path_, "-fps_mode", "passthrough"]
    if select:
        args += ["-vf", "select=" + select, "-frames:v", "1"]
    subprocess.run(args + [out_pattern], check=True, capture_output=True)


def enhance(game, iso: IsoImage, mode: str, log=print, progress=None, stop=None) -> int:
    """Every movie through Real-CUGAN in this mode (those not done yet)."""
    todo = [mp for mp in movie_paths(iso) if not os.path.exists(enhanced_path(game, number(mp), mode))]
    if progress is not None:
        progress[:] = [len(movie_paths(iso)) - len(todo), len(movie_paths(iso))]
    for mp in todo:
        if stop and stop():
            log("остановлено")
            return 0
        n = number(mp)
        with tempfile.TemporaryDirectory() as tmp:
            pmf = os.path.join(tmp, "in.pmf")
            with open(pmf, "wb") as f:
                f.write(iso.read(mp))
            frames = Psmf(open(pmf, "rb").read())
            want = sum(sg.frames for sg in frames.segments)
            src, up = os.path.join(tmp, "src"), os.path.join(tmp, "up")
            os.makedirs(src)
            os.makedirs(up)
            _decode(pmf, os.path.join(src, "%05d.png"))
            got = len(os.listdir(src))
            if got != want:
                raise ValueError("movie%02d: decoded %d frames, need %d" % (n, got, want))
            _cugan(src, up, mode)
            out = enhanced_path(game, n, mode)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            # near-lossless intermediate, back at 480x272; frame count kept
            subprocess.run([ffmpeg.exe(), "-v", "error", "-y", "-framerate", "30000/1001", "-i", os.path.join(up, "%05d.png"),
                            "-vf", "scale=%d:%d:flags=lanczos" % (W, H), "-c:v", "libx264", "-crf", "8", "-preset", "medium",
                            "-pix_fmt", "yuv420p", out + ".tmp.mkv"], check=True, capture_output=True)
            os.replace(out + ".tmp.mkv", out)
        if progress is not None:
            progress[0] += 1
        log("movie%02d: %d frames" % (n, want))
    return len(todo)


def preview_frame(game, n: int, frame: int, mode: str, which: str) -> bytes:
    """One frame of a movie, the original or cleaned in `mode` (cached)."""
    d = game.project.path("movies", "preview")
    os.makedirs(d, exist_ok=True)
    orig = os.path.join(d, "%02d_%05d_orig.png" % (n, frame))
    if not os.path.exists(orig):
        with IsoImage(game.project.iso_path) as iso, tempfile.TemporaryDirectory() as tmp:
            pmf = os.path.join(tmp, "in.pmf")
            with open(pmf, "wb") as f:
                f.write(iso.read(DIR + "movie%02d.pmf" % n))
            _decode(pmf, orig, "eq(n\\,%d)" % frame)
    if which == "orig":
        with open(orig, "rb") as f:
            return f.read()
    out = os.path.join(d, "%02d_%05d_%s.png" % (n, frame, mode))
    if not os.path.exists(out):
        with tempfile.TemporaryDirectory() as tmp:
            src, up = os.path.join(tmp, "src"), os.path.join(tmp, "up")
            os.makedirs(src)
            os.makedirs(up)
            shutil.copyfile(orig, os.path.join(src, "f.png"))
            _cugan(src, up, mode)
            Image.open(os.path.join(up, "f.png")).convert("RGB").resize((W, H), Image.LANCZOS).save(out)
    with open(out, "rb") as f:
        return f.read()


def movie_list(game, iso: IsoImage) -> List[Dict]:
    mode = enhance_settings(game)["mode"]
    out = []
    for mp in movie_paths(iso):
        n = number(mp)
        m = Psmf(iso.read(mp))
        out.append({"n": n, "frames": sum(sg.frames for sg in m.segments),
                    "ready": os.path.exists(enhanced_path(game, n, mode))})
    return out


# --- build -------------------------------------------------------------------

def build(game, iso: IsoImage, log=print) -> List[str]:
    """files/PSP_GAME/USRDIR/movieNN.pmf for movies with translated lines
    and, with the clean-up on, for every movie cleaned in its mode.
    Returns errors."""
    p = game.project
    st = style(game)
    enh = enhance_settings(game)
    done_path = p.path("movies", "built.json")
    try:
        with open(done_path) as f:
            done = json.load(f)
    except (OSError, ValueError):
        done = {}
    errors = []
    now = {}
    for mp in movie_paths(iso):
        n = number(mp)
        entry = BASE + n
        lines = [r for r in game.load_texts(entry) if r.get("dst")] if entry in game.text_entries() else []
        clean = enhanced_path(game, n, enh["mode"]) if enh["on"] else None
        if clean and not os.path.exists(clean):
            clean = None  # not prepared: the original frames
        if not lines and not clean:
            continue
        rel = "files" + mp
        key = hashlib.sha1(json.dumps([st, X264, [(r["start"], r["end"], r["dst"]) for r in lines],
                                       clean and [enh["mode"], os.path.getmtime(clean)]], sort_keys=True).encode()).hexdigest()
        now[rel] = key
        if done.get(rel) == key and os.path.exists(p.path(rel)):
            continue
        log("movie%02d: %d lines%s" % (n, len(lines), ", " + MODES[enh["mode"]][0] if clean else ""))
        try:
            data = _burn(iso.read(mp), timing(lines, st), st, log, frames=clean)
        except (ValueError, subprocess.CalledProcessError) as ex:
            errors.append("movie%02d: %s" % (n, ex))
            now.pop(rel)
            continue
        os.makedirs(os.path.dirname(p.path(rel)), exist_ok=True)
        with open(p.path(rel), "wb") as f:
            f.write(data)
    # movies no longer changed go back to the original
    for rel in done:
        if rel not in now and os.path.exists(p.path(rel)):
            os.remove(p.path(rel))
    os.makedirs(os.path.dirname(done_path), exist_ok=True)
    with open(done_path, "w") as f:
        json.dump(now, f, indent=1)
    return errors


def _burn(pmf: bytes, lines: List[Dict], st: Dict, log, frames: Optional[str] = None) -> bytes:
    """Segments that show a line get it drawn on; `frames` (a cleaned
    video with the same frames): every segment is taken from it."""
    m = Psmf(pmf)
    first = []
    n = 0
    for s in m.segments:
        first.append(n)
        n += s.frames
    todo = [k for k, s in enumerate(m.segments)
            if frames or any(r["start"] < first[k] + s.frames and r["end"] > first[k] for r in lines)]
    with tempfile.TemporaryDirectory() as tmp:
        src = frames
        if not src:
            src = os.path.join(tmp, "in.pmf")
            with open(src, "wb") as f:
                f.write(pmf)
        pre = ["-skip_initial_bytes", "2048", "-f", "mpeg"] if src.endswith(".pmf") else []
        for k in todo:
            seg = m.segments[k]
            a, b = first[k], first[k] + seg.frames
            raw = subprocess.run([ffmpeg.exe(), "-v", "error"] + pre + ["-i", src,
                                  "-fps_mode", "passthrough", "-vf", "select=between(n\\,%d\\,%d)" % (a, b - 1),
                                  "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                                 capture_output=True, check=True).stdout
            size = W * H * 3
            if len(raw) != size * seg.frames:
                raise ValueError("segment %d: decoded %d frames, need %d" % (k, len(raw) // size, seg.frames))
            buf = bytearray()
            for f in range(seg.frames):
                img = Image.frombytes("RGB", (W, H), raw[f * size:(f + 1) * size])
                text = next((r["dst"] for r in lines if r["start"] <= a + f < r["end"]), None)
                if text:
                    draw(img, text, st)
                buf += img.tobytes()
            es = _encode(bytes(buf), m.capacity(seg))
            m.replace_segment(k, es)
        log("  %d of %d segments re-encoded" % (len(todo), len(m.segments)))
    return m.bytes()


def _encode(rgb: bytes, room: int, with_crf: bool = False):
    """Best quality that fits `room` bytes (and the crf it took)."""
    for crf in (13, 16, 19, 22, 25, 28, 32, 36, 40, 45, 51):
        es = subprocess.run([ffmpeg.exe(), "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                             "-r", "30000/1001", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-profile:v", "main", "-level", "2.1", "-x264-params", "crf=%d:%s" % (crf, X264),
                             "-f", "h264", "-"], input=rgb, capture_output=True, check=True).stdout
        if len(es) <= room:
            return (es, crf) if with_crf else es
    raise ValueError("segment does not fit even at the lowest quality")
