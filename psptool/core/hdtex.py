"""HD texture pack for PPSSPP: the game stays as it is, the emulator swaps
textures for bigger PNGs while drawing (real PSPs never see the pack).

Flow: PPSSPP dumps every texture it meets ("Save new textures") into
PSP/TEXTURES/<DISC_ID>/new/<hash>.png; we upscale them (waifu2x,
Real-CUGAN or Real-ESRGAN, ncnn-vulkan builds in ~/.cache/psptool) into
PSP/TEXTURES/<DISC_ID>/<hash>.png, which PPSSPP loads by name.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Dict, List, Optional

import json
import time

from PIL import Image, ImageChops, ImageStat

ROOTS = ["~/.config/ppsspp/PSP", "~/Documents/PPSSPP/PSP", "~/Library/Application Support/PPSSPP/PSP",
         r"C:\Program Files\PPSSPP\memstick\PSP"]
TOOLS = os.path.join(os.path.expanduser("~"), ".cache", "psptool")
# id: label, program dir, executable, args(scale), native scales.
# A scale the model lacks is made with the next bigger one, then scaled down.
MODELS = {
    "waifu2x": ("waifu2x — бережно", "waifu2x", "waifu2x-ncnn-vulkan",
                lambda s: ["-n", "0", "-s", str(s), "-m", "models-cunet"], (2, 4)),
    "cugan": ("Real-CUGAN", "realcugan", "realcugan-ncnn-vulkan",
              lambda s: ["-n", "-1", "-s", str(s), "-m", "models-se"], (2, 3, 4)),
    "anime-video": ("Real-ESRGAN, быстро", "realesrgan", "realesrgan-ncnn-vulkan",
                    lambda s: ["-n", "realesr-animevideov3", "-s", str(s)], (2, 3, 4)),
    "anime": ("Real-ESRGAN, детальнее", "realesrgan", "realesrgan-ncnn-vulkan",
              lambda s: ["-n", "realesrgan-x4plus-anime", "-s", "4"], (4,)),
}
DEFAULT_MODEL = "waifu2x"


# the upscalers' own releases (MIT / BSD), fetched on request
DOWNLOADS = {
    "realesrgan": ("Real-ESRGAN", "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
                                  "realesrgan-ncnn-vulkan-20220424-%s.zip"),
    "realcugan": ("Real-CUGAN", "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/"
                                "realcugan-ncnn-vulkan-20220728-%s.zip"),
    "waifu2x": ("waifu2x", "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20250915/"
                           "waifu2x-ncnn-vulkan-20250915-%s.zip"),
}


def tool_path(folder: str, exe: str) -> str:
    return os.path.join(TOOLS, folder, exe + (".exe" if sys.platform == "win32" else ""))


def models() -> List[Dict]:
    return [{"id": k, "name": m[0], "ok": os.path.exists(tool_path(m[1], m[2])), "folder": m[1]}
            for k, m in MODELS.items()]


def tools() -> List[Dict]:
    """The upscaler programs: installed or not."""
    have = {m["folder"]: m["ok"] for m in models()}
    return [{"id": f, "name": d[0], "ok": have.get(f, False)} for f, d in DOWNLOADS.items()]


def install(folder: str, log=print, progress=None):
    """Download one upscaler for this system into TOOLS/<folder>."""
    import urllib.request
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "ubuntu")
    name, url = DOWNLOADS[folder]
    url = url % system
    log("%s: %s" % (name, url))
    with tempfile.TemporaryDirectory() as tmp:
        zp = os.path.join(tmp, "a.zip")
        with urllib.request.urlopen(url, timeout=60) as r, open(zp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress is not None:
                    progress[:] = [done >> 20, max(1, total >> 20)]
        with zipfile.ZipFile(zp) as z:
            z.extractall(os.path.join(tmp, "x"))
        exe = next(m[2] for m in MODELS.values() if m[1] == folder)
        exe_file = os.path.basename(tool_path(folder, exe))
        found = next((d for d, _dirs, files in os.walk(os.path.join(tmp, "x")) if exe_file in files), None)
        if not found:
            raise RuntimeError("%s: no %s in the archive" % (name, exe_file))
        dst = os.path.join(TOOLS, folder)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.move(found, dst)
        if sys.platform != "win32":
            os.chmod(os.path.join(dst, exe_file), 0o755)
    log("%s: ready in %s" % (name, dst))
MIN_SIDE = 16   # smaller ones (gradients, dots) only lose from AI: plain resize

# xxh64 without the address: robust, and the same texture loaded at
# another place in memory still matches
INI = """[options]
version = 1
hash = xxh64
ignoreAddress = true

