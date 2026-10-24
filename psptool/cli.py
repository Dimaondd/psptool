"""psptool command line.

    psptool init GAME.iso WORKDIR      detect game, make a project
    psptool unpack WORKDIR [--all]     pull files out
    psptool cfc WORKDIR 19 23 ...      unpack chosen cfc.dig entries
    psptool texts WORKDIR              strings -> WORKDIR/texts/*.json
    psptool ref WORKDIR OTHER.iso      fill reference text from another ISO
    psptool font WORKDIR [--ttf F]     build font with Cyrillic (needs Pillow)
    psptool pack WORKDIR OUT.iso       build a patched ISO
    psptool info WORKDIR|GAME.iso
    psptool ui [WORKDIR]               web UI on http://127.0.0.1:8765
"""
import argparse
import sys

from .core import plugin
from .core.iso import IsoImage
from .core.project import Project
from .core.sfo import parse_sfo


def _sfo(iso: IsoImage) -> dict:
    try:
        return parse_sfo(iso.read("/PSP_GAME/PARAM.SFO"))
    except KeyError:
        return {}


def _load(workdir: str):
    p = Project(workdir)
    if not p.meta:
        sys.exit("%s is not a project (run init first)" % workdir)
    return plugin.get_plugin(p.meta["plugin"])(p)


def cmd_init(a):
    with IsoImage(a.iso) as iso:
        sfo = _sfo(iso)
        cls = plugin.detect(iso, sfo)
        if cls is None:
            sys.exit("no plugin for %s (%s)" % (sfo.get("DISC_ID"), sfo.get("TITLE")))
        Project.create(a.workdir, a.iso, cls.id,
                       {"disc_id": sfo.get("DISC_ID"), "title": sfo.get("TITLE")})
    print("%s: %s -> %s" % (cls.id, sfo.get("TITLE"), a.workdir))


def cmd_unpack(a):
    g = _load(a.workdir)
    with IsoImage(g.project.iso_path) as iso:
        g.unpack(iso, everything=a.all)


def cmd_cfc(a):
    g = _load(a.workdir)
    with IsoImage(g.project.iso_path) as iso:
        g.unpack(iso, entries=a.entries)


def cmd_texts(a):
    g = _load(a.workdir)
    with IsoImage(g.project.iso_path) as iso:
        g.extract_texts(iso)


def cmd_ref(a):
    g = _load(a.workdir)
    g.import_ref(a.iso)


def cmd_font(a):
    g = _load(a.workdir)
    st = g.font_settings()
    for k in ("ttf", "index", "px", "chars"):
        if getattr(a, k) is not None:
            st[k] = getattr(a, k)
    g.build_font(st)


def cmd_pack(a):
    g = _load(a.workdir)
    g.pack(a.out, compress=a.compress)


def cmd_ui(a):
    from .ui.server import serve
    serve(a.workdir, port=a.port, open_browser=not a.no_browser)


def cmd_info(a):
    if a.target.lower().endswith(".iso"):
        with IsoImage(a.target) as iso:
            sfo = _sfo(iso)
            cls = plugin.detect(iso, sfo)
            for k in ("TITLE", "DISC_ID", "DISC_VERSION"):
                print("%-12s %s" % (k, sfo.get(k)))
            print("%-12s %s" % ("plugin", cls.id if cls else "-"))
            for e in sorted(iso.files(), key=lambda e: e.lba):
                print("  %8d %12d %s" % (e.lba, e.size, e.path))
        return
    g = _load(a.target)
    for k, v in g.project.meta.items():
        print("%-8s %s" % (k, v))
    for line in g.info():
        print(line)
    changed = list(g.project.changed())
    print("changed: %d" % len(changed))
    for rel in changed:
        print("  " + rel)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="psptool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="make a project from an ISO")
    s.add_argument("iso")
    s.add_argument("workdir")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("unpack", help="pull files out of the ISO")
    s.add_argument("workdir")
    s.add_argument("--all", action="store_true", help="also unpack every cfc.dig entry (slow)")
    s.set_defaults(fn=cmd_unpack)

    s = sub.add_parser("cfc", help="unpack chosen cfc.dig entries")
    s.add_argument("workdir")
    s.add_argument("entries", nargs="+", type=int)
    s.set_defaults(fn=cmd_cfc)

    s = sub.add_parser("texts", help="extract strings to texts/*.json")
    s.add_argument("workdir")
    s.set_defaults(fn=cmd_texts)

    s = sub.add_parser("ref", help="reference translation from another ISO")
    s.add_argument("workdir")
    s.add_argument("iso")
    s.set_defaults(fn=cmd_ref)

    s = sub.add_parser("font", help="build font with extra letters")
    s.add_argument("workdir")
    s.add_argument("--ttf", help="TTF/OTF/TTC file")
    s.add_argument("--index", type=int, help="face index in a .ttc")
    s.add_argument("--px", type=int, help="pixel size")
    s.add_argument("--chars", help="letters to add")
    s.set_defaults(fn=cmd_font)

    s = sub.add_parser("pack", help="build patched ISO")
    s.add_argument("workdir")
    s.add_argument("out")
    s.add_argument("--compress", action="store_true", help="LZ-compress changed entries")
    s.set_defaults(fn=cmd_pack)

    s = sub.add_parser("ui", help="web UI")
    s.add_argument("workdir", nargs="?")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    s.set_defaults(fn=cmd_ui)

    s = sub.add_parser("info", help="show ISO or project info")
    s.add_argument("target")
    s.set_defaults(fn=cmd_info)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
