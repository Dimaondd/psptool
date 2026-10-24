"""The ffmpeg program: the system one (PATH, Homebrew), else the build
that comes with the imageio-ffmpeg package (release builds carry it)."""
import os
import shutil
from typing import Optional

PLACES = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
_EXE = None


def find() -> Optional[str]:
    global _EXE
    if _EXE is None:
        _EXE = shutil.which("ffmpeg") or next((p for p in PLACES if os.path.exists(p)), None) or ""
        if not _EXE:
            try:
                import imageio_ffmpeg
                _EXE = imageio_ffmpeg.get_ffmpeg_exe()
            except (ImportError, RuntimeError):
                pass
    return _EXE or None


def exe() -> str:
    p = find()
    if not p:
        raise RuntimeError("ffmpeg не найден: установите его (brew install ffmpeg) или пакет imageio-ffmpeg")
    return p
