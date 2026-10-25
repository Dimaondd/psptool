# psptool

Unpack a PSP game ISO, change its files, pack it back. Built around game
plugins; the first one is BLEACH ~Soul Carnival 2~ (UCJS-10106).

## Install

**The app** (macOS on Apple Silicon, Windows 10/11): download it from
[Releases](https://github.com/Dimaondd/psptool/releases).

- macOS: open the `.dmg`, drag PSPtool to Applications. The app is not
  signed by Apple, so the first start is blocked: right-click → Open, or
  System Settings → Privacy & Security → "Open Anyway".
- Windows: unzip, run `PSPtool.exe`. SmartScreen may warn about an unknown
  publisher: "More info" → "Run anyway".

Optional:
- [Tesseract](https://github.com/tesseract-ocr/tesseract) with Japanese
  data, for reading movie subtitles and texture text on Windows (macOS uses
  its own Vision).
- [PPSSPP](https://www.ppsspp.org) for "Проверить в игре" and HD textures.
- The AI upscalers download from the HD tab when you first need them.

PSPtool contains no game data. Use your own copy of the game.

**From source** (any system with Python 3.9+):

```
python3 -m venv .venv && .venv/bin/pip install -e ".[app]"
.venv/bin/psptool-app                      # the app window
.venv/bin/psptool ui work                  # or the web UI in a browser
```

## Settings (sidebar → Настройки, ⌘,)

- **Appearance:** light / dark / system theme; one of the PSP's twelve
  theme colours (or "by month", as the console did) with the XMB wave in the
  background; interface language.
- **Languages:** English, Русский, Español, Português (Brasil), Français,
  Deutsch, 简体中文, 日本語. Strings live in `psptool/ui/i18n_table.py`; after
  editing it run `python -m psptool.ui.i18n_table`.
- Language model, PPSSPP path, text recognition, components (AI upscalers to
  download, ffmpeg, Tesseract) and access from other devices.

## Command line

```
python3 -m psptool init game.iso work      # detect game, make project
python3 -m psptool unpack work             # ISO files -> work/files
python3 -m psptool cfc work 19 23          # cfc.dig entries -> work/cfc/NNNN.bin
python3 -m psptool texts work              # strings -> work/texts/NNNN.json
python3 -m psptool ref work en.iso         # reference text from another version
python3 -m psptool pack work out.iso       # changes + translation -> new ISO
python3 -m psptool info work               # what changed
python3 -m psptool font work               # Cyrillic into the game font
python3 -m psptool ui work                 # web UI, http://127.0.0.1:8765
```

Build the app yourself: `pip install -e ".[build]"`, then
`python -m psptool.core.native && python packaging/fetch_fonts.py &&
python packaging/icon.py && pyinstaller packaging/psptool.spec`.

## EBOOT

The JP EBOOT is encrypted. Dump the decrypted one with PPSSPP (Settings →
Tools → Developer tools → "Dump decrypted EBOOT.BIN", then start the game)
and load it in Project → "Патч EBOOT". The build ships it patched:
`0x13ce4c` — the glyph routine no longer centres glyphs by the width table,
so proportional text after `[802a]` draws normally; `0x13e64c` — centred
lines (`[8013]`) are measured the way glyphs are drawn, `(cell*w + 8) >> 4`
(own code, see `elf.asm`). EBOOT has no game text.

## Textures (UI → Текстуры)

All GIM images in cfc.dig (49k), also those inside sprite containers.
"С текстом" = pixels differ in the reference ISO (65 images in the EN
patch). Download PNG → edit → upload (or drop on a card). Indexed textures
keep their palette: each pixel takes the nearest colour, so draw text in
colours the texture already has.

## Movie subtitles (UI → Проект → Субтитры роликов)

Needs ffmpeg (`brew install ffmpeg`) and text recognition (see below).
The English patch burned its subtitles into the videos. "Достать" compares
each movie of the reference with the original, finds the lines and reads
them with OCR: they show up in the Текст tab as `movieNN` files (English as
the source, a frame preview with the translation drawn on it). On build,
only the ~2 s segments that show a translated line are decoded, get the
text drawn (PT Sans Bold, white with an outline) and are encoded again
with x264 to fit their place; the file keeps its size, audio is untouched.

## Auto-translating texture text (Текстуры → a texture → Автоперевод)

OCR finds the Japanese lines and the English ones of the
reference, guesses fill/outline colours, the LLM translates (with an
optional note), the text is wiped (edge fill) and redrawn with a TTF to
fit the box. Boxes can be moved/resized, colours swapped, sizes set.
Layouts are kept in textures/auto/<id>.json; "Сохранить" makes the edit.

## HD textures for PPSSPP (UI → Проект → HD-текстуры)

A texture pack for PPSSPP only: the ISO stays the same, real PSPs are not
affected. Turn on "Сохранять новые текстуры" (PPSSPP closed), play the
translated build: PPSSPP dumps every texture it meets into
PSP/TEXTURES/UCJS10106/new. "Увеличить новые" upscales them with
Real-ESRGAN (ncnn-vulkan, in ~/.cache/psptool/realesrgan) next to it,
where PPSSPP picks them up; "Собрать zip" makes a pack to share.
textures.ini uses xxh64 without addresses (set before the first dump).

"Собрать из архива" computes the same hash PPSSPP uses (xxh64 of the
texture memory, low 32 bits, seed 0xBACD7814) for every GIM of cfc.dig
(translated entries from the last build) and upscales them without
playing; they are named with address and palette zeroed, so they match
any palette (an exact dump from playing wins). Character sprites drawn
from parts of their own format still come from playing only. Coverage
bars show both sources; "Запаковать пак" zips everything upscaled.

## Cleaner movies (UI → HD-текстуры → Ролики)

Movies stay 480x272 (the PSP decoder's size), but every frame goes through
Real-CUGAN at 2x (mode: conservative, no denoise, denoise 1-3) and back
down: cleaner lines, fewer compression blocks. "Подготовить" makes a
near-lossless intermediate per movie in movies/enhanced/<mode>/ (about a
minute per 1100 frames); with "Собирать образ из улучшенных роликов" on,
the build encodes every movie from it into its own packs (same file size)
and draws the subtitles on top. The preview shows any frame before/after.

## Text recognition (Настройки → Распознавание текста)

Movie subtitles and text in textures are read with OCR. Two engines:

- macOS Vision: macOS with Xcode command line tools (`xcode-select --install`);
  a small Swift tool is compiled on first use. Best for Japanese.
- Tesseract, any system: `brew install tesseract tesseract-lang` (macOS),
  `apt install tesseract-ocr tesseract-ocr-jpn` (Linux), the UB Mannheim
  installer with Japanese data (Windows). Reads movie subtitles nearly as
  well as Vision (only the subtitle's letters are given to it); stylised
  Japanese titles in textures much worse.

"Автоматически" uses Vision when it is there, else Tesseract. Settings:
`~/.config/psptool/ocr.json`.

## Access from other devices (Настройки → Доступ с других устройств)

Set a password and tick the box: the server then listens on every address
and asks other devices for the password (this computer never needs it).
With Tailscale on the computer and the phone, the tailnet address works from
anywhere. Settings: `~/.config/psptool/remote.json` (password hashed).

## LLM translation (LLM tab; connection in Настройки → Языковая модель)

- Anthropic (official SDK, default `claude-opus-5-5`): key in the UI,
  `ANTHROPIC_API_KEY`, or an `ant auth login` profile. Requests use
  `fallbacks: "default"`, so a safety decline is retried on a fallback model.
- Any OpenAI-compatible endpoint: OpenAI, OpenRouter, Ollama
  (`http://localhost:11434/v1`), LM Studio (`http://localhost:1234/v1`).
- Keys live in `~/.config/psptool/llm.json` (0600), not in the project.
- Each answer is checked: same commands, `{}` pairs, line breaks, all chars
  in the font. Bad lines go back to the model once with the reason.
- Same source line translated once (translation memory). Machine output is
  marked "LLM" until a person edits it. Project glossary: `glossary.txt`.

Translate in the UI (or in `texts/*.json`, field `dst`). Markup:
`\n` line break, `{…}` highlight, `[8029]` command, `[#1a3]` raw glyph.

Edit files in `work/files` or `work/cfc` in place; `pack` finds them by hash.
Files dropped into `work/files/...` (e.g. movies) are packed too.

## Layout

- `psptool/core` — ISO9660, PARAM.SFO, project, plugin registry
- `psptool/plugins/<tech>` — formats: `racjin` (CFC.DIG, LZ, containers,
  string tables), `sony` (GIM)
- `psptool/ui` — web UI; tabs depend on the plugin's `features`
- `psptool/games/<game>` — game plugins that wire formats together
- `research/` — throwaway scripts

## BLEACH SC2 notes

- `cfc.dig` is the last file on the disc, so changed entries are appended
  to it uncompressed and their table record repointed (same as the EN patch).
- Entry = 24-byte section records + data; sections may hold nested
  `"00000000"` packs. Blocks sit at align16(previous end) counted from the
  data start — the game depends on it (crashes otherwise).
- Uncompressed entries work fine with exact sizes.
- Text: string tables of u16 codes. Codes = cells of the font texture
  (entry 1: s2 main 16x16 grid, s3 extra cells at 0x1000+, s4 widths).
  `games/bleach_sc2/data/charmap.tsv` maps codes to chars (OCR, ~100 unsure).
- `EBOOT.BIN` is encrypted in the JP image; the EN patch ships it decrypted.

## License

MIT, see LICENSE. Release builds also carry ffmpeg (LGPL/GPL, from
imageio-ffmpeg) and PT Sans (SIL Open Font License); the upscalers are
downloaded from their own releases (MIT/BSD).
