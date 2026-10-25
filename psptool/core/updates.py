"""Updates of the desktop app from GitHub releases.

A release counts only when its file for this system comes with a `.sig`:
an Ed25519 signature, made on the maintainer's computer with a key that
never goes to GitHub, of "psptool-release\\n<file name>\\n<sha256>\\n".
The app knows the public key (PUBLIC_KEY) and installs nothing else, so
someone who takes over the GitHub account still cannot ship an update.

The running app cannot replace itself: install() starts a small helper
(sh on macOS, PowerShell on Windows) that waits for the app to quit, puts
the new version in place and starts it.

Maintainer side: `python -m psptool.core.updates sign FILE...` writes
FILE.sig with the key in ~/.config/psptool/release-key (see packaging/release.py).
"""
import base64
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from typing import Dict, Optional

from .. import __version__
from . import ed25519

REPO = "Dimaondd/psptool"
PUBLIC_KEY = base64.b64decode("yN7NwQ85p0SjjNzPK1UrPJT0m1D6my1DBmiUJKi85RM=")
KEY_FILE = os.path.join(os.path.expanduser("~"), ".config", "psptool", "release-key")
STATE = os.path.join(os.path.expanduser("~"), ".config", "psptool", "update.json")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "psptool", "updates")
DAY = 24 * 3600


def version_tuple(v: str):
    nums = re.findall(r"\d+", (v or "").split("-")[0])
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def asset_name(version: str) -> Optional[str]:
    """This system's release file, or None where there is no app build."""
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "PSPtool-%s-macos-arm64.dmg" % version
    if sys.platform == "win32":
        return "PSPtool-%s-windows-x64.zip" % version
    return None


def message(name: str, digest: str) -> bytes:
    return ("psptool-release\n%s\n%s\n" % (name, digest)).encode()


def installable() -> str:
    """"" when this copy can update itself, else why not."""
    if not getattr(sys, "frozen", False):
        return "source"   # run from the source: update it with git
    if not asset_name(__version__):
        return "system"
    target = _target()
    if not target or not os.access(os.path.dirname(target), os.W_OK) or not os.access(target, os.W_OK):
        return "permission"
    return ""


def _target() -> Optional[str]:
    """What gets replaced: PSPtool.app on macOS, the app's folder on Windows."""
    exe = os.path.abspath(sys.executable)
    if sys.platform == "darwin":
        app = os.path.dirname(os.path.dirname(os.path.dirname(exe)))
        return app if app.endswith(".app") else None
    return os.path.dirname(exe)


# ---- checking -------------------------------------------------------------

def _load_state() -> Dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _get(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "PSPtool/" + __version__})
    return urllib.request.urlopen(req, timeout=timeout)


def check(force: bool = False) -> Dict:
    """The latest signed release (cached for a day unless forced)."""
    st = _load_state()
    if force or time.time() - st.get("checked", 0) > DAY:
        try:
            with _get("https://api.github.com/repos/%s/releases/latest" % REPO) as r:
                rel = json.load(r)
            tag = rel.get("tag_name", "")
            ver = tag.lstrip("v")
            name = asset_name(ver)
            assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
            st = {"checked": time.time(), "version": ver, "notes": rel.get("body") or "", "page": rel.get("html_url", ""),
                  "url": assets.get(name or ""), "sig": assets.get((name or "") + ".sig"), "name": name, "error": ""}
        except Exception as e:   # offline, rate limited, no release yet
            st = dict(st, checked=time.time(), error=str(e))
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
    newer = bool(st.get("version")) and version_tuple(st["version"]) > version_tuple(__version__)
    return {"current": __version__, "latest": st.get("version", ""), "available": newer and bool(st.get("url") and st.get("sig")),
            "notes": st.get("notes", ""), "page": st.get("page", "https://github.com/%s/releases" % REPO),
            "checked": st.get("checked", 0), "error": st.get("error", ""), "installable": installable(),
            "unsigned": newer and bool(st.get("url")) and not st.get("sig")}


# ---- downloading, checking, installing ----------------------------------------

