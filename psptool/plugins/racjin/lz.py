"""Racjin LZ: 9-bit tokens packed LSB-first into a bitstream.

token & 0x100 -> literal byte (token & 0xff)
otherwise     -> copy (token & 7) + 1 bytes from history; the source
                 position is table[last_byte * 32 + (token >> 3)].

After every token, the position where it started is stored in the
32-slot ring of the byte that preceded it.

Own implementation written from the public algorithm description.
A C version (_lz.c, see core/native.py) is used when there is one.
"""
import ctypes

from ...core import native

_C = None


def _load_c():
    global _C
    if _C is None:
        _C = native.load("racjin_lz") or False
        if _C:
            _C.racjin_decompress.restype = ctypes.c_long
            _C.racjin_decompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
    return _C or None


def decompress(src: bytes, size: int) -> bytes:
    c = _load_c()
    if c:
        buf = ctypes.create_string_buffer(size)
        got = c.racjin_decompress(src, len(src), buf, size)
        if got != size:
            raise ValueError("racjin lz: got %d bytes, want %d" % (got, size))
        return buf.raw
    return decompress_py(src, size)


def decompress_py(src: bytes, size: int) -> bytes:
    out = bytearray()
    table = [0] * 8192
    ring = [0] * 256
    n = len(src)
    src = src + b"\x00"  # lets us always read two bytes
    bitpos = 0
    while len(out) < size and bitpos + 9 <= n * 8:
        b = bitpos >> 3
        v = ((src[b] | (src[b + 1] << 8)) >> (bitpos & 7)) & 0x1FF
        bitpos += 9
        pos = len(out)
        last = out[pos - 1] if pos else 0
        if v & 0x100:
            out.append(v & 0xFF)
        else:
            s = table[(last << 5) | (v >> 3)]
            for i in range((v & 7) + 1):
                out.append(out[s + i])
        slot = (last << 5) | ring[last]
        table[slot] = pos
        ring[last] = (ring[last] + 1) & 31
    if len(out) != size:
        raise ValueError("racjin lz: got %d bytes, want %d" % (len(out), size))
    return bytes(out)


def compress(data: bytes) -> bytes:
    """Greedy encoder. Mirrors the decoder's table, so for each token we
    try all 32 candidates of the current context and take the longest."""
    table = [0] * 8192
    ring = [0] * 256
    bits = 0
    nbits = 0
    out = bytearray()
    pos = 0
    n = len(data)
    while pos < n:
        last = data[pos - 1] if pos else 0
        base = last << 5
        best_len, best_idx = 0, 0
        for idx in range(32):
            s = table[base | idx]
            if s >= pos:
                continue
            ln = 0
            # source may overlap the output, same as the decoder
            while ln < 8 and pos + ln < n and data[s + ln] == data[pos + ln]:
                ln += 1
            if ln > best_len:
                best_len, best_idx = ln, idx
                if ln == 8:
                    break
        if best_len:
            tok = (best_idx << 3) | (best_len - 1)
            step = best_len
        else:
            tok = 0x100 | data[pos]
            step = 1
        bits |= tok << nbits
        nbits += 9
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8
        table[base | ring[last]] = pos
        ring[last] = (ring[last] + 1) & 31
        pos += step
    if nbits:
        out.append(bits & 0xFF)
    return bytes(out)

