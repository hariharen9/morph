<div align="center">

# morph

**Convert anything to anything, from the CLI.**

One command. No format-specific tools to remember. No cloud upload. No API keys.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Built with Typer](https://img.shields.io/badge/CLI-Typer-6C47FF.svg)](https://typer.tiangolo.com/)
[![Powered by Rich](https://img.shields.io/badge/output-Rich-8A2BE2.svg)](https://github.com/Textualize/rich)
[![TUI: Textual](https://img.shields.io/badge/TUI-Textual-4B0082.svg)](https://textual.textualize.io/)

```
morph report.docx report.pdf
morph data.csv data.xlsx --table-style TableStyleMedium2 --header-bg 2E7D32
morph clip.mp4 clip.gif --fps 10 --width 480
morph bundle.zip bundle.tar.gz
```

</div>

---

## Why morph exists

`ffmpeg` converts media. `pandoc` converts documents. `ImageMagick` converts images.
Each is excellent at its one job and painful to use next to the others — different
flag dialects, different mental models, different install stories. Nobody had wired
them into **one coherent tool with one grammar and a genuinely good CLI/TUI**.

morph doesn't reinvent codecs or file formats — it orchestrates the best tool for
each job (ffmpeg, pandoc, Pillow, or plain Python) behind a single, predictable
interface, and handles the annoying parts for you: detecting what's missing,
telling you exactly what it'll install and asking first, and routing through
intermediate formats automatically when there's no direct converter.

## Features

- 🔀 **One verb.** `morph <input> <output>` — not `morph convert`. morph *is* the verb.
- 🧭 **Smart multi-hop routing.** No direct `csv → yaml` converter? morph finds
  `csv → json → yaml` on its own, and tells you it did.
- 🎛️ **Full control, contextually.** `morph data.csv data.xlsx --help` shows exactly
  the ~20 flags relevant to *that* pair — table styles, freeze panes, passwords —
  and nothing from unrelated converters.
- 📦 **Cross-platform dependency management.** Missing `ffmpeg` or `pandoc`? morph
  detects your package manager (brew/apt/dnf/pacman/winget/choco/…), shows you the
  *exact* install command, and never runs it without asking first.
- 🖥️ **A real interactive TUI**, not just flags — point at a file, see every format
  it can reach, pick one.
- 🧩 **Pluggable by design.** Drop a file in `morph/converters/`, call `register()`,
  and it's live — no central registry to edit.
- 🔒 **Local-first.** Nothing leaves your machine. No accounts, no upload, no API keys.

## Installation

```bash
git clone https://github.com/hariharen9/morph.git
cd morph
pip install -e .
```

That's it for **data, image, and archive** conversions — pure Python, zero external
binaries. **Documents** (docx/pdf/html/…) need `pandoc`; **audio/video** need
`ffmpeg`. You don't need to install these up front — morph detects what a given
conversion needs and prompts you the first time you hit it:

```
$ morph slides.docx slides.pdf

╭─────────────── Missing dependency ────────────────╮
│ pandoc converts between document formats (docx,   │
│ md, html, epub, ...), but it isn't installed.      │
│                                                     │
│ morph can install it with:                         │
│   sudo apt install -y pandoc                       │
╰─────────────────────────────────────────────────────╯
Run this now? [Y/n]
```

Check what's available any time:

```bash
morph deps
```

## Quickstart

```bash
# Data
morph data.csv data.xlsx                     # styled workbook: table, banding, autofit
morph data.csv data.json
morph data.csv data.yaml                     # routed through json automatically

# Documents (pandoc)
morph notes.md notes.docx
morph report.docx report.pdf                 # auto-picks a working PDF engine
morph book.epub book.html

# Images (Pillow)
morph photo.png photo.webp --quality 80 --resize 1200x
morph icon.png icon.ico                      # multi-resolution ICO

# Audio / video (ffmpeg)
morph song.wav song.mp3 --bitrate 192k
morph clip.mov clip.mp4 --resolution 1280x720 --fps 30
morph clip.mp4 clip.mp3                      # extract the audio track
morph clip.mp4 clip.gif --fps 10 --width 480

# Archives
morph project.zip project.tar.gz
```

No args? You get the TUI:

```bash
morph
```

### Every conversion is self-documenting

```bash
$ morph data.csv data.xlsx --help
```
```
╭─ morph — conversion route ─╮
│ csv → xlsx                 │
╰─────────────────────────────╯

Options for this conversion (csv → xlsx):
 -d, --delimiter    Field delimiter. Auto-detected if omitted.
 -e, --encoding     Input encoding. Auto-detected if omitted.
 --table-style      Excel table style name.  (default: TableStyleMedium9)
 --header-bg        Header background hex colour (no #).  (default: 1F3864)
 --freeze-cols      Left-most columns to freeze.
 --password         Password-protect the output sheet.
 ... (20 more)
```

The exact same file pointed at `report.pdf` shows a completely different, much
shorter flag set — because pandoc's PDF pipeline genuinely only has one knob
(`--pdf-engine`) worth exposing.

### See what's reachable before you commit

```bash
$ morph formats mp4
┌────────┬──────────────────┬──────┐
│ Target │ Route            │ Hops │
├────────┼──────────────────┼──────┤
│ mp3    │ mp4 → mp3        │    1 │
│ gif    │ mp4 → gif        │    1 │
│ png    │ mp4 → gif → png  │    2 │   ← grabs a frame, discovered automatically
│ webm   │ mp4 → webm       │    1 │
│ ...    │ ...              │  ... │
└────────┴──────────────────┴──────┘
```

That `mp4 → gif → png` row isn't a hand-written "extract a frame" feature — it
fell out of the video and image domains sharing a format (`gif`) in the graph.
This is the payoff of routing everything through one registry instead of N
separate tools: capabilities compose without anyone writing the composition.

## Supported formats today

| Domain | Formats | Backend |
|---|---|---|
| **Data** | csv, xlsx, json, yaml | native (pandas / openpyxl) |
| **Documents** | md, html, docx, odt, rtf, epub, latex, rst, txt, pdf* | pandoc |
| **Images** | png, jpg/jpeg, webp, bmp, gif, tiff, ico | Pillow |
| **Audio** | mp3, wav, flac, ogg, aac, m4a | ffmpeg |
| **Video** | mp4, mkv, mov, webm, avi (+ → audio, + → gif) | ffmpeg |
| **Archives** | zip, tar, tar.gz, tar.bz2, tar.xz | stdlib |

<sub>*pdf is output-only — pandoc can't reliably parse PDFs back into structured
content, so it never appears as a source format.</sub>

Run `morph formats` for the full live list, or `morph formats <fmt>` to see
everything reachable from a given format, direct or chained.

## Architecture, in brief

```
morph/
├── registry.py          # the graph: register(src, dst, ...) edges + BFS routing
├── deps.py               # cross-platform dependency detection & guarded installer
├── cli.py                # dispatch: "morph x y" → hidden `run` command
├── tui.py                # Textual app, same engine as the CLI
└── converters/
    ├── __init__.py       # auto-discovers every file below — nothing to register by hand
    ├── csv_to_xlsx.py    # self-contained: engine + OptionSpecs + register() in one file
    ├── xlsx_to_csv.py
    ├── csv_json.py
    ├── json_yaml.py
    ├── documents.py      # one generic pandoc engine, many pairs
    ├── images.py         # one generic Pillow engine, many pairs
    ├── audio.py
    ├── video.py
    └── archives.py
```

Every converter is a function `(input_path, output_path, **options) -> ConversionResult`,
registered once with `@register(src, dst, backend=..., options=[...])`. The CLI
never hardcodes a flag — it asks the registry which `OptionSpec`s apply to the
route it just resolved and builds the parser from that, which is also what makes
per-pair `--help` possible.

### Adding a new conversion

Drop a file in `morph/converters/`:

```python
# morph/converters/svg_png.py
from pathlib import Path
from ..registry import ConversionResult, OptionSpec, register

OPTIONS = [
    OptionSpec("width", ("--width",), "Output width in pixels.", type=int),
]

@register("svg", "png", backend="cairosvg", requires_binary=None,
          family="image", options=OPTIONS)
def svg_to_png(input_path: Path, output_path: Path, *, width=None, **_options) -> ConversionResult:
    import cairosvg
    cairosvg.svg2png(url=str(input_path), write_to=str(output_path), output_width=width)
    return ConversionResult(output=output_path)
```

That's the whole integration. No imports to add elsewhere, no CLI wiring —
`converters/__init__.py` picks it up automatically, `morph x.svg y.png` works
immediately, and it slots into the routing graph for free (so e.g. anything
that could already reach `.svg` can now reach `.png` too, if that helps).

## Roadmap

- [ ] Fonts (ttf/otf/woff/woff2) via fontTools
- [ ] Ebooks (epub/mobi/azw3) via Calibre's `ebook-convert`
- [ ] HEIC/AVIF image support (pillow-heif / pillow-avif)
- [ ] Per-pair codec tuning for audio/video (currently relies on ffmpeg's
      container-inferred defaults, which are correct but not always optimal)
- [ ] `morph batch` for glob-based multi-file jobs

## Contributing

Issues and PRs welcome. If you're adding a converter, see
["Adding a new conversion"](#adding-a-new-conversion) above — that's the entire
contract. Please include a quick sanity check (a real input → real output,
not just "it imports") in your PR description.

## License

[MIT](LICENSE)
