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
morph batch '*.mp4' mp3 --workers 4
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

- **One verb.** `morph <input> <output>` — not `morph convert`. morph *is* the verb.
- **Smart multi-hop routing.** No direct `csv → yaml` converter? morph finds
  `csv → json → yaml` on its own. By utilizing a Breadth-First Search (BFS) directed graph, morph instantly unlocks thousands of implicit conversions. Currently supporting **66 formats and over 1,000+ multi-hop routes** across data, documents, images, audio, and video!
- **Full control, contextually.** `morph data.csv data.xlsx --help` shows exactly
  the flags relevant to *that* pair — table styles, freeze panes, passwords —
  and nothing from unrelated converters.
- **Batch conversion.** `morph batch '*.mp4' mp3` converts many files in parallel
  with a live Rich progress table, smart output strategies, and a clean summary.
- **Conversion history.** Every conversion is logged to `~/.morph_history.jsonl`.
  `morph history` shows a searchable, filterable table of past jobs.
- **Cross-platform dependency management.** Missing `ffmpeg` or `pandoc`? morph
  detects your package manager (brew/apt/dnf/pacman/winget/choco/…), shows you the
  *exact* install command, and never runs it without asking first.
- **A real interactive TUI**, fully keyboard-driven — type a path (with autocomplete
  dropdown for filesystem suggestions), arrow through formats (options update live),
  and watch a real progress bar while it converts. No mouse needed.
- **Live execution feedback.** ffmpeg hops show a real progress bar driven by
  ffmpeg's own `-progress` stream. Everything else shows a spinner labeled with
  which tool is working (`via pandoc`, `via pillow`, ...).
- **Pluggable by design.** Drop a file in `morph/converters/`, call `register()`,
  and it's live — no central registry to edit.
- **Local-first.** Nothing leaves your machine. No accounts, no upload, no API keys.
- **Global Configuration (`~/.morphrc`).** Generate a fully-commented YAML configuration file containing every single flag for every converter using `morph config`. CLI arguments seamlessly override these base defaults, giving you maximum control.

## Installation

```bash
git clone https://github.com/hariharen9/morph.git
cd morph
pip install -e .
```

That's it for **data, image, and archive** conversions — pure Python, zero external
binaries. **Documents** (docx/pdf/html/…) need `pandoc`; **audio/video** need
`ffmpeg`. You don't need to install these up front — morph detects what a given
conversion needs and prompts you the first time you hit it.

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
morph report.docx report.pdf
morph book.epub book.html

# Images (Pillow + cairosvg)
morph photo.png photo.webp --quality 80 --resize 1200x
morph icon.png icon.ico                      # multi-resolution ICO
morph diagram.svg diagram.png

# Fonts (fontTools)
morph font.ttf font.woff2
morph font.woff font.otf

# Ebooks (Calibre)
morph book.epub book.mobi
morph book.epub book.azw3

# Audio / video (ffmpeg)
morph song.wav song.mp3 --bitrate 192k
morph clip.mov clip.mp4 --resolution 1280x720 --fps 30
morph clip.mp4 clip.mp3                      # extract the audio track
morph clip.mp4 clip.gif --fps 10 --width 480

# Archives
morph project.zip project.tar.gz

# No args — interactive TUI
morph
```

### Batch conversion

Convert many files at once with a live progress display:

```bash
# All MP4s → MP3, 4 parallel workers
morph batch '*.mp4' mp3 --workers 4

# Whole directory, recursive, into a separate output folder
morph batch ./raw/ mp3 --recursive --out-dir ./converted/

# Mirror the input directory structure
morph batch ./raw/ mp3 --recursive --out-dir ./converted/ --mirror

# Custom output name template
morph batch '*.mp4' mp3 --rename '{stem}_audio'
# → myvideo_audio.mp3

# Skip files whose output already exists
morph batch '*.mp4' mp3 --skip-existing

# Only re-convert if input is newer than output (like make)
morph batch '*.mp4' mp3 --newer-only

# Preview what would happen — no conversion
morph batch '*.mp4' mp3 --dry-run

