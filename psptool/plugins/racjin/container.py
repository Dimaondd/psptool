"""Containers inside a cfc.dig entry.

Entry = `sections` records of 24 bytes (id, size, offset, a, b, c), then
data. A section may hold a "pack":

    01 00 00 00 10 00 00 00 "00000000"      16-byte magic
    u32 count
    count * (u32 offset, u32 size, u32 align)  offsets from magic end

Packs nest. Blocks start at align16(end of the previous block), counted
from the start of the data (section data start / pack body start), and
the game relies on that. Children are not always listed in order, so changes
are spliced in: the new blob (padded to 16) replaces the old one and every
offset after it moves by the same amount. An unchanged tree comes out
byte-identical.
"""
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

PACK_MAGIC = b"\x01\x00\x00\x00\x10\x00\x00\x00" + b"0" * 8


@dataclass
class Node:
    path: str
    start: int                     # absolute, in the entry buffer
    size: int
    size_pos: int                  # where our size field lives
    off_pos: int                   # where our offset field lives
    off_base: int                  # offset field is relative to this
    align_base: int                # blocks are 16-aligned relative to this
    children: List["Node"] = field(default_factory=list)

    def walk(self) -> Iterator["Node"]:
        yield self
        for c in self.children:
            yield from c.walk()


def _pack_children(buf: bytes, n: Node):
    blk = buf[n.start:n.start + n.size]
    if blk[:16] != PACK_MAGIC or len(blk) < 20:
        return
    count = struct.unpack_from("<I", blk, 16)[0]
    if not 0 < count < 10000 or 20 + 12 * count > len(blk):
        return
    kids = []
    for k in range(count):
        rec = n.start + 20 + 12 * k
        o, sz, _al = struct.unpack_from("<3I", buf, rec)
        if 16 + o + sz > n.size:
            return
        kids.append(Node("%s/%d" % (n.path, k), n.start + 16 + o, sz, rec + 4, rec, n.start + 16, n.start + 16))
    n.children = kids
    for c in kids:
        _pack_children(buf, c)


def parse_entry(buf: bytes, sections: int) -> List[Node]:
    out = []
    if 24 * sections > len(buf):
        return out
    for k in range(sections):
        rec = 24 * k
        sid, size, off = struct.unpack_from("<3I", buf, rec)
        if off + size > len(buf):
            return []
        n = Node("s%d" % sid, off, size, rec + 4, rec + 8, 0, 24 * sections)
        _pack_children(buf, n)
        out.append(n)
    return out


def leaves(nodes: List[Node]) -> Iterator[Node]:
    for top in nodes:
        for n in top.walk():
            if not n.children:
                yield n


def _ancestors(nodes: List[Node], target: Node) -> List[Node]:
    def find(n, chain):
        if n is target:
            return chain
        for c in n.children:
            r = find(c, chain + [n])
            if r is not None:
                return r
        return None
    for top in nodes:
        r = find(top, [])
        if r is not None:
            return r
    raise KeyError(target.path)


class Entry:
    """Mutable view of one cfc entry: replace leaves, get bytes back."""

    def __init__(self, data: bytes, sections: int):
        self.buf = bytearray(data)
        self.sections = sections
        self.nodes = parse_entry(self.buf, sections)

    def leaves(self) -> Dict[str, Node]:
        return {n.path: n for n in leaves(self.nodes)}

    def read(self, n: Node) -> bytes:
        return bytes(self.buf[n.start:n.start + n.size])

    def replace(self, path: str, data: bytes):
        node = self.leaves()[path]
        old = node.size
        # the game finds blocks at align16(end of previous), so the blob is
        # swapped together with its alignment padding and what follows
        # moves by the change of the aligned end
        base = node.align_base
        up = lambda v: base + (v - base + 15) // 16 * 16  # noqa: E731
        nxt = min([n.start for top in self.nodes for n in top.walk() if n.start > node.start]
                  + [len(self.buf)])
        old_end = max(node.start + old, min(up(node.start + old), nxt))
        body = data + b"\x00" * (up(node.start + len(data)) - node.start - len(data))
        delta = len(body) - (old_end - node.start)
        chain = _ancestors(self.nodes, node)
        self.buf[node.start:old_end] = body
        node.size = len(data)
        struct.pack_into("<I", self.buf, node.size_pos, node.size)
        if delta:
            self._shift(node, chain, delta)

    def _shift(self, node: Node, chain: List[Node], delta: int):
        cut = node.start  # everything starting after this moves
        # fix offset fields that point past the cut. Record positions
        # themselves only move if they sit after the cut (they never do
        # for our own chain: headers come before their data).
        for top in self.nodes:
            for n in top.walk():
                if n.start > cut:
                    n.start += delta
                if n.size_pos > cut:
                    n.size_pos += delta
                if n.off_pos > cut:
                    n.off_pos += delta
                if n.off_base > cut:
                    n.off_base += delta
                if n.align_base > cut:
                    n.align_base += delta
        for top in self.nodes:
            for n in top.walk():
                if n is not node and n.start > cut:
                    struct.pack_into("<I", self.buf, n.off_pos, n.start - n.off_base)
        for a in chain:
            a.size += delta
            struct.pack_into("<I", self.buf, a.size_pos, a.size)

    def bytes(self) -> bytes:
        return bytes(self.buf)


def find_leaf(nodes: List[Node], path: str) -> Optional[Node]:
    for n in leaves(nodes):
        if n.path == path:
            return n
    return None


def leaf_items(data: bytes, sections: int) -> List[Tuple[str, bytes]]:
    nodes = parse_entry(data, sections)
    return [(n.path, data[n.start:n.start + n.size]) for n in leaves(nodes)]
