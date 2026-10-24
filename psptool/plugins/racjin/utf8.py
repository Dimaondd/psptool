"""Plain UTF-8 string tables (save data texts shown by the system dialog):

    u32 count
    count x (u16 offset, u16 length)   offsets from the table start
    strings, back to back, no terminator
"""
import struct
from typing import List, Optional


def parse(blob: bytes) -> Optional[List[str]]:
    """Strings, or None if the blob is not such a table."""
    if len(blob) < 8:
        return None
    n = struct.unpack_from("<I", blob)[0]
    head = 4 + 4 * n
    if not 0 < n < 4096 or head >= len(blob):
        return None
    pos = head
    out = []
    for k in range(n):
        off, size = struct.unpack_from("<HH", blob, 4 + 4 * k)
        if off != pos or pos + size > len(blob):
            return None
        try:
            s = blob[off:off + size].decode("utf-8")
        except UnicodeDecodeError:
            return None
        if any(c < " " and c not in "\n\t" for c in s):
            return None
        out.append(s)
        pos += size
    # the last string ends the table (some tables pad to 4)
    if len(blob) - pos > 3 or any(blob[pos:]):
        return None
    if not any(out):
        return None
    return out


def build(strings: List[str]) -> bytes:
    data = [s.encode("utf-8") for s in strings]
    head = 4 + 4 * len(data)
    out = bytearray(struct.pack("<I", len(data)))
    pos = head
    for d in data:
        if pos > 0xFFFF or len(d) > 0xFFFF:
            raise ValueError("UTF-8 table too big")
        out += struct.pack("<HH", pos, len(d))
        pos += len(d)
    for d in data:
        out += d
    return bytes(out)