# Multiple patterns at once
morph batch '*.flac' '*.wav' mp3

# Pass converter flags through
morph batch '*.mp4' mp3 --bitrate 192k
```

During conversion, morph shows a live table:

```
╭─ morph batch — 8 files → mp3 ─────────────────────────────────────╮
│  Status          File                    Time      Size             │
│  ✓ done          concert_01.flac         0:00:04   8.3MB → 4.1MB   │
│  ✓ done          concert_02.flac         0:00:03   7.9MB → 3.8MB   │
│  ▶ converting…   concert_03.flac         0:00:01                    │
│  · waiting       concert_04.wav                                     │
│                                                                      │
│  Overall  ████████░░░░░░░░  2/8  [0:00:07]                          │
╰──────────────────────────────────────────────────────────────────────╯
```

### Conversion history

Every conversion (single and batch) is automatically logged:

```bash
morph history               # last 20 conversions
morph history -n 50         # last 50
morph history --failed      # only failures
morph history --fmt mp4     # filter by format
morph history --clear       # wipe history
morph history --json        # raw JSONL output (for scripting)
```

```
┌──────────┬──────┬──────┬────────────────┬────────┬────────────┐
│ When     │ From │ To   │ File           │ Mode   │ Status     │
├──────────┼──────┼──────┼────────────────┼────────┼────────────┤
│ 2m ago   │ md   │ docx │ README.md      │ single │ ✓ 1.8s     │
│ 1h ago   │ mp4  │ mp3  │ intro.mp4      │ batch  │ ✓ 4.2s     │
│ yesterday│ csv  │ xlsx │ data.csv       │ single │ ✓ 0.1s     │
└──────────┴──────┴──────┴────────────────┴────────┴────────────┘
```

History is stored at `~/.morph_history.jsonl` — one JSON object per line,
easy to parse with `jq` or Python.

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
 --table-style      Excel table style name.  (default: TableStyleMedium9)
 --header-bg        Header background hex colour (no #).  (default: 1F3864)
 --freeze-cols      Left-most columns to freeze.
 --password         Password-protect the output sheet.
 ... (more)
```

The exact same file pointed at `report.pdf` shows a completely different,
shorter flag set — because pandoc's PDF pipeline genuinely only has one knob
worth exposing.

### See what's reachable

```bash
# Tree view grouped by family — great for discovery
$ morph formats
  morph — 45 formats across 8 families

  * document  (11 formats, via pandoc, 82 direct routes)
  ├── md    → docx epub html latex odt pdf rst rtf txt
  ├── docx  → epub html latex md odt pdf rst rtf txt
  └── ...

  * audio  (6 formats, via ffmpeg, 30 direct routes)
  ├── mp3  → aac flac m4a ogg wav
  └── ...

# Per-format table — see everything reachable from one format
$ morph formats mp4
┌────────┬──────────────────┬──────┐
│ Target │ Route            │ Hops │
├────────┼──────────────────┼──────┤
│ mp3    │ mp4 → mp3        │    1 │
│ gif    │ mp4 → gif        │    1 │
│ webm   │ mp4 → webm       │    1 │
│ ...    │ ...              │  ... │
└────────┴──────────────────┴──────┘
```

## Supported formats

| Domain | Formats | Backend |
|---|---|---|
| **Data** | csv, xlsx, json, yaml, parquet, feather, ods, xml, html, sqlite | native (pandas / openpyxl) |
| **Documents** | md, html, docx, odt, rtf, epub, latex, rst, txt, ipynb, pptx, adoc, org, opml, man, pdf* | pandoc |
| **Images** | png, jpg/jpeg, webp, bmp, gif, tiff, ico, heic, avif, icns, pdf, svg (input only) | Pillow / cairosvg |
| **Fonts** | ttf, otf, woff, woff2 | fontTools |
| **Ebooks** | epub, mobi, azw3 | Calibre (`ebook-convert`) |
| **Audio** | mp3, wav, flac, ogg, aac, m4a, opus, wma | ffmpeg |
| **Video** | mp4, mkv, mov, webm, avi, flv, wmv, mpeg (+ → audio, + → gif/webp, + → srt/vtt) | ffmpeg |
| **OCR** | png, jpg, webp, pdf, etc. → txt | tesseract |
| **Archives** | zip, tar, tar.gz, tar.bz2, tar.xz | stdlib |

