"""Textures of BLEACH SC2: every GIM in cfc.dig (as a leaf or embedded in
sprite containers), PNG export/import.

    textures/index.json        list of all images (built once)
    textures/edit/<id>.png     user's replacement, applied on build
    textures/cache/<id>.png    thumbnails / exports

id = "NNNN_<leaf path with - for />_<gim offset hex>_<image index>"
PNG leaves (save dialog icon and background): offset "png".
"""
import os
import struct
from typing import Dict, Iterable, List

from ...core.image import Image, read_png_rgba
from ...plugins.racjin.container import Entry, leaf_items
from ...plugins.sony import gim

SKIP_ENTRIES = {1}  # the font has its own tab


PNG = b"\x89PNG\r\n\x1a\n"


def make_id(entry: int, path: str, off, k: int) -> str:
    off = off if isinstance(off, str) else "%x" % off
    return "%04d_%s_%s_%d" % (entry, path.replace("/", "-"), off, k)


def parse_id(tid: str):
    """-> entry, leaf path, GIM offset (None: the leaf is a PNG), index"""
    e, path, off, k = tid.split("_")
    return int(e), path.replace("-", "/"), None if off == "png" else int(off, 16), int(k)


def _png_size(blob: bytes):
    return struct.unpack_from(">II", blob, 16)


def scan(arc, ref_arc=None, log=print) -> List[Dict]:
    """All images. `ref_arc` (another version of the game): images whose
    pixels differ there are marked `ref` — most likely they carry text."""
    out = []
    for e in arc.entries:
        if not e.size or e.index in SKIP_ENTRIES:
            continue
        data = arc.read(e)
        if b"MIG.00.1PSP" not in data and PNG not in data:
            continue
        ref_leaves = None
        if ref_arc is not None:
            r = ref_arc.entries[e.index]
            if r.pack() != e.pack():
                ref_leaves = dict(leaf_items(ref_arc.read(r), r.sections))
        for path, blob in leaf_items(data, e.sections):
            if blob.startswith(PNG):
                w, h = _png_size(blob)
                changed = bool(ref_leaves) and path in ref_leaves and ref_leaves[path] != blob
                out.append({"id": make_id(e.index, path, "png", 0), "entry": e.index, "w": w, "h": h,
                            "fmt": "png", "ref": changed})
                continue
            for off, n in gim.find(blob):
                g = blob[off:off + n]
                try:
                    imgs, _pals = gim.parse(g)
                except Exception:
                    continue
                rg = None
                if ref_leaves and path in ref_leaves:
                    rb = ref_leaves[path]
                    rg = rb[off:off + n] if rb[off:off + 12] == g[:12] else None
                for k, im in enumerate(imgs):
                    changed = False
                    if rg is not None and len(rg) == len(g):
                        a = g[im.pix_pos:im.pix_pos + im.stride * im.rows]
                        b = rg[im.pix_pos:im.pix_pos + im.stride * im.rows]
                        changed = a != b
                    out.append({"id": make_id(e.index, path, off, k), "entry": e.index, "w": im.w, "h": im.h,
                                "fmt": im.fmt, "ref": changed})
        if e.index % 200 == 0:
            log("textures: entry %d/%d, %d images" % (e.index, len(arc.entries), len(out)))
    return out


def _gim_of(arc, tid: str):
    e, path, off, k = parse_id(tid)
    ent = arc.entries[e]
    blob = dict(leaf_items(arc.read(ent), ent.sections))[path]
    n = dict(gim.find(blob))[off]
    return blob[off:off + n], k


def _leaf(arc, tid: str) -> bytes:
    e, path, _off, _k = parse_id(tid)
    ent = arc.entries[e]
    return dict(leaf_items(arc.read(ent), ent.sections))[path]


def decode(arc, tid: str) -> Image:
    if parse_id(tid)[2] is None:
        return read_png_rgba(_leaf(arc, tid))
    g, k = _gim_of(arc, tid)
    return gim.decode(g, k)


def check(arc, tid: str, img: Image):
    """Raises if `img` can not replace this texture."""
    if parse_id(tid)[2] is None:
        w, h = _png_size(_leaf(arc, tid))
        if (img.w, img.h) != (w, h):
            raise ValueError("нужен размер %dx%d, а у картинки %dx%d" % (w, h, img.w, img.h))
        return
    g, k = _gim_of(arc, tid)
    gim.encode(g, img, k)


def apply_edits(entry: Entry, entry_index: int, edits: Dict[str, bytes]):
    """edits: id -> PNG bytes, all for this entry. Same size in place."""
    leaves = entry.leaves()
    by_leaf: Dict[str, List] = {}
    for tid, png in edits.items():
        _e, path, off, k = parse_id(tid)
        if off is None:  # PNG leaf: the new picture as is
            entry.replace(path, read_png_rgba(png).png())
            leaves = entry.leaves()
            continue
        by_leaf.setdefault(path, []).append((off, k, png))
    for path, items in by_leaf.items():
        blob = bytearray(entry.read(leaves[path]))
        sizes = dict(gim.find(bytes(blob)))
        for off, k, png in items:
            n = sizes[off]
            new = gim.encode(bytes(blob[off:off + n]), read_png_rgba(png), k)
            blob[off:off + n] = new
        entry.replace(path, bytes(blob))
        leaves = entry.leaves()


def edited_ids(project) -> Iterable[str]:
    d = project.path("textures", "edit")
    if not os.path.isdir(d):
        return []
    return sorted(n[:-4] for n in os.listdir(d) if n.endswith(".png"))
