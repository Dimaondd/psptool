"""The app icon from the UI's mark (a PSP: screen between two grips), white on black,
as icon.png (1024), icon.icns (macOS, needs iconutil) and icon.ico."""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
INK, GROUND = (255, 255, 255, 255), (0, 0, 0, 255)  # black and white: no theme colour


def draw(size: int) -> Image.Image:
    s = size / 22  # the mark's own 22x22 grid, on a rounded dark tile
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.22, fill=GROUND)
    k, o = 0.72, size * 0.14  # the mark at 72%, centred
    t = lambda v: o + v * s * k
    d.rounded_rectangle((t(1), t(5), t(21), t(17)), radius=6 * s * k, outline=INK, width=max(1, round(1.6 * s * k)))
    d.rounded_rectangle((t(6.5), t(8), t(15.5), t(14)), radius=1 * s * k, fill=INK)
    return im


def main():
    big = draw(1024)
    big.save(os.path.join(HERE, "icon.png"))
    big.save(os.path.join(HERE, "icon.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    if sys.platform == "darwin" and shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iset = os.path.join(tmp, "icon.iconset")
            os.makedirs(iset)
            for n in (16, 32, 128, 256, 512):
                draw(n).save(os.path.join(iset, "icon_%dx%d.png" % (n, n)))
                draw(n * 2).save(os.path.join(iset, "icon_%dx%d@2x.png" % (n, n)))
            subprocess.run(["iconutil", "-c", "icns", iset, "-o", os.path.join(HERE, "icon.icns")], check=True)


if __name__ == "__main__":
    main()
