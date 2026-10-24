"""Racjin string tables and text codec.

String table: u32 count, count * u32 offset (from table start), then
strings of u16 codes, each ended by 0x8000. Codes < 0x8000 are glyph
numbers in the game font; codes >= 0x8000 are commands.

Text form used for editing:
    plain chars          glyphs, via a charmap
    \\n                  0x8001 line break
    {  }                 0x8008 / 0x800f highlight on / off
    [8029]               any other command, hex
    [#1a3]               glyph with no char in the charmap
"""
import re
import struct
from typing import Dict, List, Optional

END = 0x8000
NAMED = {0x8001: "\n", 0x8008: "{", 0x800F: "}"}
NAMED_REV = {v: k for k, v in NAMED.items()}


def parse_table(blob: bytes) -> Optional[List[List[int]]]:
    """Strings without the 0x8000 end mark, or None if not a table."""
    if len(blob) < 8:
        return None
    count = struct.unpack_from("<I", blob)[0]
    if not 1 <= count <= 20000 or 4 + 4 * count > len(blob):
        return None
    offs = struct.unpack_from("<%dI" % count, blob, 4)
    if offs[0] != 4 + 4 * count or offs[-1] >= len(blob):
        return None
    if any(b <= a for a, b in zip(offs, offs[1:])):
        return None
    out = []
    for k, o in enumerate(offs):
        end = offs[k + 1] if k + 1 < count else len(blob)
        codes = list(struct.unpack_from("<%dH" % ((end - o) // 2), blob, o))
        if END not in codes:
            return None
        out.append(codes[:codes.index(END)])
    return out


def _extras(blob: bytes, strings: List[List[int]]) -> List[bytes]:
    """Bytes after each string's end mark up to the next string (some
    tables keep per-line data there; the last one holds the padding)."""
    count = len(strings)
    offs = struct.unpack_from("<%dI" % count, blob, 4) + (len(blob),)
    return [blob[offs[k] + 2 * (len(s) + 1):offs[k + 1]] for k, s in enumerate(strings)]


def build_table(strings: List[List[int]], extras: Optional[List[bytes]] = None) -> bytes:
    extras = extras or [b""] * len(strings)
    head = 4 + 4 * len(strings)
    offs, body = [], bytearray()
    for s, x in zip(strings, extras):
        offs.append(head + len(body))
        body += struct.pack("<%dH" % (len(s) + 1), *s, END) + x
    return struct.pack("<%dI" % (len(strings) + 1), len(strings), *offs) + bytes(body)


def rebuild_table(blob: bytes, strings: List[List[int]]) -> bytes:
    """New table, keeping the per-string extra bytes of the original."""
    return build_table(strings, _extras(blob, parse_table(blob)))


class Charmap:
    """code <-> char for one font layout."""

    def __init__(self, table: Dict[int, str]):
        self.to_char = dict(table)
        self.to_code: Dict[str, int] = {}
        for code, ch in sorted(table.items()):
            if ch and ch not in self.to_code:
                self.to_code[ch] = code

    @classmethod
    def load(cls, path: str) -> "Charmap":
        t = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 2 and p[0]:
                    t[int(p[0], 16)] = p[1]
        return cls(t)

    def decode(self, codes: List[int]) -> str:
        out = []
        for c in codes:
            if c >= 0x8000:
                out.append(NAMED.get(c, "[%x]" % c))
            else:
                ch = self.to_char.get(c)
                # a char shared by several codes (OCR, icons) would come back
                # as the first of them: keep the others as raw codes
                if not ch or ch in "[]{}\\" or self.to_code.get(ch) != c:
                    out.append("[#%x]" % c)
                else:
                    out.append(ch)
        return "".join(out)

    _TOKEN = re.compile(r"\[#([0-9a-fA-F]+)\]|\[([0-9a-fA-F]{4})\]|(.)", re.S)

    def encode(self, text: str) -> List[int]:
        out = []
        for m in self._TOKEN.finditer(text):
            if m.group(1):
                out.append(int(m.group(1), 16))
            elif m.group(2):
                out.append(int(m.group(2), 16))
            else:
                ch = m.group(3)
                if ch in NAMED_REV:
                    out.append(NAMED_REV[ch])
                elif ch in self.to_code:
                    out.append(self.to_code[ch])
                else:
                    raise ValueError("no glyph for %r" % ch)
        return out


PROPORTIONAL = 0x802A
LINE = 0x8001


def proportional(codes: List[int]) -> List[int]:
    """Put 0x802a (draw with the width table instead of fixed cells) at
    the start of every line that has glyphs, after its leading commands.
    Same as the English patch does."""
    out, line = [], []

    def flush():
        if any(c < 0x8000 for c in line) and PROPORTIONAL not in line:
            k = 0
            while k < len(line) and line[k] >= 0x8000:
                k += 1
            line.insert(k, PROPORTIONAL)
        out.extend(line)

    for c in codes:
        if c == LINE:
            flush()
            out.append(c)
            line = []
        else:
            line.append(c)
    flush()
    return out


def looks_like_text(strings: List[List[int]], charmap: "Charmap") -> bool:
    """Number tables and other binary data parse as string tables too.
    Text: commands only in 0x8000..0x81ff, most codes are known glyphs,
    and strings are not all 1 long."""
    known = total = latin = jp = 0
    for s in strings:
        for c in s:
            if c >= 0x8200:
                return False
            if c < 0x8000:
                total += 1
                ch = charmap.to_char.get(c)
                known += ch is not None
                if ch and ch.isascii() and ch.isalpha():
                    latin += 1
                elif c >= 0x5E:
                    jp += 1
    if not total or known < total * 0.9:
        return False
    # binary that happens to decode: Latin letters mixed into kanji at
    # random (real JP text here stays under ~15% Latin)
    if jp and latin > 0.35 * (latin + jp):
        return False
    return sum(len(s) for s in strings) > 1.5 * len(strings)
