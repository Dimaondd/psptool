"""ISO9660 reader and in-place patcher for PSP UMD images.

Only what PSP images need: primary volume descriptor, plain directory
records, no Joliet/Rock Ridge.
"""
import os
import shutil
import struct
from dataclasses import dataclass, field
from typing import BinaryIO, Dict, Iterator, List, Optional

SECTOR = 2048


@dataclass
class IsoEntry:
    path: str          # "/PSP_GAME/USRDIR/cfc.dig"
    lba: int
    size: int
    is_dir: bool
    record_pos: int    # absolute byte offset of the directory record
    children: List["IsoEntry"] = field(default_factory=list)


def _both_endian32(v: int) -> bytes:
    return struct.pack("<I", v) + struct.pack(">I", v)


class IsoImage:
    def __init__(self, path: str, writable: bool = False):
        self.path = path
        self.f: BinaryIO = open(path, "r+b" if writable else "rb")
        self.entries: Dict[str, IsoEntry] = {}
        self._read_pvd()
        self.root = self._read_dir("/", self.root_lba, self.root_size, self.root_record_pos)

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _read_pvd(self):
        self.f.seek(16 * SECTOR)
        pvd = self.f.read(SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise ValueError("not an ISO9660 image")
        self.pvd_pos = 16 * SECTOR
        self.volume_id = pvd[40:72].decode("ascii", "replace").strip()
        self.volume_sectors = struct.unpack_from("<I", pvd, 80)[0]
        self.root_record_pos = self.pvd_pos + 156
        self.root_lba = struct.unpack_from("<I", pvd, 156 + 2)[0]
        self.root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]

    def _read_dir(self, path: str, lba: int, size: int, record_pos: int) -> IsoEntry:
        node = IsoEntry(path, lba, size, True, record_pos)
        self.entries[path] = node
        self.f.seek(lba * SECTOR)
        data = self.f.read(size)
        pos = 0
        while pos < len(data):
            rec_len = data[pos]
            if rec_len == 0:
                # records never cross sector boundaries; skip padding
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            name_len = data[pos + 32]
            name = data[pos + 33:pos + 33 + name_len]
            flags = data[pos + 25]
            e_lba = struct.unpack_from("<I", data, pos + 2)[0]
            e_size = struct.unpack_from("<I", data, pos + 10)[0]
            abs_pos = lba * SECTOR + pos
            pos += rec_len
            if name in (b"\x00", b"\x01"):
                continue
            n = name.decode("ascii", "replace").split(";")[0]
            child_path = path.rstrip("/") + "/" + n
            if flags & 2:
                node.children.append(self._read_dir(child_path, e_lba, e_size, abs_pos))
            else:
                e = IsoEntry(child_path, e_lba, e_size, False, abs_pos)
                self.entries[child_path] = e
                node.children.append(e)
        return node

    def files(self) -> Iterator[IsoEntry]:
        for e in self.entries.values():
            if not e.is_dir:
                yield e

    def get(self, path: str) -> IsoEntry:
        e = self.entries.get(path)
        if e is None:
            raise KeyError(path)
        return e

    def read(self, path: str, offset: int = 0, size: Optional[int] = None) -> bytes:
        e = self.get(path)
        if size is None:
            size = e.size - offset
        self.f.seek(e.lba * SECTOR + offset)
        return self.f.read(size)

    def extract(self, path: str, dest: str, chunk: int = 16 << 20):
        e = self.get(path)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        self.f.seek(e.lba * SECTOR)
        left = e.size
        with open(dest, "wb") as out:
            while left:
                buf = self.f.read(min(chunk, left))
                out.write(buf)
                left -= len(buf)

    # --- patching -------------------------------------------------------

    def _last_used_sector(self) -> int:
        end = 0
        for e in self.entries.values():
            end = max(end, e.lba + (e.size + SECTOR - 1) // SECTOR)
        return end

    def replace_file(self, path: str, src: str, chunk: int = 16 << 20):
        """Replace file content. Fits in place if possible, else moves the
        file to the end of the image and fixes its directory record."""
        e = self.get(path)
        new_size = os.path.getsize(src)
        old_sectors = (e.size + SECTOR - 1) // SECTOR
        new_sectors = (new_size + SECTOR - 1) // SECTOR
        is_last = e.lba + old_sectors >= self._last_used_sector()
        if new_sectors > old_sectors and not is_last:
            e.lba = self._last_used_sector()
        self.f.seek(e.lba * SECTOR)
        with open(src, "rb") as s:
            shutil.copyfileobj(s, self.f, chunk)
        pad = new_sectors * SECTOR - new_size
        if pad:
            self.f.write(b"\x00" * pad)
        e.size = new_size
        self._write_record(e)
        self._fix_volume_size()

    def _write_record(self, e: IsoEntry):
        self.f.seek(e.record_pos + 2)
        self.f.write(_both_endian32(e.lba))
        self.f.write(_both_endian32(e.size))

    def _fix_volume_size(self):
        self.f.seek(0, os.SEEK_END)
        total = (self.f.tell() + SECTOR - 1) // SECTOR
        total = max(total, self._last_used_sector())
        self.f.truncate(total * SECTOR)
        self.volume_sectors = total
        self.f.seek(self.pvd_pos + 80)
        self.f.write(_both_endian32(total))
