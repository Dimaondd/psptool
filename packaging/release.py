"""Sign and publish a release that GitHub Actions built as a draft.

    python packaging/release.py v0.3.0      # with the gh CLI (gh auth login once)
    python packaging/release.py --sign DIR  # without it: sign the files in DIR

With gh: downloads the draft's .dmg/.zip, checks they are this version,
signs each with ~/.config/psptool/release-key, uploads the .sig files and
publishes the release. Without gh: download the draft's files from its page,
sign them here, upload the .sig files there and press "Publish release".

The key never leaves this computer; keep a copy of it somewhere safe (a
password manager): without it no update can be shipped to installed apps.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from psptool import __version__  # noqa: E402
from psptool.core import updates  # noqa: E402

REPO = updates.REPO


def sign_dir(d: str):
    files = sorted(f for f in glob.glob(os.path.join(d, "PSPtool-*")) if f.endswith((".dmg", ".zip")))
    if not files:
        raise SystemExit("no PSPtool-*.dmg / .zip in " + d)
    for f in files:
        print("signed", updates.sign_file(f))
    return files


def gh(*args):
    return subprocess.run(["gh", *args, "--repo", REPO], check=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--sign":
        sign_dir(sys.argv[2])
        return
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    tag = sys.argv[1]
    if tag.lstrip("v") != __version__:
        raise SystemExit("%s is not this checkout's version (%s)" % (tag, __version__))
    if not shutil.which("gh"):
        raise SystemExit("gh is not installed (brew install gh): or sign by hand with --sign DIR")
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", tag, "--dir", d, "--pattern", "PSPtool-*")
        for f in glob.glob(os.path.join(d, "PSPtool-*")):
            if ("-%s-" % __version__) not in os.path.basename(f):
                raise SystemExit("%s is not version %s" % (f, __version__))
        files = sign_dir(d)
        gh("release", "upload", tag, "--clobber", *[f + ".sig" for f in files])
        gh("release", "edit", tag, "--draft=false", "--latest")
    print("published %s: installed apps will offer it" % tag)


if __name__ == "__main__":
    main()
