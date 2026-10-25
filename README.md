# PSPtool

A tool for translating PSP games. It unpacks the game image, lets you
translate its text (by hand or with a language model), the text drawn in its
textures and the subtitles burned into its movies, and builds a patched ISO
for the PSP and emulators. On the side it makes HD texture
packs and cleaner movies for PPSSPP.

Formats are handled by plugins (archives, string tables, fonts, textures,
movies), and each game gets a small plugin that wires them together.
Tested with BLEACH ~Soul Carnival 2~ (JP).

PSPtool contains no game data: use your own copy of the game.

## Features

- **Text:** every string table of the game, side by side with the original
  and a reference from another version (e.g. an English release or fan
  patch), with a preview in the game's own font and a width check.
- **Language model translation:** Anthropic or any OpenAI-compatible
  endpoint (OpenAI, OpenRouter, Ollama, LM Studio), with a glossary,
  translation memory and reviewed lines used as examples.
- **Font:** new letters drawn into the game's font from any TTF/OTF.
- **Textures:** find the ones with text, edit them, or auto-translate them
  (OCR, translation, the text erased and redrawn in a matching style).
- **Movie subtitles:** lines read from a reference version's videos and
  drawn, translated, into the original ones.
- **HD textures and cleaner movies for PPSSPP** with AI upscalers.
- **Test in game:** build a test image and start it in PPSSPP from a save
  state, a line of your choice put in place.
- **Works from a phone** over Tailscale or Wi-Fi (password protected).
- An interface in the style of Apple's apps, light and dark, in eight
  languages, with the PSP's twelve theme colours.

## Install

