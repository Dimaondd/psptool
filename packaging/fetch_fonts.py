"""PT Sans (SIL Open Font License) into psptool/fonts for release builds:
the faces macOS has in PTSans.ttc, for systems without it."""
import os
import urllib.request

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FILES = ["ptsans/PT_Sans-Web-Regular.ttf", "ptsans/PT_Sans-Web-Bold.ttf", "ptsans/PT_Sans-Web-BoldItalic.ttf",
         "ptsansnarrow/PT_Sans-Narrow-Web-Bold.ttf", "ptsanscaption/PT_Sans-Caption-Web-Regular.ttf",
         "ptsanscaption/PT_Sans-Caption-Web-Bold.ttf", "ptsans/OFL.txt"]
DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "psptool", "fonts")

os.makedirs(DST, exist_ok=True)
for f in FILES:
    with urllib.request.urlopen(BASE + f, timeout=60) as r, open(os.path.join(DST, os.path.basename(f)), "wb") as out:
        out.write(r.read())
    print("fetched", os.path.basename(f))
