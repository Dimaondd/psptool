"""New font for BLEACH SC2: put extra letters (Cyrillic) into the cells of
the least used kanji and redraw ASCII, so the engine needs no changes.

Font lives in cfc entry 1: s2 = GIM, 7 pages 256x256 + 256x32 of 16x16
cells (codes 0x000..0x71f), idx8 palette where index = (255 - alpha) / 2
and 128 = clear; s4 = one advance width byte per code.

Output in the project:
    font/font.json     settings + which code got which char
    font/s2.gim        new font texture
    font/s4.bin        new widths
    font/charmap.tsv   code -> char for encoding the translation
"""
import json
import os
from collections import Counter
from typing import Dict, List, Optional

from ...core import fontgen
from ...plugins.sony import gim

CYRILLIC = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
EXTRA = "«»—–№"
ASCII_CODES = range(0x00, 0x5E)       # space + ASCII, redrawn in the new font
KEEP = 0x5E                            # first non-ASCII code
MAIN_CODES = 0x720                     # cells in s2
DEFAULT_FONT = ("/System/Library/Fonts/Supplemental/PTSans.ttc", 5, 14)  # PT Sans Caption


def default_settings() -> Dict:
    path, index, px = DEFAULT_FONT
    return {"ttf": path if os.path.exists(path) else "", "index": index, "px": px,
            "chars": CYRILLIC + EXTRA, "redraw_ascii": True, "tracking": 1}


def pick_cells(usage: Counter, count: int, charmap: Dict[int, str]) -> List[int]:
    """Least used kanji/kana cells; later codes first on ties (rarer)."""
    cand = [c for c in range(KEEP, MAIN_CODES) if charmap.get(c, "").strip()]
    cand.sort(key=lambda c: (usage.get(c, 0), -c))
    if len(cand) < count:
        raise ValueError("font has only %d free cells" % len(cand))
    return sorted(cand[:count])


# With the JP EBOOT, after [802a] the game draws a glyph cell at
# x + (16 - width) / 2 and then advances by width (measured in game).
# So ink must sit in the cell where that shift puts it at x + INK_AT.
INK_AT = 5
MIN_ADVANCE = 2 * (8 - INK_AT)   # narrower would need ink left of the cell


def cell_shift(width: int) -> int:
    # integer halving, as game code would do it
    return (16 - width) // 2


def fit_to_engine(g: fontgen.Glyph, tracking: int = 1) -> fontgen.Glyph:
    first, last = fontgen.measure(g.alpha)
    if last < 0:
        return g
    ink = last - first + 1
    adv = max(ink + 1 + tracking, MIN_ADVANCE)
    want = INK_AT - cell_shift(adv)
    want = max(0, min(want, 16 - ink))
    dx = want - first
    alpha = [[row[x - dx] if 0 <= x - dx < 16 else 0 for x in range(16)] for row in g.alpha]
    return fontgen.Glyph(g.ch, alpha, adv)


def alpha_to_index(a: int) -> int:
    return 128 if a < 2 else max(0, min(127, round((255 - a) / 2)))


def plain(g: fontgen.Glyph, tracking: int = 1) -> fontgen.Glyph:
    """Patched engine: ink at the left of the cell, advance = ink + gap."""
    first, last = fontgen.measure(g.alpha)
    if last < 0:
        return g
    return fontgen.Glyph(g.ch, g.alpha, min(last + 1 + tracking, 16))


def build(s2: bytes, s4: bytes, settings: Dict, usage: Counter, charmap: Dict[int, str],
          glyphs: Optional[List[fontgen.Glyph]] = None, centred: bool = True):
    """-> (new s2, new s4, assignment {code: char}).
    `glyphs` overrides rendering (e.g. read back from an edited sheet)."""
    chars = settings["chars"]
    cells = pick_cells(usage, len(chars), charmap)
    assign = dict(zip(cells, chars))
    if settings.get("redraw_ascii"):
        assign.update((c, charmap[c]) for c in ASCII_CODES if charmap.get(c))
    if glyphs is None:
        if not settings.get("ttf"):
            raise ValueError("set a TTF/OTF font file")
        order = [assign[c] for c in sorted(assign)]
        glyphs = fontgen.render(settings["ttf"], "".join(order), fontgen.CellSpec(),
                                px=settings.get("px"), index=settings.get("index", 0))
        fit = fit_to_engine if centred else plain
        glyphs = [fit(g, int(settings.get("tracking", 1))) for g in glyphs]
    by_code = dict(zip(sorted(assign), glyphs))

    out = bytearray(s2)
    imgs, _ = gim.parse(s2)
    base = 0
    for im in imgs:
        cols, rows_n = im.w // 16, im.h // 16
        per = cols * rows_n
        hit = [c for c in by_code if base <= c < base + per]
        if hit:
            rows = [bytearray(r) for r in gim.indices(s2, im)]
            for c in hit:
                k = c - base
                ox, oy = k % cols * 16, k // cols * 16
                g = by_code[c]
                for y in range(16):
                    for x in range(16):
                        rows[oy + y][ox + x] = alpha_to_index(g.alpha[y][x])
            gim.write_indices(out, im, [bytes(r) for r in rows])
        base += per

    widths = bytearray(s4)
    for c, g in by_code.items():
        widths[c] = g.advance
    return bytes(out), bytes(widths), assign


def glyph_sheet(glyphs: List[fontgen.Glyph]) -> bytes:
    return fontgen.sheet(glyphs).png()


def save(project, s2: bytes, s4: bytes, assign: Dict[int, str], settings: Dict, charmap: Dict[int, str]):
    d = project.path("font")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "s2.gim"), "wb") as f:
        f.write(s2)
    with open(os.path.join(d, "s4.bin"), "wb") as f:
        f.write(s4)
    with open(os.path.join(d, "font.json"), "w", encoding="utf-8") as f:
        json.dump({"settings": settings, "cells": {"%04x" % c: ch for c, ch in sorted(assign.items())}},
                  f, ensure_ascii=False, indent=1)
    # encoding map: the old font minus the cells we took, plus the new chars
    taken = set(assign.values())
    target = {c: ch for c, ch in charmap.items() if ch not in taken}
    target.update(assign)
    with open(os.path.join(d, "charmap.tsv"), "w", encoding="utf-8") as f:
        for c in sorted(target):
            f.write("%04x\t%s\t\n" % (c, target[c]))