**The app** (macOS on Apple Silicon, Windows 10/11): download it from
[Releases](https://github.com/Dimaondd/psptool/releases).

- macOS: open the `.dmg`, drag PSPtool to Applications. The app is not
  signed by Apple, so the first start is blocked: right-click → Open, or
  System Settings → Privacy & Security → "Open Anyway".
- Windows: unzip, run `PSPtool.exe`. SmartScreen may warn about an unknown
  publisher: "More info" → "Run anyway".

Optional:

- [PPSSPP](https://www.ppsspp.org) for "Test in game" and HD textures.
- [Tesseract](https://github.com/tesseract-ocr/tesseract) with Japanese
  data, for text recognition on Windows and Linux (macOS uses its own Vision).
- The AI upscalers download from Settings → Components when you need them.

**From source** (Python 3.9+, any system):

```
python3 -m venv .venv && .venv/bin/pip install -e ".[app]"
.venv/bin/psptool-app                      # the app window
.venv/bin/psptool ui work                  # or the web UI in a browser
```

Build the app yourself: `pip install -e ".[build]"`, then
`python -m psptool.core.native && python packaging/fetch_fonts.py &&
python packaging/icon.py && pyinstaller packaging/psptool.spec`.

## How a translation goes

The Project screen lists the steps:

1. **New project:** pick the game image and a folder for the project.
2. **Unpack the image** and **Game text**: the string tables become
   `texts/NNNN.json` in the project.
3. **Reference from another version** (optional): the same game in another
   language; its lines appear next to yours.
4. **Movie subtitles** (optional): lines burned into the reference's movies.
5. **EBOOT patch** (if the game's plugin needs one, e.g. for proportional
   text): load the decrypted EBOOT dumped by PPSSPP.
6. Translate in **Text**, check in **Test in game**, then **Build the image**.

The project folder holds the unpacked game files next to your work (texts,
glossary, edited textures), so keep it private: do not publish it.

## Text

Files on the left, lines on the right: original, reference, translation and
a preview in the game font. Search over all files, sort and filter (by
translated / reviewed / machine-translated, where to search), mark lines as
reviewed, copy a translation to every repeat of the line. Markup in lines:
`\n` line break, `{…}` highlight, `[8029]` engine command, `[#1a3]` a raw
glyph.

## Language model (LLM)

- Anthropic (official SDK): key in Settings, `ANTHROPIC_API_KEY`, or an
  `ant auth login` profile. Requests use `fallbacks: "default"`, so a
  declined request is retried on a fallback model.
- Any OpenAI-compatible endpoint: OpenAI, OpenRouter, Ollama
  (`http://localhost:11434/v1`), LM Studio (`http://localhost:1234/v1`).
- Each answer is checked (same commands, `{}` pairs, line breaks, every
  character present in the font); bad lines go back to the model once with
  the reason. The same source line is translated once. Machine output is
  marked "LLM" until a person edits it. Project glossary: `glossary.txt`.
- Keys live in `~/.config/psptool/llm.json` (mode 0600), never in a project.

## Textures

Every texture of the game (GIM, PNG), also those inside sprite containers.
"With text" shows the ones that differ in the reference version. Download a
PNG, edit, upload (or drop it on a card); indexed textures keep their
palette, so draw text in colours the texture already has.

**Auto-translate:** OCR finds the lines (and the reference's), guesses fill
and outline colours, the language model translates (with an optional hint),
the text is erased and redrawn with a TTF to fit its box. Boxes can be
moved and resized, colours swapped, sizes set.

## Movie subtitles

Needs ffmpeg (bundled in the app; `brew install ffmpeg` from source) and
text recognition. When a reference version burned subtitles into its
movies, "Extract" compares each movie with the original, finds the lines
and reads them; they appear in Text as `movieNN` files. On build only the
segments that show a translated line are decoded, get the text drawn and
are encoded again to fit their place: the file keeps its size, the audio is
untouched.

## HD textures for PPSSPP

A texture pack for PPSSPP only: the ISO stays the same, a real PSP is not
affected.

- **From play:** turn on "Save new textures" (PPSSPP closed) and play;
  PPSSPP dumps every texture it meets, "Upscale new" upscales them where
  PPSSPP picks them up.
- **From the archive:** "Collect from archive" computes the hash PPSSPP
  uses (xxh64 of the texture memory) for every texture in the game files and
  upscales them without playing. Character sprites built from parts still
  come from playing only.
- Models: Real-ESRGAN, Real-CUGAN, waifu2x. The gallery compares before and
  after, filters by size and model, and marks textures to redo with another
  model. "Pack it" makes a zip to share.

## Cleaner movies

Movies stay 480x272 (the PSP decoder's size), but every frame goes through
Real-CUGAN at 2x and back down: cleaner lines, fewer compression blocks.
"Prepare" makes an intermediate per movie; with "Build the image with the
cleaned movies" on, the build encodes every movie from it and draws the
subtitles on top. The preview shows any frame before and after.

## Settings (⌘,)

- **Appearance:** theme (light, dark, system), one of the PSP's twelve
  theme colours or "by month" as the console did, the XMB wave, language.
- **Languages:** English, Русский, Español, Português (Brasil), Français,
  Deutsch, 简体中文, 日本語. Strings live in `psptool/ui/i18n_table.py`;
  after editing it run `python -m psptool.ui.i18n_table`.
- **Language model, emulator** (PPSSPP's path), **components** (upscalers
  to download, ffmpeg, Tesseract).
- **Text recognition:** macOS Vision (best for Japanese; needs the Xcode
  command line tools when run from source) or Tesseract on any system
  (`brew install tesseract tesseract-lang`, `apt install tesseract-ocr
  tesseract-ocr-jpn`, or the UB Mannheim installer on Windows).
- **Access from other devices:** set a password and turn it on; the server
  then answers other devices that know the password. With Tailscale on the
  computer and the phone it works from anywhere, encrypted.

Settings are stored in `~/.config/psptool/`.

## Command line

```
psptool init game.iso work      # detect the game, make a project
psptool unpack work             # ISO files -> work/files
psptool texts work              # strings -> work/texts/NNNN.json
psptool ref work other.iso      # reference text from another version
psptool font work               # new letters into the game font
psptool pack work out.iso       # changes + translation -> new ISO
psptool info work               # what changed
psptool ui work                 # the web UI, http://127.0.0.1:8765
```

## Layout

- `psptool/core`: ISO 9660, PARAM.SFO, projects, plugin registry, OCR,
  upscalers, LLM, remote access.
- `psptool/plugins/<tech>`: formats, e.g. `sony` (GIM, PSMF movies, ELF
  patches), `racjin` (CFC archives, LZ, containers, string tables).
- `psptool/games/<game>`: game plugins that wire formats together, with
  notes on their game.
- `psptool/ui`: the interface; its screens depend on the plugin's
  `features`.
- `psptool/app.py`, `packaging/`: the desktop app.

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT, see LICENSE. Release builds also carry ffmpeg (LGPL/GPL, from
imageio-ffmpeg) and PT Sans (SIL Open Font License); the upscalers are
downloaded from their own releases (MIT/BSD).
