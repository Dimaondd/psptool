# BLEACH ~Soul Carnival 2~ (UCJS-10106): plugin notes

## Archive

- `cfc.dig` is the last file on the disc, so changed entries are appended to
  it uncompressed and their table record repointed.
- Entry = 24-byte section records + data; sections may hold nested
  `"00000000"` packs. Blocks sit at align16(previous end) counted from the
  data start: the game depends on it (crashes otherwise).
- Uncompressed entries work fine with exact sizes.

## Text

- String tables of u16 codes. Codes are cells of the font texture (entry 1:
  s2 main 16x16 grid, s3 extra cells at 0x1000+, s4 widths).
  `data/charmap.tsv` maps codes to characters (read by OCR, about 100 unsure).
- Entry 11: the save dialog, plain UTF-8 tables drawn by the system font.
- Entry 33 s4/s5/s7/s8: the staff roll, with a font of its own (left out).
- Markup: `\n` line break, `{…}` highlight, `[8029]` command, `[#1a3]` raw glyph.

## EBOOT

The JP EBOOT is encrypted. Dump the decrypted one with PPSSPP (Settings →
Tools → Developer tools → "Dump decrypted EBOOT.BIN", then start the game)
and load it in Project → "EBOOT patch". The build ships it patched:

- `0x13ce4c`: the glyph routine no longer centres glyphs by the width table,
  so proportional text after `[802a]` draws normally;
- `0x13e64c`: centred lines (`[8013]`) are measured the way glyphs are
  drawn, `(cell*w + 8) >> 4` (own code, see `plugins/sony/elf.py`, `asm`).

The EBOOT has no game text.

## Movies

`movieNN.pmf` (PSMF, H.264 480x272). The English fan patch burned its
subtitles into the videos; "Extract" in Project → Movie subtitles reads them
from there.
