"""Racjin CFC.DIG archive.

Layout: 16 zero bytes, then 16-byte records until a record with offset 0:
    u32 offset        in 2048-byte sectors from archive start
    u32 stored_size   bytes on disc
    u16 sections      count of sub-sections inside the file
    u16 flags         bit 0 = Racjin LZ compressed
    u32 size          unpacked size
Records are not sorted by offset. File data starts right after the table.
"""
import struct
from dataclasses import dataclass
from typing import BinaryIO, List

from . import lz

SECTOR = 2048
HEADER = 16
REC = struct.Struct("<IIHHI")


@dataclass
class CfcEntry:
    index: int
    offset: int       # sectors
    stored_size: int
    sections: int
    flags: int
    size: int

    @property
    def compressed(self) -> bool:
        return bool(self.flags & 1)

    @property
    def end_sector(self) -> int:
        return self.offset + (self.stored_size + SECTOR - 1) // SECTOR

    def pack(self) -> bytes:
        return REC.pack(self.offset, self.stored_size, self.sections, self.flags, self.size)


class CfcArchive:
    """Works on a file object positioned anywhere: `base` is the byte offset
    of the archive inside it (so it can be read straight from the ISO)."""

    def __init__(self, f: BinaryIO, base: int = 0, length: int = 0):
        self.f = f
        self.base = base
        self.length = length
        self.entries: List[CfcEntry] = []
        self._read_table()

    def _read_table(self):
        self.f.seek(self.base + HEADER)
        i = 0
        while True:
            rec = REC.unpack(self.f.read(REC.size))
            if rec[0] == 0:
                break
            self.entries.append(CfcEntry(i, *rec))
            i += 1
        self.table_end = HEADER + REC.size * (len(self.entries) + 1)

    def read_raw(self, e: CfcEntry) -> bytes:
        self.f.seek(self.base + e.offset * SECTOR)
        return self.f.read(e.stored_size)

    def read(self, e: CfcEntry) -> bytes:
        raw = self.read_raw(e)
        if e.compressed:
            return lz.decompress(raw, e.size)
        return raw[:e.size]

    def data_end_sector(self) -> int:
        return max(e.end_sector for e in self.entries)

    def append(self, e: CfcEntry, data: bytes, compress: bool = False) -> int:
        """Write new content for an entry after the current end of the
        archive and update its record. Returns the new archive length."""
        stored = lz.compress(data) if compress else data
        sector = self.data_end_sector()
        self.f.seek(self.base + sector * SECTOR)
        self.f.write(stored)
        pad = -len(stored) % SECTOR
        if pad:
            self.f.write(b"\x00" * pad)
        e.offset = sector
        e.stored_size = len(stored)
        e.size = len(data)
        e.flags = (e.flags | 1) if compress else (e.flags & ~1)
        self.f.seek(self.base + HEADER + e.index * REC.size)
        self.f.write(e.pack())
        self.length = max(self.length, (sector * SECTOR) + len(stored) + pad)
        return self.length