def download(log=print, progress=None) -> str:
    """The new version's file, its signature checked. Raises if it does not check."""
    st = _load_state()
    name, url, sig_url = st.get("name"), st.get("url"), st.get("sig")
    if not (name and url and sig_url):
        raise RuntimeError("no update for this system")
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    digest = hashlib.sha256()
    log("downloading " + name)
    with _get(url, timeout=60) as r, open(path, "wb") as f:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress is not None:
                progress[:] = [done >> 20, max(1, total >> 20)]
    with _get(sig_url) as r:
        sig = base64.b64decode(r.read().strip())
    if not ed25519.verify(PUBLIC_KEY, message(name, digest.hexdigest()), sig):
        os.remove(path)
        raise RuntimeError("the update's signature does not match: not installed")
    log("signature checked")
    return path


def install(path: str, log=print):
    """Start the helper that replaces the app once it quits. The caller quits."""
    why = installable()
    if why:
        raise RuntimeError("this copy cannot update itself (%s)" % why)
    target, pid = _target(), os.getpid()
    logf = os.path.join(CACHE, "update.log")
    if sys.platform == "darwin":
        q = shlex.quote
        script = """#!/bin/sh
# PSPtool update helper: wait for the app to quit, swap it, start it again
while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
MNT=$(mktemp -d)
hdiutil attach -nobrowse -readonly -noautoopen -mountpoint "$MNT" {dmg} >/dev/null || exit 1
if [ -d "$MNT/PSPtool.app" ]; then
  rm -rf {new} && ditto "$MNT/PSPtool.app" {new} && rm -rf {app} && mv {new} {app}
fi
hdiutil detach "$MNT" -quiet
xattr -dr com.apple.quarantine {app} 2>/dev/null
open {app}
""".format(pid=pid, dmg=q(path), app=q(target), new=q(target + ".updating"))
        sh = os.path.join(CACHE, "update.sh")
        with open(sh, "w") as f:
            f.write(script)
        subprocess.Popen(["/bin/sh", sh], start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=open(logf, "w"), stderr=subprocess.STDOUT)
    else:
        lit = lambda s: "'" + s.replace("'", "''") + "'"
        script = """# PSPtool update helper: wait for the app to quit, swap its folder, start it again
while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 300 }}
$tmp = Join-Path $env:TEMP ("psptool-update-" + [guid]::NewGuid())
Expand-Archive -LiteralPath {zip} -DestinationPath $tmp -Force
$src = Join-Path $tmp 'PSPtool'
if (Test-Path (Join-Path $src 'PSPtool.exe')) {{ robocopy $src {dir} /MIR /NFL /NDL /NJH /NJS /NP | Out-Null }}
Remove-Item $tmp -Recurse -Force
Start-Process (Join-Path {dir} 'PSPtool.exe')
""".format(pid=pid, zip=lit(path), dir=lit(target))
        ps1 = os.path.join(CACHE, "update.ps1")
        with open(ps1, "w", encoding="utf-8-sig") as f:
            f.write(script)
        flags = 0x00000008 | 0x00000200 | 0x08000000   # detached, new group, no window
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", ps1],
                         creationflags=flags, stdin=subprocess.DEVNULL, stdout=open(logf, "w"), stderr=subprocess.STDOUT)
    log("installing: the app restarts")


# ---- the maintainer's side: signing release files ---------------------------

def sign_file(path: str, key_file: str = KEY_FILE) -> str:
    with open(key_file, "rb") as f:
        secret = base64.b64decode(f.read().strip())
    if ed25519.public_key(secret) != PUBLIC_KEY:
        raise SystemExit("this key is not the one the app trusts (PUBLIC_KEY)")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    sig = ed25519.sign(secret, message(os.path.basename(path), digest.hexdigest()))
    out = path + ".sig"
    with open(out, "w") as f:
        f.write(base64.b64encode(sig).decode() + "\n")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "sign":
        for p in sys.argv[2:]:
            print("signed", sign_file(p))
    else:
        print("usage: python -m psptool.core.updates sign FILE...")
