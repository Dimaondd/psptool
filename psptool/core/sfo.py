"""PARAM.SFO reader (key/value table with game title, disc id, etc.)."""
import struct
from typing import Dict, Union


def parse_sfo(data: bytes) -> Dict[str, Union[str, int]]:
    magic, _ver, key_off, val_off, count = struct.unpack_from("<4sIIII", data)
    if magic != b"\x00PSF":
        raise ValueError("not a PARAM.SFO")
    out = {}
    for i in range(count):
        k_off, fmt, length, _max, v_off = struct.unpack_from("<HHIII", data, 20 + i * 16)
        end = data.index(b"\x00", key_off + k_off)
        key = data[key_off + k_off:end].decode("ascii")
        raw = data[val_off + v_off:val_off + v_off + length]
        if fmt == 0x0404:
            out[key] = struct.unpack("<I", raw[:4])[0]
        else:
            out[key] = raw.rstrip(b"\x00").decode("utf-8", "replace")
    return out
