"""Font files on any system. Settings name fonts by the path they were
picked from (often macOS's PTSans.ttc + face index); where that file is
missing, the same face comes from psptool/fonts (PT Sans, OFL) or from
the system's own font folder."""
import os
import sys
from typing import Tuple

BUNDLED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
MAC = "/System/Library/Fonts/Supplemental/"
WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
PTSANS = MAC + "PTSans.ttc"

# faces of macOS's PTSans.ttc -> the same face as a single file
PTSANS_FACES = {0: "PT_Sans-Web-Regular.ttf", 2: "PT_Sans-Narrow-Web-Bold.ttf", 4: "PT_Sans-Caption-Web-Bold.ttf",
                5: "PT_Sans-Caption-Web-Regular.ttf", 6: "PT_Sans-Web-BoldItalic.ttf", 7: "PT_Sans-Web-Bold.ttf"}
# other system fonts: macOS name -> Windows name
SYSTEM = {"Arial Black.ttf": "ariblk.ttf", "Georgia Bold.ttf": "georgiab.ttf"}


def resolve(path: str, index: int = 0) -> Tuple[str, int]:
    """(file, face index) that exists here, as close to the asked one as
    possible; the asked one when nothing better is found."""
    if os.path.exists(path):
        return path, index
    base = os.path.basename(path)
    if base == "PTSans.ttc" and index in PTSANS_FACES:
        own = os.path.join(BUNDLED, PTSANS_FACES[index])
        if os.path.exists(own):
            return own, 0
    if base in SYSTEM:
        for p in (MAC + base, os.path.join(WIN, SYSTEM[base])):
            if os.path.exists(p):
                return p, 0
    return path, index


def exists(path: str, index: int = 0) -> bool:
    return os.path.exists(resolve(path, index)[0])


def default_dir() -> str:
    """Where to start the font file dialog."""
    if sys.platform == "darwin":
        return MAC
    if sys.platform == "win32":
        return WIN
    return "/usr/share/fonts"
