"""The small C helpers (LZ decoder, xxHash): prebuilt next to the package
(release builds, `python -m psptool.core.native`) or compiled on first
use when a C compiler is around. None: use the Python version."""
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
from typing import Optional

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREBUILT = os.path.join(PKG, "_native")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "psptool")
EXT = ".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"
SOURCES = {"racjin_lz": os.path.join(PKG, "plugins", "racjin", "_lz.c"),
           "xxh": os.path.join(PKG, "core", "_xxh.c")}


def _compiler() -> Optional[str]:
    return shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def compile_to(name: str, out: str):
    cc = _compiler()
    if not cc:
        raise OSError("no C compiler")
    args = [cc, "-O2", "-shared", "-o", out, SOURCES[name]]
    if sys.platform != "win32":
        args.insert(3, "-fPIC")
    else:  # MinGW: no libgcc DLL needed next to it
        args.insert(3, "-static-libgcc")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(args, check=True, capture_output=True)


def load(name: str) -> Optional[ctypes.CDLL]:
    built = os.path.join(PREBUILT, name + EXT)
    if os.path.exists(built):
        return ctypes.CDLL(built)
    try:
        with open(SOURCES[name], "rb") as f:
            tag = hashlib.sha1(f.read()).hexdigest()[:12]
        lib = os.path.join(CACHE, "%s_%s%s" % (name, tag, EXT))
        if not os.path.exists(lib):
            compile_to(name, lib)
        return ctypes.CDLL(lib)
    except (OSError, subprocess.CalledProcessError) as e:
        print("psptool: C %s unavailable (%s), using Python" % (name, e), file=sys.stderr)
        return None


if __name__ == "__main__":  # release builds: psptool/_native/*
    for n in SOURCES:
        compile_to(n, os.path.join(PREBUILT, n + EXT))
        print("built", n + EXT)
    if sys.platform == "darwin":  # the macOS Vision OCR tool
        subprocess.run(["swiftc", "-O", "-o", os.path.join(PREBUILT, "ocr"),
                        os.path.join(PKG, "plugins", "macos", "ocr.swift")], check=True)
        print("built ocr")
