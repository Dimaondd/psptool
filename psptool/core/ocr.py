"""Text recognition: macOS Vision (best for Japanese, macOS only) or
Tesseract (any system). Both give lines [{text, conf, x, y, w, h}] with
coordinates as fractions of the image, origin top-left."""
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

SETTINGS = os.path.join(os.path.expanduser("~"), ".config", "psptool", "ocr.json")
ENGINES = {"auto": "Автоматически", "vision": "macOS Vision", "tesseract": "Tesseract"}
MIN_CONF = 30  # Tesseract's word confidence, 0..100
TESS_LANG = {"en": "eng", "ja": "jpn", "ru": "rus"}
# where installers put it when it is not on PATH (apps started from Finder
# or the Start menu get a short PATH)
TESS_PLACES = ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract",
               r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]


def load_settings() -> Dict:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(st: Dict):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)


def tesseract_bin() -> Optional[str]:
    custom = load_settings().get("tesseract")
    if custom and os.path.exists(custom):
        return custom
    return shutil.which("tesseract") or next((p for p in TESS_PLACES if os.path.exists(p)), None)


def tesseract_langs() -> List[str]:
    exe = tesseract_bin()
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.strip() for l in out.splitlines()[1:] if l.strip()]


def vision_available() -> bool:
    if sys.platform != "darwin":
        return False
    from ..plugins.macos import ocr as vision
    return vision.available()


def status() -> Dict:
    st = load_settings()
    return {"engine": st.get("engine", "auto"), "engines": ENGINES, "active": engine(),
            "vision": vision_available(), "tesseract": tesseract_bin() or "",
            "tesseract_langs": [l for l in tesseract_langs() if l in TESS_LANG.values()]}


def engine() -> str:
    """The engine that will run: the chosen one if it works, else the other."""
    want = load_settings().get("engine", "auto")
    if want == "tesseract" and tesseract_bin():
        return "tesseract"
    if want in ("auto", "vision") and vision_available():
        return "vision"
    if tesseract_bin():
        return "tesseract"
    return ""


def recognize(paths: List[str], lang: str = "en-US", sparse: bool = True) -> Dict[str, List[Dict]]:
    """file -> lines, top to bottom. lang: "en-US", "ja-JP", ...;
    sparse: text scattered over a picture (textures), else one block
    (a subtitle strip)."""
    eng = engine()
    if eng == "vision":
        from ..plugins.macos import ocr as vision
        return vision.recognize(paths, lang)
    if eng == "tesseract":
        return _tesseract(paths, lang, sparse)
    raise RuntimeError("нет распознавания текста: установите Tesseract (tesseract-ocr) "
                       "или используйте macOS с Xcode Command Line Tools")


def _tesseract(paths: List[str], lang: str, sparse: bool) -> Dict[str, List[Dict]]:
    exe = tesseract_bin()
    code = TESS_LANG.get(lang.split("-")[0].lower(), "eng")
    if code not in tesseract_langs():
        raise RuntimeError("в Tesseract нет языка %s: установите его данные (tesseract-lang)" % code)
    psm = "11" if sparse else "6"

    def one(path):
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        res = subprocess.run([exe, path, "stdout", "-l", code, "--psm", psm, "tsv"],
                             capture_output=True, text=True, encoding="utf-8")
        return path, _lines(res.stdout, iw, ih, joiner="" if code == "jpn" else " ")

    with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 1))) as ex:
        return dict(ex.map(one, paths))


def _lines(tsv: str, iw: int, ih: int, joiner: str) -> List[Dict]:
    """Words of Tesseract's TSV joined into lines."""
    groups: Dict[tuple, List[Dict]] = {}
    for row in tsv.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5" or not c[11].strip():
            continue
        groups.setdefault((c[2], c[3], c[4]), []).append(
            {"x": int(c[6]), "y": int(c[7]), "w": int(c[8]), "h": int(c[9]), "conf": float(c[10]), "text": c[11].strip()})
    out = []
    for words in groups.values():
        if sum(w["conf"] for w in words) / len(words) < MIN_CONF:
            continue  # bits of the picture read as letters
        x0 = min(w["x"] for w in words)
        y0 = min(w["y"] for w in words)
        x1 = max(w["x"] + w["w"] for w in words)
        y1 = max(w["y"] + w["h"] for w in words)
        out.append({"text": joiner.join(w["text"] for w in words),
                    "conf": sum(max(0.0, w["conf"]) for w in words) / len(words) / 100,
                    "x": x0 / iw, "y": y0 / ih, "w": (x1 - x0) / iw, "h": (y1 - y0) / ih})
    return sorted(out, key=lambda l: (l["y"], l["x"]))
