# PyInstaller: PSPtool.app (macOS) / PSPtool\PSPtool.exe (Windows).
# Build: python -m psptool.core.native && python packaging/icon.py &&
#        pyinstaller packaging/psptool.spec --noconfirm
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.dirname(SPECPATH)
PKG = os.path.join(ROOT, "psptool")
VERSION = os.environ.get("PSPTOOL_VERSION", "0.1.0")


def tree(rel):
    """Every file under psptool/<rel>, kept at the same place."""
    out = []
    for d, _dirs, files in os.walk(os.path.join(PKG, rel)):
        files = [f for f in files if not f.endswith((".pyc", ".DS_Store"))]
        if files:
            dst = os.path.relpath(d, ROOT)
            out += [(os.path.join(d, f), dst) for f in files]
    return out


datas = tree("ui/static") + tree("_native") + collect_data_files("imageio_ffmpeg")
for opt in ("fonts", os.path.join("games", "bleach_sc2", "data")):
    if os.path.isdir(os.path.join(PKG, opt)):
        datas += tree(opt)

a = Analysis([os.path.join(SPECPATH, "launch.py")], pathex=[ROOT], datas=datas,
             hiddenimports=collect_submodules("psptool") + ["anthropic"],
             excludes=["tkinter"] if sys.platform == "darwin" else [])
pyz = PYZ(a.pure)
icon = os.path.join(SPECPATH, "icon.icns" if sys.platform == "darwin" else "icon.ico")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PSPtool", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="PSPtool")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="PSPtool.app", icon=icon, bundle_identifier="io.github.dimaondd.psptool",
                 version=VERSION, info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0",
                                              "CFBundleShortVersionString": VERSION})