<sub>*pdf is output-only — morph doesn't read PDFs back into structured content,
since that's a fundamentally lossier operation than every other conversion here.</sub>

## Architecture

```
morph/
├── cli.py                # dispatch + all subcommands (run, batch, formats, history, deps)
├── registry.py           # the graph: register(src, dst) edges + BFS routing
├── batch.py              # parallel batch engine: ThreadPoolExecutor + Rich Live display
├── history.py            # JSONL log at ~/.morph_history.jsonl
├── deps.py               # cross-platform dep detection & guarded installer
├── progress.py           # Rich progress bars for the CLI
├── ffmpeg_utils.py       # ffmpeg -progress pipe parser for real % tracking
├── tui.py                # Textual keyboard-driven TUI (same engine as CLI)
└── converters/
    ├── __init__.py       # auto-discovers every file below — nothing to register by hand
    ├── csv_to_xlsx.py    # self-contained: engine + OptionSpecs + register() in one file
    ├── xlsx_to_csv.py
    ├── csv_json.py
    ├── json_yaml.py
    ├── documents.py      # one generic pandoc engine, many pairs
    ├── images.py         # one generic Pillow engine, many pairs
    ├── svg.py            # cairosvg for SVG → raster/PDF
    ├── audio.py          # ffmpeg with real progress tracking
    ├── video.py          # ffmpeg, includes → gif + audio extraction
    ├── archives.py
    ├── fonts.py          # fontTools: ttf/otf/woff/woff2
    └── ebooks.py         # Calibre ebook-convert
```

Every converter is a function `(input_path, output_path, **options) -> ConversionResult`,
registered once with `@register(src, dst, backend=..., options=[...])`. The CLI
never hardcodes a flag — it asks the registry which `OptionSpec`s apply to the
route it just resolved and builds the parser from that, which is also what makes
per-pair `--help` possible.

### Adding a new conversion

Drop a file in `morph/converters/`:

```python
# morph/converters/my_converter.py
from pathlib import Path
from ..registry import ConversionResult, OptionSpec, register

OPTIONS = [
    OptionSpec("quality", ("--quality",), "Output quality (1-100).", default=85, type=int),
]

@register("foo", "bar", backend="sometool", family="image", options=OPTIONS)
def foo_to_bar(input_path: Path, output_path: Path, *, quality=85, **_) -> ConversionResult:
    # ... do the conversion ...
    return ConversionResult(output=output_path)
```

That's the whole integration. No imports to add elsewhere, no CLI wiring —
`converters/__init__.py` picks it up automatically, `morph x.foo y.bar` works
immediately, and it slots into the routing graph so anything that could reach
`.foo` can now reach `.bar` too.

## CLI reference

```
morph <input> <output> [OPTIONS]     # convert a single file
morph <input> <output> --help        # show flags for THIS conversion only
morph batch <patterns...> <format>   # batch convert (see morph batch --help)
morph formats                        # tree of all formats by family
morph formats <fmt>                  # everything reachable from <fmt>
morph history                        # recent conversion log
morph deps                           # check / install external tools
morph                                # launch the interactive TUI
```

## Roadmap

- [ ] Per-pair codec tuning for audio/video (currently relies on ffmpeg defaults)
- [ ] HEIC/AVIF image support (pillow-heif / pillow-avif)
- [ ] `~/.morphrc` config file for persistent flag defaults
- [ ] Automated test suite

## Contributing

Issues and PRs welcome. If you're adding a converter, see
["Adding a new conversion"](#adding-a-new-conversion) above — that's the entire
contract. Please include a quick sanity check (a real input → real output,
not just "it imports") in your PR description.

## License

[MIT](LICENSE)
