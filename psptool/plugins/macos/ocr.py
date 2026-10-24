"""OCR through macOS Vision (a small Swift tool, compiled on first use)."""
import json
import os
import subprocess
from typing import Dict, List

SRC = os.path.join(os.path.dirname(__file__), "ocr.swift")
PREBUILT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_native", "ocr")
BIN = PREBUILT if os.path.exists(PREBUILT) else os.path.join(os.path.expanduser("~"), ".cache", "psptool", "ocr")


def available() -> bool:
    return os.path.exists(BIN) or bool(_which("swiftc"))


def _which(name):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.access(p, os.X_OK):
            return p
    return None


def _build():
    if BIN == PREBUILT or os.path.exists(BIN) and os.path.getmtime(BIN) >= os.path.getmtime(SRC):
        return
    if not _which("swiftc"):
        raise RuntimeError("OCR needs macOS with Xcode command line tools (swiftc)")
    os.makedirs(os.path.dirname(BIN), exist_ok=True)
    subprocess.run(["swiftc", "-O", "-o", BIN, SRC], check=True, capture_output=True)


def recognize(paths: List[str], lang: str = "en-US") -> Dict[str, List[Dict]]:
    """file -> lines [{text, conf, x, y, w, h}], top to bottom."""
    _build()
    out: Dict[str, List[Dict]] = {}
    for k in range(0, len(paths), 200):
        res = subprocess.run([BIN, lang] + paths[k:k + 200], check=True, capture_output=True, text=True)
        for line in res.stdout.splitlines():
            r = json.loads(line)
            out[r["file"]] = sorted(r["lines"], key=lambda l: (l["y"], l["x"]))
    return out
