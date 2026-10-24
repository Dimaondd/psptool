"""BLEACH ~Soul Carnival 2~ (UCJS-10106), Racjin engine.

Project layout:
    files/...          ISO files except movies and cfc.dig
    cfc/index.json     table of cfc.dig
    cfc/NNNN.bin       unpacked cfc.dig entries
    charmap.tsv        glyph code -> char of the original font
    texts/NNNN.json    strings of entry NNNN: src, ref, dst
"""
import hashlib
import json
import os
import re
import shutil
import threading
from collections import Counter
from typing import Dict, Iterable, List, Optional

from ...core.image import on_background
from ...core.iso import SECTOR, IsoImage
from ...core.plugin import GamePlugin, register
from ...plugins.racjin.cfc import CfcArchive
from ...plugins.racjin.container import Entry, leaf_items
from ...plugins.racjin import utf8
from ...plugins.racjin.text import Charmap, looks_like_text, parse_table, proportional, rebuild_table
from ...plugins.sony import elf, gim
from . import font, movies, textures

CFC = "/PSP_GAME/USRDIR/cfc.dig"
SKIP = (CFC,)
DATA = os.path.join(os.path.dirname(__file__), "data")
FONT_ENTRY = 1          # cfc entry with the font
FONT_MAIN = "s2"        # GIM, 16x16 cells, codes 0x000..
FONT_EXTRA = "s3"       # GIM, 16x16 cells, codes 0x1000..
FONT_WIDTHS = "s4"      # one byte per glyph
# codes 0x1000+ (icons, extra page) are not in the width table: measured in
# game, each takes 22 px with the 16 px cell centred in it
EXTRA_ADVANCE = 22
EXTRA_OFFSET = 3

EBOOT = "/PSP_GAME/SYSDIR/EBOOT.BIN"
# The draw routine centres each glyph in its 16 px cell by the width table
# (fine for the JP digits it was made for, breaks proportional text).
# Skip that: `bnel a0, zero` -> `b`, the delay slot runs on both paths.
EBOOT_PATCHES = [
    elf.Patch("glyph-no-centre", 0x13CE4C, bytes.fromhex("16008054"), elf.mips_b(0x13CE4C, 0x13CEA8)),
    # line width for centring ([8013]) in width-table mode: JP computes
    # 16*w/10000 there (~0), so centred lines start mid-screen. Measure
    # the way glyphs are drawn instead: (cell*w + 8) >> 4, one more
    # pixel unless mode ($s5) is 2. Falls through to the old join point.
    elf.Patch("measure-proportional", 0x13E64C,
              "sha1:6a7060b880a23b7f74e343f3ba5c77302706c841",
              elf.asm(["xori a0, s5, 2",        # a0 = mode != 2
                       "sltu a0, zero, a0",
                       "lbu a2, 0(a2)",         # w from the width table
                       "mult s3, a2",
                       "mflo s0",
                       "addiu s0, s0, 8",
                       "sra s0, s0, 4",
                       "addu s0, s0, a0"] + ["nop"] * 9)),
]


# string tables drawn with a font of their own, not the main one: codes
# mean nothing in our charmap (0033: staff roll, font in s0/s1)
OWN_FONT = {33: ("s4", "s5", "s7", "s8")}


def _text_tables(data: bytes, sections: int, cm: Charmap, index: int = -1):
    for path, blob in leaf_items(data, sections):
        if path in OWN_FONT.get(index, ()):
            continue
        t = parse_table(blob)
        if t and looks_like_text(t, cm):
            yield path, t


# the save data dir name (DISC_ID): the system finds saves by it
GAME_CODE = re.compile(r"^[A-Z]{4}\d{5}$")


def _utf8_tables(data: bytes, sections: int):
    """Save dialog texts: plain UTF-8, drawn by the system font."""
    for path, blob in leaf_items(data, sections):
        t = utf8.parse(blob)
        if t:
            yield path, t


def _cfc_name(i: int) -> str:
    return "cfc/%04d.bin" % i


