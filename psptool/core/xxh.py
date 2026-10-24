"""xxHash32 / xxHash64: the C helper (core/native.py), else Python
(same results, much slower: only for systems without the helper)."""
import ctypes
import struct

from . import native

_C = None


def _lib():
    global _C
    if _C is None:
        c = native.load("xxh")
        if c:
            c.psptool_xxh32.restype = ctypes.c_uint32
            c.psptool_xxh32.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32]
            c.psptool_xxh64.restype = ctypes.c_uint64
            c.psptool_xxh64.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint64]
        _C = c or False
    return _C or None


def xxh32(data: bytes, seed: int = 0) -> int:
    c = _lib()
    return c.psptool_xxh32(data, len(data), seed) if c else xxh32_py(data, seed)


def xxh64(data: bytes, seed: int = 0) -> int:
    c = _lib()
    return c.psptool_xxh64(data, len(data), seed) if c else xxh64_py(data, seed)


# --- Python versions, from the public algorithm description ---------------

M32, M64 = 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF
P32 = (2654435761, 2246822519, 3266489917, 668265263, 374761393)
P64 = (11400714785074694791, 14029467366897019727, 1609587929392839161,
       9650029242287828579, 2870177450012600261)


def _rol32(x, r):
    return ((x << r) | (x >> (32 - r))) & M32


def _rol64(x, r):
    return ((x << r) | (x >> (64 - r))) & M64


def xxh32_py(data: bytes, seed: int = 0) -> int:
    n, p = len(data), 0
    if n >= 16:
        v = [(seed + P32[0] + P32[1]) & M32, (seed + P32[1]) & M32, seed, (seed - P32[0]) & M32]
        while p <= n - 16:
            for i, x in enumerate(struct.unpack_from("<4I", data, p)):
                v[i] = _rol32((v[i] + x * P32[1]) & M32, 13) * P32[0] & M32
            p += 16
        h = (_rol32(v[0], 1) + _rol32(v[1], 7) + _rol32(v[2], 12) + _rol32(v[3], 18)) & M32
    else:
        h = (seed + P32[4]) & M32
    h = (h + n) & M32
    while p + 4 <= n:
        h = _rol32((h + struct.unpack_from("<I", data, p)[0] * P32[2]) & M32, 17) * P32[3] & M32
        p += 4
    while p < n:
        h = _rol32((h + data[p] * P32[4]) & M32, 11) * P32[0] & M32
        p += 1
    h ^= h >> 15
    h = h * P32[1] & M32
    h ^= h >> 13
    h = h * P32[2] & M32
    return h ^ (h >> 16)


def _round64(acc, x):
    return _rol64((acc + x * P64[1]) & M64, 31) * P64[0] & M64


def xxh64_py(data: bytes, seed: int = 0) -> int:
    n, p = len(data), 0
    if n >= 32:
        v = [(seed + P64[0] + P64[1]) & M64, (seed + P64[1]) & M64, seed, (seed - P64[0]) & M64]
        while p <= n - 32:
            for i, x in enumerate(struct.unpack_from("<4Q", data, p)):
                v[i] = _round64(v[i], x)
            p += 32
        h = (_rol64(v[0], 1) + _rol64(v[1], 7) + _rol64(v[2], 12) + _rol64(v[3], 18)) & M64
        for x in v:
            h = ((h ^ _round64(0, x)) * P64[0] + P64[3]) & M64
    else:
        h = (seed + P64[4]) & M64
    h = (h + n) & M64
    while p + 8 <= n:
        h = (_rol64(h ^ _round64(0, struct.unpack_from("<Q", data, p)[0]), 27) * P64[0] + P64[3]) & M64
        p += 8
    if p + 4 <= n:
        h = (_rol64(h ^ (struct.unpack_from("<I", data, p)[0] * P64[0] & M64), 23) * P64[1] + P64[2]) & M64
        p += 4
    while p < n:
        h = _rol64(h ^ (data[p] * P64[4] & M64), 11) * P64[0] & M64
        p += 1
    h ^= h >> 33
    h = h * P64[1] & M64
    h ^= h >> 29
    h = h * P64[2] & M64
    return h ^ (h >> 32)
