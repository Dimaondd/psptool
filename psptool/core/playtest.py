"""Run the built image in an emulator (PPSSPP) for a quick look.

Machine settings (emulator path) live in ~/.config/psptool/settings.json.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

CONFIG = os.path.join(os.path.expanduser("~"), ".config", "psptool", "settings.json")

CANDIDATES = [
    "/Applications/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL",
    "/Applications/PPSSPP.app/Contents/MacOS/PPSSPP",
    os.path.expanduser("~/Applications/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL"),
    "C:\\Program Files\\PPSSPP\\PPSSPPWindows64.exe",
]
STATE_DIRS = [
    "~/.config/ppsspp/PSP/PPSSPP_STATE",
    "~/Documents/PPSSPP/PSP/PPSSPP_STATE",
    "~/Library/Application Support/PPSSPP/PSP/PPSSPP_STATE",
    r"C:\Program Files\PPSSPP\memstick\PSP\PPSSPP_STATE",
]


def load() -> Dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(s: Dict):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def find_emulator() -> str:
    path = load().get("emulator", "")
    if path and os.path.exists(path):
        return path
    for p in CANDIDATES + [shutil.which("PPSSPPSDL") or "", shutil.which("ppsspp") or ""]:
        if p and os.path.exists(p):
            return p
    return ""


def states(disc_id: str) -> List[Dict]:
    """Save states of this game, newest first."""
    out = []
    for d in STATE_DIRS:
        for p in glob.glob(os.path.join(os.path.expanduser(d), "%s*.ppst" % disc_id)):
            out.append({"path": p, "name": os.path.basename(p), "mtime": os.path.getmtime(p)})
    return sorted(out, key=lambda s: -s["mtime"])


_proc: Optional[subprocess.Popen] = None


def launch(iso: str, state: str = "", log=print):
    """Start the emulator; a previous run started from here is closed."""
    global _proc
    emu = find_emulator()
    if not emu:
        raise RuntimeError("PPSSPP not found: set its path in Project")
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(5)
        except subprocess.TimeoutExpired:
            _proc.kill()
    args = [emu, "--windowed"]
    if state and os.path.exists(state):
        args.append("--state=" + state)
    args.append(iso)
    log("run: %s%s" % (os.path.basename(emu), " + " + os.path.basename(state) if state else ""))
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform != "win32":
        kw["start_new_session"] = True
    _proc = subprocess.Popen(args, **kw)
