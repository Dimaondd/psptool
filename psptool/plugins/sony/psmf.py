"""PSMF movies (.pmf): MPEG-PS in 2048-byte packs after a 0x800 header.

Video (PES 0xE0, H.264) is one continuous stream. It is cut into
segments of ~2 s: the first pack of a segment carries a system header
(0xBB), a private stream 2 (0xBF) and the video PES with PTS/DTS. The
0xBF block lists the sizes of all frames of the segment; it is repeated
at every GOP start inside the segment. The header's EP map points at the
segment starts. Audio (PES 0xBD, ATRAC3plus) lives in packs of its own.

`replace_segment` puts a re-encoded segment (same frames, same timing)
into the video packs of that segment, audio packs stay where they are.
"""
import struct
from dataclasses import dataclass, field
from typing import List, Tuple

PACK = 2048


def _pts(b: bytes, o: int) -> int:
    return (((b[o] >> 1) & 7) << 30) | (b[o + 1] << 22) | ((b[o + 2] >> 1) << 15) | (b[o + 3] << 7) | (b[o + 4] >> 1)


def nal_units(es: bytes) -> List[Tuple[int, int]]:
    """[(offset of 00 00 01, nal type)]"""
    out, i = [], 0
    while True:
        j = es.find(b"\0\0\1", i)
        if j < 0 or j + 3 >= len(es):
            return out
        # 4-byte start code: the zero before belongs to it
        out.append((j - 1 if j and es[j - 1] == 0 else j, es[j + 3] & 0x1F))
        i = j + 3


def access_units(es: bytes) -> List[bytes]:
    """Split at access unit delimiters (NAL 9), one per frame."""
    starts = [o for o, t in nal_units(es) if t == 9]
    if not starts:
        raise ValueError("no access unit delimiters in the stream")
    starts.append(len(es))
    return [es[starts[k]:starts[k + 1]] for k in range(len(starts) - 1)]


@dataclass
class Segment:
    first: int                  # pack index of the segment start
    end: int                    # pack index after the segment
    pts: int                    # of its first frame
    bf: bytes                   # private stream 2 payload (frame size table)
    frames: int = 0
    video_packs: List[int] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return (self.pts - 90000) / 90000


class Psmf:
    def __init__(self, data: bytes):
        if data[:4] != b"PSMF":
            raise ValueError("not a PSMF file")
        self.data = bytearray(data)
        self.start, self.size = struct.unpack_from(">II", data, 8)
        self.segments = self._segments()

    # --- reading ---------------------------------------------------------

    def packs(self) -> int:
        return self.size // PACK

    def _pack(self, k: int) -> memoryview:
        o = self.start + k * PACK
        return memoryview(self.data)[o:o + PACK]

    def _pes(self, k: int):
        """[(stream id, offset in pack, total length)] of a pack."""
        p = self._pack(k)
        o = 14 + (p[13] & 7)
        out = []
        while o + 6 <= PACK and bytes(p[o:o + 3]) == b"\0\0\1":
            sid = p[o + 3]
            ln = struct.unpack_from(">H", p, o + 4)[0]
            out.append((sid, o, 6 + ln))
            o += 6 + ln
        return out

    def _segments(self) -> List[Segment]:
        segs: List[Segment] = []
        for k in range(self.packs()):
            pes = self._pes(k)
            sids = [s for s, _, _ in pes]
            if 0xBF in sids and 0xE0 in sids:
                p = self._pack(k)
                _, o, n = pes[sids.index(0xBF)]
                bf = bytes(p[o + 6:o + n])
                _, vo, _ = pes[sids.index(0xE0)]
                if not segs or segs[-1].bf != bf:  # a GOP inside a segment repeats its bf
                    if segs:
                        segs[-1].end = k
                    segs.append(Segment(k, 0, _pts(p, vo + 9), bf))
            if segs and 0xE0 in sids:
                segs[-1].video_packs.append(k)
        if segs:
            segs[-1].end = self.packs()
        for s in segs:
            s.frames = struct.unpack_from(">H", s.bf, 16)[0]
        return segs

    def video_es(self, seg: Segment) -> bytes:
        out = bytearray()
        for k in seg.video_packs:
            p = self._pack(k)
            for sid, o, n in self._pes(k):
                if sid == 0xE0:
                    hl = p[o + 8]
                    out += p[o + 9 + hl:o + n]
        return bytes(out)

    def frame_sizes(self, seg: Segment) -> List[int]:
        return [struct.unpack_from(">H", seg.bf, 20 + 4 * k)[0] for k in range(seg.frames)]

    def capacity(self, seg: Segment) -> int:
        """Bytes of video the segment's packs can hold (GOP starts inside
        the segment lose their timestamps: one GOP per segment)."""
        return sum(PACK - self._slot(seg, k)[1] for k in seg.video_packs)

    def _slot(self, seg: Segment, k: int) -> Tuple[int, int]:
        """(video PES offset, payload offset) in pack k after rewriting."""
        p = self._pack(k)
        vo = next(o for sid, o, n in self._pes(k) if sid == 0xE0)
        if k == seg.first:
            return vo, vo + 9 + p[vo + 8]
        return vo, vo + 9

    # --- writing ---------------------------------------------------------

    def replace_segment(self, index: int, es: bytes):
        """New video for one segment: same number of frames (access units,
        each starting with an AUD), first one an IDR."""
        seg = self.segments[index]
        aus = access_units(es)
        if len(aus) != seg.frames:
            raise ValueError("segment %d: %d frames, need %d" % (index, len(aus), seg.frames))
        if max(len(a) for a in aus) > 0xFFFF:
            raise ValueError("segment %d: a frame is over 64 KB" % index)
        cap = self.capacity(seg)
        if len(es) > cap:
            raise ValueError("segment %d: %d bytes, room for %d" % (index, len(es), cap))
        bf = bytearray(seg.bf)
        for k, a in enumerate(aus):
            struct.pack_into(">H", bf, 20 + 4 * k, len(a))
        bf = bytes(bf)
        pos = 0
        for k in seg.video_packs:
            p = self._pack(k)
            vo, start = self._slot(seg, k)
            # a GOP start pack: its bf is the table of the whole segment
            for sid, o, n in self._pes(k):
                if sid == 0xBF:
                    p[o + 6:o + n] = bf
            if k != seg.first:  # plain PES header, no PTS/DTS
                p[vo + 6:vo + 9] = b"\x81\x00\x00"
            take = min(PACK - start, len(es) - pos)
            if take <= 0:  # nothing left: padding
                self._pad(p, vo)
                continue
            gap = PACK - start - take
            if 0 < gap < 6:  # too small for a padding PES: header stuffing bytes
                p[vo + 8] += gap
                p[start:start + gap] = b"\xff" * gap
                start += gap
            p[start:start + take] = es[pos:pos + take]
            pos += take
            end = start + take
            struct.pack_into(">H", p, vo + 4, end - vo - 6)
            if end < PACK:
                self._pad(p, end)
        self.segments = self._segments()

    @staticmethod
    def _pad(p: memoryview, at: int):
        """Padding PES (0xBE) from `at` to the end of the pack."""
        n = PACK - at
        if n < 6:  # replace_segment stuffs the header instead
            raise ValueError("no room for padding")
        p[at:at + 6] = b"\0\0\1\xbe" + struct.pack(">H", n - 6)
        p[at + 6:PACK] = b"\xff" * (n - 6)

    def bytes(self) -> bytes:
        return bytes(self.data)