@register
class BleachSC2(GamePlugin):
    id = "bleach_sc2"
    name = "BLEACH ~Soul Carnival 2~"
    disc_ids = ("UCJS10106",)
    features = ("texts", "charmap", "font", "eboot", "textures", "movies")

    @classmethod
    def detect(cls, iso, sfo):
        return sfo.get("DISC_ID") in cls.disc_ids and CFC in iso.entries

    def _archive(self, iso: IsoImage) -> CfcArchive:
        e = iso.get(CFC)
        return CfcArchive(iso.f, e.lba * SECTOR, e.size)

    def unpack(self, iso: IsoImage, everything: bool = False, entries: Optional[Iterable[int]] = None,
               log=print):
        p = self.project
        if entries is None:
            for e in iso.files():
                if e.path in SKIP or e.path.lower().endswith(".pmf"):
                    continue
                rel = "files" + e.path
                iso.extract(e.path, p.path(rel))
                p.remember(rel)
            arc = self._archive(iso)
            os.makedirs(p.path("cfc"), exist_ok=True)
            with open(p.path("cfc", "index.json"), "w") as f:
                json.dump([{"index": x.index, "size": x.size, "sections": x.sections,
                            "compressed": x.compressed} for x in arc.entries], f, indent=0)
            entries = range(len(arc.entries)) if everything else []
        arc = self._archive(iso)
        entries = list(entries)
        for n, i in enumerate(entries, 1):
            rel = _cfc_name(i)
            with open(p.path(rel), "wb") as f:
                f.write(arc.read(arc.entries[i]))
            p.remember(rel)
            if n % 50 == 0 or n == len(entries):
                log("cfc %d/%d" % (n, len(entries)))
                p.save_state()
        p.save_state()

    def pack(self, out_iso: str, compress: bool = False, log=print, probe: Optional[str] = None):
        p = self.project
        if self.text_entries() or self._font_leaves() or self.eboot_patched() or probe is not None:
            with IsoImage(p.iso_path) as iso:
                errors = self.build_entries(iso, log=log, probe=probe)
                errors += movies.build(self, iso, log=log)  # cached: only changed movies are encoded
            for err in errors[:20]:
                log("  " + err)
            if errors:
                raise ValueError("%d errors: %s" % (len(errors), "; ".join(errors[:3]) + (" …" if len(errors) > 3 else "")))
        changed_files = list(p.changed("files/"))
        # files dropped in by hand (movies are not unpacked by default)
        for dirpath, _dirs, names in os.walk(p.path("files")):
            for name in names:
                rel = os.path.relpath(os.path.join(dirpath, name), p.root).replace(os.sep, "/")
                if rel not in p.state:
                    changed_files.append(rel)
        changed_cfc = [r for r in p.changed("cfc/") if r.endswith(".bin")]
        log("changed: %d iso files, %d cfc entries" % (len(changed_files), len(changed_cfc)))

        log("copy %s -> %s" % (p.iso_path, out_iso))
        shutil.copyfile(p.iso_path, out_iso)
        with IsoImage(out_iso, writable=True) as iso:
            cfc_entry = iso.get(CFC)
            for rel in changed_files:
                path = rel[len("files"):]
                e = iso.get(path)
                if os.path.getsize(p.path(rel)) > -(-e.size // SECTOR) * SECTOR:
                    # moving it would land after cfc.dig, which must stay last
                    raise ValueError("%s grew past its sectors" % path)
                log("replace " + path)
                iso.replace_file(path, p.path(rel))

            arc = self._archive(iso)
            for rel in changed_cfc:
                i = int(os.path.basename(rel)[:4])
                with open(p.path(rel), "rb") as f:
                    data = f.read()
                log("cfc %04d: %d bytes" % (i, len(data)))
                arc.append(arc.entries[i], data, compress=compress)
            cfc_entry.size = arc.length
            iso._write_record(cfc_entry)
            iso._fix_volume_size()
        log("done: " + out_iso)

    # --- text ---------------------------------------------------------

    def charmap(self) -> Charmap:
        p = self.project.path("charmap.tsv")
        if not os.path.exists(p):
            shutil.copyfile(os.path.join(DATA, "charmap.tsv"), p)
        return Charmap.load(p)

    def target_charmap(self) -> Charmap:
        """Font layout the translation is encoded with (font/charmap.tsv
        once a new font is built, else the original one)."""
        p = self.project.path("font", "charmap.tsv")
        return Charmap.load(p) if os.path.exists(p) else self.charmap()

    def _texts_path(self, i: int) -> str:
        return self.project.path("texts", "%04d.json" % i)

    def load_texts(self, i: int) -> List[Dict]:
        with open(self._texts_path(i), encoding="utf-8") as f:
            return json.load(f)

    def save_texts(self, i: int, rows: List[Dict]):
        with open(self._texts_path(i), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)

    def text_entries(self) -> List[int]:
        d = self.project.path("texts")
        if not os.path.isdir(d):
            return []
        return sorted(int(n[:4]) for n in os.listdir(d) if n.endswith(".json"))

    def _cfc_texts(self) -> List[int]:
        """Text files of cfc.dig entries (not movie subtitles)."""
        return [i for i in self.text_entries() if not movies.is_movie(i)]

    def entry_name(self, i: int) -> str:
        return movies.name(i) if movies.is_movie(i) else "%04d" % i

    def import_movie_lines(self, log=print) -> int:
        ref = self.project.meta.get("ref_iso")
        if not ref or not os.path.isfile(ref):
            raise ValueError("сначала укажи образ-подсказку")
        n = movies.import_lines(self, ref, log=log)
        log("movies: %d lines" % n)
        return n

    # movies cleaned by Real-CUGAN (see movies.py)
    def movie_enhance_settings(self) -> Dict:
        return movies.enhance_settings(self)

    def set_movie_enhance(self, changes: Dict):
        st = movies.enhance_settings(self)
        st.update({k: v for k, v in changes.items() if k in ("on", "mode")})
        if st["mode"] not in movies.MODES:
            raise ValueError("unknown mode " + str(st["mode"]))
        self.project.meta["movie_enhance"] = st
        self.project.save_meta()

    def movie_status(self) -> Dict:
        with IsoImage(self.project.iso_path) as iso:
            lst = movies.movie_list(self, iso)
        return {"settings": movies.enhance_settings(self), "movies": lst,
                "modes": [{"id": k, "name": v[0]} for k, v in movies.MODES.items()],
                "ready": sum(1 for m in lst if m["ready"])}

    def enhance_movies(self, mode: str, log=print, progress=None, stop=None) -> int:
        with IsoImage(self.project.iso_path) as iso:
            return movies.enhance(self, iso, mode, log=log, progress=progress, stop=stop)

    def movie_frame(self, n: int, frame: int, mode: str, which: str) -> bytes:
        return movies.preview_frame(self, n, frame, mode, which)

    def movie_preview(self, entry: int, rid: str, text: str) -> bytes:
        return movies.preview_png(self, entry, rid, text)

    def extract_texts(self, iso: IsoImage, log=print) -> int:
        """Write texts/NNNN.json. Keeps dst/ref already there (by id)."""
        cm = self.charmap()
        arc = self._archive(iso)
        os.makedirs(self.project.path("texts"), exist_ok=True)
        total = 0
        seen = set()
        for e in arc.entries:
            if not e.size:
                continue
            rows = []
            for path, strings in _text_tables(arc.read(e), e.sections, cm, e.index):
                for k, codes in enumerate(strings):
                    rows.append({"id": "%s:%d" % (path, k), "src": cm.decode(codes), "ref": "", "dst": ""})
            for path, strings in _utf8_tables(arc.read(e), e.sections):
                for k, text in enumerate(strings):
                    if text.strip() and not GAME_CODE.match(text):
                        rows.append({"id": "%s:%d" % (path, k), "src": text, "ref": "", "dst": "", "utf8": True})
            if not rows:
                continue
            seen.add(e.index)
            if os.path.exists(self._texts_path(e.index)):
                old = {r["id"]: r for r in self.load_texts(e.index)}
                self._set_aside(e.index, [r for k, r in old.items()
                                          if r.get("dst") and k not in {x["id"] for x in rows}])
                for r in rows:
                    o = old.get(r["id"])
                    if o:  # everything but the source: ref, dst, marks
                        r.update({k: v for k, v in o.items() if k not in ("id", "src")})
            self.save_texts(e.index, rows)
            total += len(rows)
        # entries no longer seen as text (detection got better): set aside,
        # not deleted, in case they held translations
        gone = [i for i in self._cfc_texts() if i not in seen]
        if gone:
            os.makedirs(self.project.path("texts", "removed"), exist_ok=True)
        for i in gone:
            os.replace(self._texts_path(i), self.project.path("texts", "removed", "%04d.json" % i))
        if gone:
            log("texts: %d entries are not text, moved to texts/removed: %s"
                % (len(gone), ", ".join("%04d" % i for i in gone)))
        log("texts: %d strings in %d entries" % (total, len(self.text_entries())))
        return total

    def _set_aside(self, i: int, rows: List[Dict]):
        """Translated lines that are no longer text: keep them in
        texts/removed/NNNN-lines.json instead of losing them."""
        if not rows:
            return
        p = os.path.join(self.project.path("texts", "removed"), "%04d-lines.json" % i)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            with open(p, encoding="utf-8") as f:
                kept = {r["id"]: r for r in json.load(f)}
        except (OSError, ValueError):
            kept = {}
        kept.update({r["id"]: r for r in rows})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(list(kept.values()), f, ensure_ascii=False, indent=1)

    def import_ref(self, other_iso: str, log=print) -> int:
        """Fill `ref` from another version of the game (same layout),
        e.g. the English patch."""
        cm = self.charmap()
        n = 0
        other_iso = os.path.abspath(os.path.expanduser(other_iso.strip()))
        if not os.path.isfile(other_iso):
            raise ValueError("нет такого образа: " + other_iso)
        with IsoImage(other_iso) as iso:
            arc = self._archive(iso)
            for i in self._cfc_texts():
                e = arc.entries[i]
                data = arc.read(e)
                tables = dict(_text_tables(data, e.sections, cm, e.index))
                plain = dict(_utf8_tables(data, e.sections))
                rows = self.load_texts(i)
                for r in rows:
                    path, k = r["id"].rsplit(":", 1)
                    if r.get("utf8"):
                        t = plain.get(path)
                        if t and int(k) < len(t):
                            r["ref"] = t[int(k)]
                            n += 1
                        continue
                    t = tables.get(path)
                    if t and int(k) < len(t):
                        # [802a] is the EN patch's font switch, noise for a reader
                        r["ref"] = cm.decode(t[int(k)]).replace("[802a]", "")
                        n += 1
                self.save_texts(i, rows)
        self.project.meta["ref_iso"] = other_iso
        self.project.save_meta()
        log("ref: %d strings" % n)
        return n

    # where "show in game" puts a line: the jump hint on the first screen
    DEFAULT_PROBE_SLOTS = ["0005:s11:0", "0005:s11:4", "0005:s41:0", "0005:s41:4"]

    def probe_slots(self) -> List[str]:
        return self.project.meta.get("probe_slots") or self.DEFAULT_PROBE_SLOTS

    def build_entries(self, iso: IsoImage, log=print, probe: Optional[str] = None) -> List[str]:
        """Write every entry we change (translation, font) to
        cfc/NNNN.bin, always starting from the original. Returns errors.
        `probe`: text put into the probe slots (test builds only)."""
        cm = self.target_charmap()
        src_cm = self.charmap()
        arc = self._archive(iso)
        errors = []
        todo = {i: [r for r in self.load_texts(i) if r.get("dst")] for i in self._cfc_texts()}
        if probe is not None:
            for slot in self.probe_slots():
                e, rid = slot.split(":", 1)
                rows = [r for r in todo.get(int(e), []) if r["id"] != rid]
                rows.append({"id": rid, "dst": probe})
                todo[int(e)] = rows
        todo = {i: rows for i, rows in todo.items() if rows}
        font = self._font_leaves()
        if font:
            todo.setdefault(FONT_ENTRY, [])
        tex: Dict[int, Dict[str, bytes]] = {}
        for tid in textures.edited_ids(self.project):
            with open(self.project.path("textures", "edit", tid + ".png"), "rb") as f:
                tex.setdefault(textures.parse_id(tid)[0], {})[tid] = f.read()
        for i in tex:
            todo.setdefault(i, [])
        built = set()
        for i, rows in sorted(todo.items()):
            e = arc.entries[i]
            orig = arc.read(e)
            entry = Entry(orig, e.sections)
            if i == FONT_ENTRY and font:
                for path, blob in font.items():
                    entry.replace(path, blob)
            if i in tex:
                try:
                    textures.apply_edits(entry, i, tex[i])
                except (ValueError, KeyError) as ex:
                    errors.append("%04d texture: %s" % (i, ex))
            tables = dict(_text_tables(orig, e.sections, src_cm, i))
            edits: Dict[str, Dict[int, List[int]]] = {}
            plain: Dict[str, Dict[int, str]] = {}
            for r in rows:
                path, k = r["id"].rsplit(":", 1)
                if r.get("utf8"):
                    plain.setdefault(path, {})[int(k)] = r["dst"]
                    continue
                try:
                    # proportional: the game draws translated lines with the width table
                    edits.setdefault(path, {})[int(k)] = proportional(cm.encode(r["dst"]))
                except ValueError as ex:
                    errors.append("%04d %s: %s" % (i, r["id"], ex))
            leaves = entry.leaves()
            for path, by_k in edits.items():
                strings = list(tables[path])
                for k, codes in by_k.items():
                    strings[k] = codes
                entry.replace(path, rebuild_table(entry.read(leaves[path]), strings))
                leaves = entry.leaves()
            if plain:
                orig_plain = dict(_utf8_tables(orig, e.sections))
                for path, by_k in plain.items():
                    strings = list(orig_plain[path])
                    for k, text in by_k.items():
                        strings[k] = text
                    entry.replace(path, utf8.build(strings))
            rel = _cfc_name(i)
            os.makedirs(self.project.path("cfc"), exist_ok=True)
            with open(self.project.path(rel), "wb") as f:
                f.write(entry.bytes())
            # pristine = the original entry, so pack sees the change
            self.project.state[rel] = hashlib.sha1(orig).hexdigest()
            built.add(rel)
        # entries built last time that need no change now go back to original
        for rel in self._load_built() - built:
            if os.path.exists(self.project.path(rel)):
                os.remove(self.project.path(rel))
            self.project.state.pop(rel, None)
        self._save_built(built)
        self.project.save_state()
        self._build_eboot(log)
        log("built %d entries, %d errors" % (len(built), len(errors)))
        return errors

    # --- EBOOT --------------------------------------------------------------

    def _eboot_path(self) -> str:
        return self.project.path("eboot", "decrypted.elf")

    def eboot_patched(self) -> bool:
        return os.path.exists(self._eboot_path())

    def import_eboot(self, path: str, log=print):
        """Take a decrypted EBOOT (PPSSPP: Developer tools -> Dump decrypted
        EBOOT.BIN) so the build can ship a patched one."""
        with open(os.path.expanduser(path), "rb") as f:
            b = f.read()
        elf.apply(b, EBOOT_PATCHES)  # checks it is the right game/version
        os.makedirs(self.project.path("eboot"), exist_ok=True)
        with open(self._eboot_path(), "wb") as f:
            f.write(b)
        log("EBOOT: ok, %d patch(es) will be applied" % len(EBOOT_PATCHES))
        if os.path.exists(self.project.path("font", "font.json")):
            log("rebuilding font for the patched engine")
            self.build_font(self.font_settings(), log=log)

    def _build_eboot(self, log=print):
        rel = "files" + EBOOT
        if not self.eboot_patched():
            return
        with open(self._eboot_path(), "rb") as f:
            b = elf.apply(f.read(), EBOOT_PATCHES)
        with open(self.project.path(rel), "wb") as f:
            f.write(b)
        log("EBOOT: patched")

    def _load_built(self) -> set:
        try:
            with open(self.project.path("cfc", "built.json")) as f:
                return set(json.load(f))
        except (OSError, ValueError):
            return set()

    def _save_built(self, built: set):
        with open(self.project.path("cfc", "built.json"), "w") as f:
            json.dump(sorted(built), f)

    # --- font / charmap -----------------------------------------------

    _font_lock = threading.Lock()

    def _orig_font_leaves(self) -> Dict[str, bytes]:
        with IsoImage(self.project.iso_path) as iso:
            arc = self._archive(iso)
            e = arc.entries[FONT_ENTRY]
            return dict(leaf_items(arc.read(e), e.sections))

    def _font_leaves(self) -> Dict[str, bytes]:
        """New font blobs by leaf path, if a font was built."""
        out = {}
        for path, name in ((FONT_MAIN, "s2.gim"), (FONT_WIDTHS, "s4.bin")):
            f = self.project.path("font", name)
            if os.path.exists(f):
                with open(f, "rb") as fh:
                    out[path] = fh.read()
        return out

    def _font_pages(self, new: bool = False):
        """Decoded font pages, cached: [(first_code, Image), ...]."""
        with self._font_lock:
            cache = "_pages_new" if new else "_pages"
            if getattr(self, cache, None) is None:
                setattr(self, cache, self._load_font_pages(new))
            return getattr(self, cache)

    def _load_font_pages(self, new: bool):
        leaves = self._orig_font_leaves()
        if new:
            leaves.update(self._font_leaves())
        pages = []
        for name, base in ((FONT_MAIN, 0), (FONT_EXTRA, 0x1000)):
            blob = leaves[name]
            imgs, _ = gim.parse(blob)
            for k in range(len(imgs)):
                pages.append((base, gim.decode(blob, k)))
                base += (imgs[k].w // 16) * (imgs[k].h // 16)
        return pages

    def glyph_png(self, code: int, scale: int = 3, new: bool = False) -> bytes:
        for base, img in self._font_pages(new):
            per = (img.w // 16) * (img.h // 16)
            if base <= code < base + per:
                k = code - base
                cols = img.w // 16
                tile = img.crop(k % cols * 16, k // cols * 16, 16, 16)
                # as the game shows it: real colours on a dark window
                return on_background(tile).scaled(scale).png()
        raise KeyError(code)

    def render_png(self, text: str, scale: int = 2, new: bool = True) -> bytes:
        """Text drawn the way the game does: glyph cells advanced by the
        width table, 0x8001 = new line, commands skipped."""
        from ...core.image import Image
        cm = self.target_charmap() if new else self.charmap()
        widths = self._widths(new)
        pages = self._font_pages(new)
        lines, cur = [], []
        for c in cm.encode(text):
            if c == 0x8001:
                lines.append(cur)
                cur = []
            elif c < 0x8000:
                cur.append(c)
        lines.append(cur)
        adv = lambda c: widths[c] if c < len(widths) else EXTRA_ADVANCE  # noqa: E731
        w = max([sum(adv(c) for c in ln) for ln in lines] + [1]) + 16
        img = Image(w, 18 * len(lines) + 2)
        for y, ln in enumerate(lines):
            x = 2
            for c in ln:
                # where the game puts the cell: icons centred in 22 px,
                # glyphs shifted by (16 - width) / 2 (see font.py)
                dx = EXTRA_OFFSET if c >= 0x1000 else (0 if self.eboot_patched() else font.cell_shift(adv(c)))
                for base, page in pages:
                    per = (page.w // 16) * (page.h // 16)
                    if base <= c < base + per:
                        k = c - base
                        tile = page.crop(k % (page.w // 16) * 16, k // (page.w // 16) * 16, 16, 16)
                        for ty in range(16):
                            for tx in range(16):
                                px = tile.get(tx, ty)
                                if px[3] and x + dx + tx < w:
                                    o = img.get(x + dx + tx, 1 + y * 18 + ty)
                                    if px[3] > o[3]:
                                        img.put(x + dx + tx, 1 + y * 18 + ty, px)
                        break
                x += adv(c)
        return on_background(img).scaled(scale).png()

    def _blank_codes(self) -> set:
        """Font cells with no ink at all."""
        if getattr(self, "_blank", None) is None:
            blank = set()
            for base, page in self._font_pages():
                cols = page.w // 16
                for k in range(cols * (page.h // 16)):
                    x0, y0 = k % cols * 16, k // cols * 16
                    if not any(page.px[((y0 + y) * page.w + x0 + x) * 4 + 3] for y in range(16) for x in range(16)):
                        blank.add(base + k)
            self._blank = blank
        return self._blank

    def charmap_rows(self) -> List[Dict]:
        self.charmap()
        blank = self._blank_codes()
        rows = []
        with open(self.project.path("charmap.tsv"), encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if p and p[0]:
                    code = int(p[0], 16)
                    rows.append({"code": code, "ch": p[1] if len(p) > 1 else "",
                                 "unsure": len(p) > 2 and p[2] == "?", "blank": code in blank})
        # one char on several codes: all but the first show up as [#code]
        # in the text, so they need a look too
        by_ch: Dict[str, List[int]] = {}
        for r in rows:
            if r["ch"].strip():
                by_ch.setdefault(r["ch"], []).append(r["code"])
        for r in rows:
            same = [c for c in by_ch.get(r["ch"], []) if c != r["code"]]
            if same:
                r["dup"] = same
        return rows

    def set_chars(self, changes: Dict[int, str]):
        """Fix OCR mistakes; a fixed glyph is no longer marked unsure."""
        rows = self.charmap_rows()
        for r in rows:
            if r["code"] in changes:
                r["ch"], r["unsure"] = changes[r["code"]], False
        with open(self.project.path("charmap.tsv"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write("%04x\t%s\t%s\n" % (r["code"], r["ch"], "?" if r["unsure"] else ""))
        self.redecode()

    def redecode(self, log=print):
        """Charmap changed: decode the lines (src, ref) again from the
        discs, translations and marks stay."""
        with IsoImage(self.project.iso_path) as iso:
            self.extract_texts(iso, log=log)
        ref = self.project.meta.get("ref_iso")
        if ref and os.path.isfile(ref):
            self.import_ref(ref, log=log)

    def font_settings(self) -> Dict:
        try:
            with open(self.project.path("font", "font.json"), encoding="utf-8") as f:
                return json.load(f)["settings"]
        except (OSError, ValueError, KeyError):
            return font.default_settings()

    def glyph_usage(self) -> Counter:
        """How often each glyph code appears in the game text."""
        cm = self.charmap()
        use = Counter()
        with IsoImage(self.project.iso_path) as iso:
            arc = self._archive(iso)
            for i in self._cfc_texts():
                e = arc.entries[i]
                for _path, strings in _text_tables(arc.read(e), e.sections, cm, e.index):
                    for s in strings:
                        use.update(c for c in s if c < 0x8000)
        return use

    def build_font(self, settings: Dict, log=print) -> Dict[int, str]:
        leaves = self._orig_font_leaves()
        cm = self.charmap().to_char
        log("counting glyph use...")
        usage = self.glyph_usage()
        log("rendering %d chars with %s" % (len(settings["chars"]), settings.get("ttf")))
        s2, s4, assign = font.build(leaves[FONT_MAIN], leaves[FONT_WIDTHS], settings, usage, cm,
                                    centred=not self.eboot_patched())
        font.save(self.project, s2, s4, assign, settings, cm)
        self._pages_new = self._w_new = None
        new = {c: ch for c, ch in assign.items() if c >= font.KEEP}
        lost = sum(usage.get(c, 0) for c in new)
        log("font: %d new chars, replaced glyphs were used %d times in JP text" % (len(new), lost))
        return assign

    def _widths(self, new: bool) -> bytes:
        cache = "_w_new" if new else "_w_old"
        if getattr(self, cache, None) is None:
            w = self._orig_font_leaves()[FONT_WIDTHS]
            if new:
                w = self._font_leaves().get(FONT_WIDTHS, w)
            setattr(self, cache, w)
        return getattr(self, cache)

    def line_widths(self, text: str, new: bool = True) -> List[int]:
        """Pixel width of each line as the game draws it (src text: new=False)."""
        cm = self.target_charmap() if new else self.charmap()
        widths = self._widths(new)
        out, cur = [], 0
        for c in cm.encode(text):
            if c == 0x8001:
                out.append(cur)
                cur = 0
            elif c < len(widths):
                cur += widths[c]
            elif 0x1000 <= c < 0x8000:
                cur += EXTRA_ADVANCE
        out.append(cur)
        return out

    def font_cells(self) -> Dict[int, str]:
        try:
            with open(self.project.path("font", "font.json"), encoding="utf-8") as f:
                return {int(k, 16): v for k, v in json.load(f)["cells"].items()}
        except (OSError, ValueError, KeyError):
            return {}

    # --- textures -------------------------------------------------------

    def texture_index(self) -> List[Dict]:
        p = self.project.path("textures", "index.json")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            rows = json.load(f)
        edited = set(textures.edited_ids(self.project))
        for r in rows:
            r["edited"] = r["id"] in edited
        return rows

    def hd_archive(self, out_dir: str, log=print, progress=None, stop=None) -> int:
        """Every GIM texture of the game as PPSSPP will see it, without
        playing: <hash>.png named like its dumps (address and palette
        zeroed, any palette matches). The hash is xxh64 (low 32 bits) of
        the texture memory: the power-of-two size the game draws with,
        read from the file as loaded, so bytes after a picture that is
        not a power of two are the file's next bytes. Translated entries
        are read from the last build (what the game will show)."""
        from ...core.xxh import xxh64
        from PIL import Image as PImage
        os.makedirs(out_dir, exist_ok=True)
        built = self._load_built()
        p2 = lambda x: 1 << (x - 1).bit_length()
        made = set()
        stopped = False
        with IsoImage(self.project.iso_path) as iso:
            arc = self._archive(iso)
            if progress is not None:
                progress[:] = [0, len(arc.entries)]
            for e in arc.entries:
                if progress is not None:
                    progress[0] += 1
                if stop and stop():
                    log("остановлено")
                    stopped = True
                    break
                if not e.size:
                    continue
                rel = _cfc_name(e.index)
                if rel in built and os.path.exists(self.project.path(rel)):
                    with open(self.project.path(rel), "rb") as f:
                        data = f.read()
                else:
                    data = arc.read(e)
                if gim.MAGIC not in data:
                    continue
                try:
                    leaves = list(leaf_items(data, e.sections))
                except Exception:
                    continue
                for _path, blob in leaves:
                    for off, n in gim.find(blob):
                        gb = blob[off:off + n]
                        try:
                            imgs, _pals = gim.parse(gb)
                        except Exception:
                            continue
                        for k, im in enumerate(imgs):
                            bpp = gim.BPP[im.fmt]
                            bufw, tw, th = im.stride * 8 // bpp, p2(im.w), p2(im.h)
                            if bufw > tw or tw > 512 or th > 512:
                                continue  # strided rows: hashed row by row, not done here
                            size = bpp * (bufw * th + (tw - bufw)) // 8
                            start = off + im.pix_pos
                            if start + size > len(blob):
                                continue  # needs bytes from after the file: unknown
                            name = "0000000000000000%08x.png" % (xxh64(blob[start:start + size], 0xBACD7814) & 0xFFFFFFFF)
                            if name in made:
                                continue
                            try:
                                pic = gim.to_pil(gb, k)
                            except Exception:
                                continue
                            canvas = PImage.new("RGBA", (tw, th))
                            canvas.paste(pic, (0, 0))
                            canvas.save(os.path.join(out_dir, name))
                            made.add(name)
                if e.index % 500 == 0:
                    log("  %d/%d entries, %d textures" % (e.index, len(arc.entries), len(made)))
        # textures gone (a translation changed them) go away too
        if not stopped:
            for n in os.listdir(out_dir):
                if n.endswith(".png") and n not in made:
                    os.remove(os.path.join(out_dir, n))
        log("из архива: %d текстур" % len(made))
        return len(made)

    def build_texture_index(self, log=print) -> int:
        ref = self.project.meta.get("ref_iso")
        with IsoImage(self.project.iso_path) as iso:
            arc = self._archive(iso)
            if ref and os.path.exists(ref):
                with IsoImage(ref) as riso:
                    rows = textures.scan(arc, self._archive(riso), log=log)
            else:
                rows = textures.scan(arc, None, log=log)
        os.makedirs(self.project.path("textures"), exist_ok=True)
        with open(self.project.path("textures", "index.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f)
        log("textures: %d images, %d changed in the reference" % (len(rows), sum(r["ref"] for r in rows)))
        return len(rows)

    def texture_png(self, tid: str, which: str = "jp", scale: int = 1) -> bytes:
        """which: jp (original), ref (other version), edit (user's file)."""
        if which == "edit":
            with open(self.project.path("textures", "edit", tid + ".png"), "rb") as f:
                return f.read()
        cache = self.project.path("textures", "cache", "%s_%s_%d.png" % (tid, which, scale))
        if os.path.exists(cache):
            with open(cache, "rb") as f:
                return f.read()
        path = self.project.iso_path if which == "jp" else self.project.meta.get("ref_iso")
        if not path:
            raise KeyError("no reference ISO")
        with IsoImage(path) as iso:
            img = textures.decode(self._archive(iso), tid)
        data = (img.scaled(scale) if scale > 1 else img).png()
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "wb") as f:
            f.write(data)
        return data

    def set_texture(self, tid: str, png: Optional[bytes]):
        """Save a replacement (checked: decodes, right size, encodes)."""
        p = self.project.path("textures", "edit", tid + ".png")
        if png is None:
            if os.path.exists(p):
                os.remove(p)
            return
        from ...core.image import read_png_rgba
        img = read_png_rgba(png)
        with IsoImage(self.project.iso_path) as iso:
            textures.check(self._archive(iso), tid, img)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(png)

    def info(self) -> List[str]:
        with IsoImage(self.project.iso_path) as iso:
            arc = self._archive(iso)
            n = len(arc.entries)
            comp = sum(1 for e in arc.entries if e.compressed)
            size = sum(e.size for e in arc.entries)
        return ["cfc.dig: %d entries, %d compressed, %.0f MB unpacked" % (n, comp, size / 1e6)]
