<div align="center">

# 🦋 MORPH

**The Universal File Converter for the Command Line.**

*One command. No format-specific tools to remember. No cloud upload. No API keys.*
*Convert anything, to anything.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Built with Typer](https://img.shields.io/badge/CLI-Typer-6C47FF.svg)](https://typer.tiangolo.com/)
[![Powered by Rich](https://img.shields.io/badge/output-Rich-8A2BE2.svg)](https://github.com/Textualize/rich)
[![TUI: Textual](https://img.shields.io/badge/TUI-Textual-4B0082.svg)](https://textual.textualize.io/)

```bash
morph report.docx report.pdf
morph data.csv data.xlsx --table-style TableStyleMedium2 --header-bg 2E7D32
morph logo.png logo.svg --mode spline
morph batch '*.mp4' mp3 --workers 4
```

</div>

---

## ⚡ Why `morph` exists

`ffmpeg` converts media. `pandoc` converts documents. `ImageMagick` converts images. Each is an incredible piece of software, but using them together is a nightmare of different flag dialects, mental models, and obscure syntax errors. 

**`morph` doesn't reinvent codecs or file formats — it orchestrates the best tool for each job behind a single, predictable, and beautiful interface.**

Whether you are rendering a 3D `.blend` file to a `.png`, scraping a Wikipedia article into a Markdown file, vectorizing a `.jpg` into an `.svg`, or converting a batch of `.csv` files to `.parquet`, `morph` calculates the route, fetches the dependencies, and executes the job.

## ✨ Features

- **One Universal Verb.** `morph <input> <output>`. That's it. Omit the output, and `morph` acts as a wizard, presenting you with an interactive menu of all possible destination formats.
- **Undo.** Made a mistake? Convert a massive 1,000-file directory by accident? Just type `morph undo` and watch it instantly delete the generated files and revert your history.
- **Smart Multi-Hop Graph Routing.** No direct `csv → yaml` converter? `morph` automatically finds the `csv → json → yaml` route. When crossing wild paradigms (e.g. Markdown → SQLite), `morph` explicitly hints its logic (like `extracts tabular data only`).
- **Contextual Intelligence.** Run `morph data.csv data.xlsx --help` and you'll *only* see flags relevant to that specific pair (like `--table-style` or `--freeze-cols`). Run it on a video file, and you'll see bitrate and framerate controls instead.
- **Output Verification.** Pass the `--verify` flag to calculate and display the exact SHA-256 checksum of the resulting file right alongside the success message.
- **Transparent Remote Downloads.** Pass any `http://` link and `morph` handles the rest. It uses `trafilatura` to scrape web articles into clean Markdown, or `yt-dlp` to natively download high-quality media (`morph <url> --audio`).
- **Batch Processing Engine.** `morph batch '*.mp4' mp3` converts files concurrently with a live progress table, smart skip logic (`--newer-only`, `--skip-existing`), and output structure mirroring.
- **Interactive TUI.** Type `morph` with no arguments to launch a stunning, keyboard-driven Textual UI. Navigate your filesystem, preview conversion options, and watch live progress bars without touching your mouse.
- **Automated Dependency Management.** Missing `ffmpeg` or `pandoc`? `morph` detects your OS and package manager (brew/apt/winget/etc.), shows you the exact install command, and asks before running it. Massive dependencies (like 3D rendering engines) are cleanly isolated as optional extras!
- **Pluggable Architecture.** Drop a Python script in `morph/converters/`, add a `@register` decorator, and it's instantly live in the routing graph.
- **Local-First & Private.** No cloud uploads. No API keys. Everything runs on your machine.

---

## 📦 Installation

`morph` is natively distributed across all major operating systems. You do not need Python installed to use the standalone binaries!

### Windows
```powershell
# via Winget (Recommended)
winget install hariharen.morph

# via Scoop
scoop bucket add morph https://github.com/hariharen9/scoop-bucket.git
scoop install morph
```

### macOS & Linux
```bash
# via Homebrew
brew tap hariharen9/homebrew-tap
brew install morph
```

### Python Ecosystem (PyPI)
If you prefer managing via `pip` (or `pipx`), install it globally:
```bash
pipx install morphconv
```

### Development (Source)
```bash
git clone https://github.com/hariharen9/morph.git
cd morph
pip install -e .
```

`morph` relies on native Python libraries for data, web, and archives. For massive specialized packages, `morph` uses optional extras to keep your base installation blazing fast. If you need them, simply install them:
```bash
pip install -e ".[3d]"   # Installs bpy (Blender) for 3D conversions
pip install -e ".[web]"  # Installs crawl4ai and playwright for heavy JS rendering
```

For domain-specific external binaries (e.g., `ffmpeg`, `pandoc`), you don't need to install these upfront — `morph` will intelligently prompt you to install them the first time they are needed.

To see your current system dependencies at any time:
```bash
morph deps
```

---

## 🚀 Quickstart & Real-World Examples

### 📊 Data Processing
Switch between analytical formats effortlessly.

```bash
morph data.csv data.xlsx
morph data.json data.yaml
morph database.sqlite data.csv
```

### 📄 Documents & Ebooks
```bash
morph notes.md notes.docx
morph report.docx report.pdf
morph book.epub book.mobi
```

### 🖼️ Images & Vectorization
Raster conversions, plus advanced raster-to-vector tracing.

```bash
# Standard image processing
morph photo.png photo.webp --quality 80 --resize 1200x
morph icon.png icon.ico

# Raster to Vector (via vtracer)
morph logo.png logo.svg --mode spline --hierarchical stacked
```

### 🎬 Audio & Video (via `ffmpeg`)
Media manipulation with real-time progress bars parsed directly from ffmpeg.

```bash
morph song.wav song.mp3 --bitrate 192k
morph clip.mp4 clip.gif --fps 10 --width 480
morph clip.mkv clip.mp3  # Extract audio
```

### 🌐 Web & Remote Files
Fetch data directly from the internet and transform it locally in one step. `morph` natively embeds `yt-dlp` to download almost any media from the web.

```bash
# Natively download video from YouTube, Twitter, etc.
morph https://youtube.com/watch?v=... video.mp4

# Extract audio only from a remote video with metadata embedded
morph https://youtube.com/watch?v=... audio.mp3 --audio

# Scrape an article into clean Markdown (via trafilatura)
morph https://en.wikipedia.org/wiki/Graph_theory graph_theory.md

# Download a remote CSV and style it as an Excel workbook natively
morph https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/latest/owid-covid-latest.csv covid.xlsx --table-style TableStyleMedium2

# Scrape a JavaScript-heavy page (requires morphconv[web])
morph https://example.com/dynamic-article doc.pdf --js
```

### 🧊 3D Models & Rendering (Powered by Blender/`bpy`)
Seamlessly convert between 3D formats, or utilize headless rendering to generate images of your models.

```bash
# Format conversion
morph character.fbx character.glb
morph scene.obj scene.blend

# Headless 3D rendering (automatically places lights and cameras)
morph character.gltf character.png
```

---

## 🏎️ Batch Operations

Convert hundreds of files concurrently with a beautiful terminal dashboard.

```bash
# All MP4s to MP3 using 4 parallel workers
morph batch '*.mp4' mp3 --workers 4

# Recursively convert a whole directory and mirror its structure in an output folder
morph batch ./raw_footage/ mp3 --recursive --out-dir ./audio_only/ --mirror

# Skip files that have already been converted
morph batch '*.flac' mp3 --skip-existing
```

During batch conversions, `morph` displays a live status table:

```text
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

---

## 🗂️ Supported Formats

| Domain | Formats | Backend |
|---|---|---|
| **Data** | `csv`, `xlsx`, `json`, `yaml`, `parquet`, `feather`, `ods`, `xml`, `html`, `sqlite` | Native (`pandas` / `openpyxl`) |
| **Documents** | `md`, `html`, `docx`, `odt`, `rtf`, `epub`, `latex`, `rst`, `txt`, `ipynb`, `pptx`, `adoc`, `org`, `opml`, `man`, `pdf`* | `pandoc` |
| **Images (Raster)** | `png`, `jpg/jpeg`, `webp`, `bmp`, `gif`, `tiff`, `ico`, `heic`, `avif`, `icns`, `pdf` | `Pillow` / `cairosvg` |
| **Vectorization** | `png`/`jpg`/etc. → `svg` | `vtracer` |
| **3D Models** | `obj`, `stl`, `fbx`, `gltf`, `glb`, `blend`, `any → png` (Render) | `bpy` (Blender) |
| **Web Extraction** | `url` → `md`, `txt`, `xml`, `html` | `trafilatura` / `crawl4ai` |
| **Audio** | `mp3`, `wav`, `flac`, `ogg`, `aac`, `m4a`, `opus`, `wma` | `ffmpeg` |
| **Video** | `mp4`, `mkv`, `mov`, `webm`, `avi`, `flv`, `wmv`, `mpeg` | `ffmpeg` |
| **Ebooks** | `epub`, `mobi`, `azw3` | `ebook-convert` |
| **Fonts** | `ttf`, `otf`, `woff`, `woff2` | `fontTools` |
| **OCR** | `png`, `jpg`, `webp`, `pdf`, etc. → `txt` | `tesseract` |
| **Archives** | `zip`, `tar`, `tar.gz`, `tar.bz2`, `tar.xz` | Python stdlib |

*\* Note: PDF is an output-only format for documents. Extracting structured text back out of a PDF is handled via the OCR pipeline.*

---

## 🛠️ Architecture & Under the Hood

The magic of `morph` lies in its modular graph architecture.

```text
morph/
├── cli.py                # Command dispatch (run, batch, formats, history, deps)
├── registry.py           # BFS Routing graph & registration logic
├── tui.py                # Textual keyboard-driven TUI
└── converters/
    ├── __init__.py       # Auto-discovers all modules
    ├── documents.py      # pandoc engine
    ├── images.py         # Pillow engine
    ├── models_3d.py      # Blender/bpy engine
    ├── web.py            # trafilatura / crawl4ai engine
    └── vtracer_converter.py  # Raster-to-SVG vectorization
```

### Adding a new conversion is trivial

Drop a file in `morph/converters/` and use the `@register` decorator. No central registry, no CLI parsers to update. 

```python
from pathlib import Path
from ..registry import ConversionResult, OptionSpec, register

@register("foo", "bar", backend="mytool", family="image")
def foo_to_bar(input_path: Path, output_path: Path, **kwargs) -> ConversionResult:
    # Do the conversion...
    return ConversionResult(output=output_path)
```

Because of `morph`'s graph routing, once `foo → bar` is registered, if a path exists from `bar → baz`, `morph` immediately knows how to convert `foo → baz`.

---

## 📜 History & Transparency

Every conversion is automatically logged. You can review your execution history at any time.

```bash
morph history
```

```text
┌──────────┬──────┬──────┬────────────────┬────────┬────────────┐
│ When     │ From │ To   │ File           │ Mode   │ Status     │
├──────────┼──────┼──────┼────────────────┼────────┼────────────┤
│ 2m ago   │ md   │ docx │ README.md      │ single │ ✓ 1.8s     │
│ 1h ago   │ mp4  │ mp3  │ intro.mp4      │ batch  │ ✓ 4.2s     │
└──────────┴──────┴──────┴────────────────┴────────┴────────────┘
```

---

## 🤝 Contributing

PRs are highly encouraged! If you are adding a new conversion, simply add the file in the `converters/` directory.

## ⚖️ License

Released under the [MIT License](LICENSE).