[hashes]

[hashranges]

[filtering]
"""


def psp_root() -> str:
    for r in ROOTS:
        p = os.path.expanduser(r)
        if os.path.isdir(p):
            return p
    return os.path.expanduser(ROOTS[0])


def tex_dir(disc_id: str) -> str:
    return os.path.join(psp_root(), "TEXTURES", disc_id)


def _ppsspp_ini() -> str:
    return os.path.join(psp_root(), "SYSTEM", "ppsspp.ini")


def _ini_get(key: str) -> Optional[str]:
    try:
        with open(_ppsspp_ini(), encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*%s\s*=\s*(\S+)" % key, line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def _ini_set(values: Dict[str, str]):
    """Change keys in [Graphics] of ppsspp.ini (PPSSPP rewrites the file
    on exit: it must be closed)."""
    p = _ppsspp_ini()
    with open(p, encoding="utf-8") as f:
        lines = f.read().split("\n")
    left = dict(values)
    section = None
    for k, line in enumerate(lines):
        if line.startswith("["):
            if section == "[Graphics]" and left:  # missing keys go to the end of [Graphics]
                lines[k:k] = ["%s = %s" % kv for kv in left.items()]
                left = {}
                break
            section = line.strip()
            continue
        m = re.match(r"\s*(\w+)\s*=", line)
        if section == "[Graphics]" and m and m.group(1) in left:
            lines[k] = "%s = %s" % (m.group(1), left.pop(m.group(1)))
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _all_dumps(disc_id: str) -> List[str]:
    d = os.path.join(tex_dir(disc_id), "new")
    return sorted(n for n in os.listdir(d) if n.lower().endswith(".png")) if os.path.isdir(d) else []


def _dumps(disc_id: str) -> List[str]:
    """Dumped textures worth upscaling: not movie frames."""
    skip = movie_frames(disc_id)
    return [n for n in _all_dumps(disc_id) if n not in skip]


# textures computed from the game files (see the game plugin), kept out of
# the PPSSPP folder: it would take the small originals for replacements
ARCHIVE: Dict[str, str] = {}


def set_archive_dir(disc_id: str, path: str):
    ARCHIVE[disc_id] = path


def _archive(disc_id: str) -> List[str]:
    d = ARCHIVE.get(disc_id)
    return sorted(n for n in os.listdir(d) if n.endswith(".png")) if d and os.path.isdir(d) else []


def sources(disc_id: str) -> Dict[str, str]:
    """name -> original PNG: dumped by PPSSPP while playing (exact keys)
    and computed from the game files (data hash only, any palette)."""
    d = tex_dir(disc_id)
    out = {n: os.path.join(ARCHIVE[disc_id], n) for n in _archive(disc_id)}
    out.update({n: os.path.join(d, "new", n) for n in _dumps(disc_id)})
    return out


def _noise(g: Image.Image, box) -> float:
    g = g.crop(box)
    a, b = g.crop((1, 0, g.width, g.height)), g.crop((0, 0, g.width - 1, g.height))
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]


def movie_frames(disc_id: str) -> set:
    """Frames of the PSMF player PPSSPP dumped as textures: 512x512, opaque,
    the 480x272 picture on top and leftover noise under it. Each frame has
    its own hash, upscaling them is wasted. Cached per file name."""
    d = tex_dir(disc_id)
    cache_path = os.path.join(d, "psptool_frames.json")
    try:
        with open(cache_path) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    changed = False
    for n in _all_dumps(disc_id):
        if n in cache:
            continue
        with Image.open(os.path.join(d, "new", n)) as im:
            hit = False
            if im.size == (512, 512):
                im = im.convert("RGBA")
                if im.getchannel("A").getextrema()[0] == 255:
                    g = im.convert("L")
                    top, bottom = _noise(g, (0, 0, 480, 272)), _noise(g, (0, 280, 480, 500))
                    hit = bottom > 12 and bottom > 3 * max(top, 0.5)
        cache[n] = hit
        changed = True
    if changed:
        with open(cache_path, "w") as f:
            json.dump(cache, f)
    return {n for n, v in cache.items() if v}


def status(disc_id: str) -> Dict:
    d = tex_dir(disc_id)
    dumps = _dumps(disc_id)
    arch = _archive(disc_id)
    hd = {n for n in os.listdir(d) if n.endswith(".png")} if os.path.isdir(d) else set()
    src = set(dumps) | set(arch)
    # what the last sessions brought: new dumps per day, newest first
    days: Dict[str, int] = {}
    for n in dumps:
        t = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(os.path.join(d, "new", n))))
        days[t] = days.get(t, 0) + 1
    return {"dir": d, "dumped": len(dumps), "archive": len(arch), "archive_done": len(set(arch) & hd),
            "dumped_done": len(set(dumps) & hd), "total": len(src), "done": len(src & hd),
            "days": sorted(days.items(), reverse=True)[:5], "frames": len(movie_frames(disc_id)),
            "saving": (_ini_get("SaveNewTextures") or "").lower() == "true",
            "replacing": (_ini_get("ReplaceTextures") or "").lower() == "true",
            "ini": os.path.exists(os.path.join(d, "textures.ini")),
            "upscaler": any(m["ok"] for m in models()), "tools": tools()}


def _json(path: str) -> Dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def sizes_cache(disc_id: str) -> Dict[str, List[int]]:
    return sizes(disc_id)


def sizes(disc_id: str) -> Dict[str, List[int]]:
    """name -> [w, h] of the original (cached: there are tens of thousands)."""
    path = os.path.join(tex_dir(disc_id), "psptool_sizes.json")
    cache = _json(path)
    src = sources(disc_id)
    changed = False
    for n, p in src.items():
        if n not in cache:
            with Image.open(p) as im:
                cache[n] = list(im.size)
            changed = True
    if changed:
        _save_json(path, cache)
    return cache


def made_by(disc_id: str) -> Dict[str, str]:
    """name -> "model xN" of its HD version (as far as we recorded it)."""
    return _json(os.path.join(tex_dir(disc_id), "psptool_models.json"))


def _record(disc_id: str, names: List[str], model: str, scale: int):
    path = os.path.join(tex_dir(disc_id), "psptool_models.json")
    data = _json(path)
    for n in names:
        data[n] = "%s x%d" % (model, scale)
    _save_json(path, data)


def sort_sizes(counts: Dict[str, int]) -> List:
    """[("512x512", n), ...] biggest resolution first."""
    def area(k):
        w, h = map(int, k.split("x"))
        return (-w * h, -w)
    return sorted(counts.items(), key=lambda kv: area(kv[0]))


def pick(disc_id: str, sizes: List[str] = (), models: List[str] = (), redo: bool = False) -> Dict:
    """What an upscale run would take: sources of these original sizes
    (all when empty), only the not yet upscaled ones unless `redo`, and on
    a redo only those last made by these models (all when empty).
    Returns names and the counts per size and per model for the dialog."""
    d = tex_dir(disc_id)
    src = sources(disc_id)
    hd = {n for n in os.listdir(d) if n.endswith(".png")} if os.path.isdir(d) else set()
    dims = sizes_cache(disc_id)
    by = made_by(disc_id)
    pool = [n for n in src if redo or n not in hd]
    size_counts: Dict[str, int] = {}
    model_counts: Dict[str, int] = {}
    made = lambda n: (by.get(n, "").split(" ")[0] or "?") if n in hd else "-"   # "-": not upscaled yet
    for n in pool:
        k = "%dx%d" % tuple(dims[n])
        size_counts[k] = size_counts.get(k, 0) + 1
        if redo and (not sizes or k in sizes):  # models counted within the chosen sizes
            model_counts[made(n)] = model_counts.get(made(n), 0) + 1
    names = [n for n in pool if (not sizes or "%dx%d" % tuple(dims[n]) in sizes)
             and (not (redo and models) or made(n) in models)]
    return {"names": names, "sizes": sort_sizes(size_counts), "models": sorted(model_counts.items())}


def gallery(disc_id: str, offset: int = 0, limit: int = 60, q: str = "", size: str = "",
            only: Optional[set] = None, model: str = "", marks: Optional[set] = None,
            want_all: bool = False, sort: str = "size", desc: bool = True) -> Dict:
    """Upscaled textures. Filters: name part, the original size ("32x32"),
    a set of names (marked), the model used. Order: size (area), name or
    model; desc reverses it."""
    d = tex_dir(disc_id)
    src = sources(disc_id)
    hd = {n for n in os.listdir(d) if n.endswith(".png")} if os.path.isdir(d) else set()
    dims = sizes(disc_id)
    by = made_by(disc_id)
    done = [x for x in src if x in hd]
    facet_sizes: Dict[str, int] = {}
    facet_models: Dict[str, int] = {}
    for x in done:
        k = "%dx%d" % tuple(dims[x])
        facet_sizes[k] = facet_sizes.get(k, 0) + 1
        m = by.get(x, "").split(" ")[0] or "?"
        facet_models[m] = facet_models.get(m, 0) + 1
    if q:
        done = [x for x in done if q.lower() in x.lower()]
    if size:  # one size or several, comma-separated
        want = set(size.split(","))
        done = [x for x in done if "%dx%d" % tuple(dims[x]) in want]
    if only is not None:
        done = [x for x in done if x in only]
    if model:
        want_m = set(model.split(","))
        done = [x for x in done if (by.get(x, "").split(" ")[0] or "?") in want_m]
    keys = {"size": lambda x: (dims[x][0] * dims[x][1], x), "name": lambda x: x,
            "model": lambda x: (by.get(x, "").split(" ")[0] or "~", x)}
    done.sort(key=keys.get(sort, keys["size"]), reverse=desc)
    items = []
    for n in done[offset:offset + limit]:
        w, h = dims[n]
        k = round(1.0 * Image.open(os.path.join(d, n)).width / max(1, w)) if n in hd else 0
        items.append({"name": n, "w": w, "h": h, "hw": w * k, "hh": h * k, "by": by.get(n, ""),
                      "marked": bool(marks and n in marks)})
    return {"total": len(done), "items": items, "all": done if want_all else None,
            "sizes": sort_sizes(facet_sizes), "models": sorted(facet_models.items())}


def thumb(disc_id: str, name: str, which: str, cache: str, size: int = 192) -> bytes:
    """Small PNG of the original or the HD version (cached by mtime)."""
    d = tex_dir(disc_id)
    src = original(disc_id, name) if which == "orig" else os.path.join(d, name)
    out = os.path.join(cache, "%s_%s_%d.png" % (name[:-4], which, size))
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        os.makedirs(cache, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGBA")
            im.thumbnail((size, size), Image.LANCZOS)
            im.save(out)
    with open(out, "rb") as f:
        return f.read()


def original(disc_id: str, name: str) -> str:
    p = os.path.join(tex_dir(disc_id), "new", name)
    if not os.path.exists(p) and disc_id in ARCHIVE:
        p = os.path.join(ARCHIVE[disc_id], name)
    return p


def samples(disc_id: str, n: int = 8) -> List[str]:
    """Latest upscaled textures (for a before/after look), bigger ones first."""
    d = tex_dir(disc_id)
    src = sources(disc_id)
    done = [x for x in src if os.path.exists(os.path.join(d, x))]
    done.sort(key=lambda x: -os.path.getmtime(os.path.join(d, x)))
    recent = done[:60]
    recent.sort(key=lambda x: -os.path.getsize(src[x]))
    return recent[:n]


def set_saving(disc_id: str, on: bool):
    """Turn dumping on (and replacing, to see the result) and make sure the
    pack has our textures.ini before the first dump: it sets the hash."""
    d = tex_dir(disc_id)
    os.makedirs(os.path.join(d, "new"), exist_ok=True)
    ini = os.path.join(d, "textures.ini")
    if not os.path.exists(ini):
        with open(ini, "w", encoding="utf-8") as f:
            f.write(INI)
    _ini_set({"SaveNewTextures": "True" if on else "False", "ReplaceTextures": "True"})


class Stopped(Exception):
    pass


def _run_model(model: str, scale: int, src: str, dst: str):
    _label, folder, exe, args, scales = MODELS[model]
    native = min([n for n in scales if n >= scale] or [max(scales)])
    path = tool_path(folder, exe)
    if not os.path.exists(path):
        raise RuntimeError("%s not found in %s" % (exe, os.path.dirname(path)))
    subprocess.run([path, "-i", src, "-o", dst, "-f", "png"] + args(native),
                   cwd=os.path.dirname(path), check=True, capture_output=True)


def upscale(disc_id: str, scale: int = 3, model: str = DEFAULT_MODEL, redo: bool = False,
            log=print, progress=None, stop=None, names: Optional[List[str]] = None) -> int:
    """Dumped textures without an HD version yet (or `names`) -> HD.
    `stop()` true: finish the current batch and quit. Returns how many."""
    d = tex_dir(disc_id)
    os.makedirs(d, exist_ok=True)
    src = sources(disc_id)
    if names is not None:
        todo = [n for n in names if n in src]
    else:
        todo = [n for n in src if redo or not os.path.exists(os.path.join(d, n))]
    if progress is not None:
        progress[:] = [0, len(todo)]
    log("HD: %d textures, x%d, %s" % (len(todo), scale, MODELS[model][0]))
    small, big = [], []
    for n in todo:
        with Image.open(src[n]) as im:
            (big if min(im.size) >= MIN_SIDE else small).append(n)
    for n in small:
        _resize(src[n], os.path.join(d, n), scale)
    if small:
        _record(disc_id, small, "resize", scale)
    if progress is not None:
        progress[0] += len(small)
    step = 50
    done = len(small)
    src_of = src
    for k in range(0, len(big), step):
        if stop and stop():
            log("остановлено: %d из %d" % (done, len(todo)))
            raise Stopped()
        part = big[k:k + step]
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, "in"), os.path.join(tmp, "out")
            os.makedirs(src)
            os.makedirs(dst)
            for n in part:
                shutil.copyfile(src_of[n], os.path.join(src, n))
            _run_model(model, scale, src, dst)
            for n in part:
                out = os.path.join(dst, n)
                if not os.path.exists(out):
                    log("  failed: " + n)
                    continue
                _finish(src_of[n], out, os.path.join(d, n), scale)
            _record(disc_id, [n for n in part if os.path.exists(os.path.join(dst, n))], model, scale)
        done += len(part)
        if progress is not None:
            progress[0] += len(part)
        if (k // step) % 10 == 9 or k + step >= len(big):
            log("  %d/%d" % (min(k + step, len(big)), len(big)))
    return len(todo)


def _resize(src: str, dst: str, scale: int):
    with Image.open(src) as im:
        im.resize((im.width * scale, im.height * scale), Image.LANCZOS).save(dst)


def _finish(orig: str, up: str, dst: str, scale: int):
    """Exact size (a x4 model for x2/x3 is scaled down). The model's own
    alpha is kept: smoother sprite edges than the original one scaled."""
    with Image.open(orig) as o, Image.open(up) as u:
        size = (o.width * scale, o.height * scale)
        u = u.convert("RGBA")
        if u.size != size:
            u = u.resize(size, Image.LANCZOS)
        u.save(dst)


def make_zip(disc_id: str, out: str) -> int:
    """The pack as one file: PSP/TEXTURES/<DISC_ID>/textures.zip works too.
    Stored, not deflated: PNGs are compressed already and load faster."""
    d = tex_dir(disc_id)
    src = sources(disc_id)
    names = [n for n in os.listdir(d) if n.lower().endswith(".png") and n in src] + ["textures.ini"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        for n in names:
            if os.path.exists(os.path.join(d, n)):
                z.write(os.path.join(d, n), n)
    return len(names) - 1
