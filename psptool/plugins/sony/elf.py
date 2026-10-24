"""PSP ELF/PRX (decrypted EBOOT): virtual address -> file offset, and
small code patches checked against the expected original bytes."""
import hashlib
import struct
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Patch:
    """`old`: the bytes the game has there, or "sha1:<hex>" of them (the
    patch then replaces len(new) bytes)."""
    name: str
    vaddr: int
    old: object
    new: bytes

    def matches(self, cur: bytes) -> bool:
        if isinstance(self.old, str):
            return hashlib.sha1(cur).hexdigest() == self.old.split(":", 1)[1]
        return cur == self.old


def segments(b: bytes) -> List[Tuple[int, int, int]]:
    """[(vaddr, file_offset, size)] of loadable segments."""
    if b[:4] != b"\x7fELF":
        raise ValueError("not an ELF (is the EBOOT still encrypted?)")
    phoff = struct.unpack_from("<I", b, 0x1C)[0]
    phnum = struct.unpack_from("<H", b, 0x2C)[0]
    out = []
    for k in range(phnum):
        t, off, va, _pa, fsz, _msz, _fl, _al = struct.unpack_from("<8I", b, phoff + 32 * k)
        if t == 1:
            out.append((va, off, fsz))
    return out


def offset_of(b: bytes, vaddr: int) -> int:
    for va, off, size in segments(b):
        if va <= vaddr < va + size:
            return off + vaddr - va
    raise KeyError(hex(vaddr))


def apply(b: bytes, patches: List[Patch]) -> bytes:
    out = bytearray(b)
    for p in patches:
        o = offset_of(b, p.vaddr)
        cur = bytes(out[o:o + len(p.new)])
        if cur == p.new:
            continue
        if not p.matches(cur):
            raise ValueError("%s: unexpected bytes at %x (%s), wrong EBOOT?" % (p.name, p.vaddr, cur.hex()))
        out[o:o + len(p.new)] = p.new
    return bytes(out)


def mips_b(from_vaddr: int, to_vaddr: int) -> bytes:
    """`b to` (beq $zero, $zero) placed at from_vaddr."""
    off = (to_vaddr - (from_vaddr + 4)) >> 2
    return struct.pack("<I", (0x04 << 26) | (off & 0xFFFF))


# --- a few Allegrex (MIPS II) instructions, enough for small patches -----

REG = {n: i for i, n in enumerate(
    "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split())}


def _r(funct: int, rs="zero", rt="zero", rd="zero", sa=0) -> int:
    return (REG[rs] << 21) | (REG[rt] << 16) | (REG[rd] << 11) | (sa << 6) | funct


def _i(op: int, rs: str, rt: str, imm: int) -> int:
    return (op << 26) | (REG[rs] << 21) | (REG[rt] << 16) | (imm & 0xFFFF)


def asm(lines: List[str]) -> bytes:
    """`op a, b, c` lines -> little-endian words. Knows: nop, lbu, addiu,
    xori, sra, mult, mflo, addu, sltu."""
    out = b""
    for line in lines:
        op, _, rest = line.strip().partition(" ")
        a = [x.strip() for x in rest.split(",")] if rest else []
        if op == "nop":
            w = 0
        elif op == "lbu":  # lbu rt, off(rs)
            off, rs = a[1].rstrip(")").split("(")
            w = _i(0x24, rs, a[0], int(off, 0))
        elif op == "addiu":
            w = _i(0x09, a[1], a[0], int(a[2], 0))
        elif op == "xori":
            w = _i(0x0E, a[1], a[0], int(a[2], 0))
        elif op == "sra":
            w = _r(0x03, rt=a[1], rd=a[0], sa=int(a[2], 0))
        elif op == "mult":
            w = _r(0x18, rs=a[0], rt=a[1])
        elif op == "mflo":
            w = _r(0x12, rd=a[0])
        elif op == "addu":
            w = _r(0x21, rs=a[1], rt=a[2], rd=a[0])
        elif op == "sltu":
            w = _r(0x2B, rs=a[1], rt=a[2], rd=a[0])
        else:
            raise ValueError("asm: unknown op " + op)
        out += struct.pack("<I", w)
    return out
