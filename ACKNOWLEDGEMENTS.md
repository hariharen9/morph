# Acknowledgements

`morph` is built on the shoulders of giants. It does not reinvent file codecs, parsing logic, or rendering engines. Instead, its core value is providing a unified, seamless graph and CLI/TUI over the incredible work of the open-source community.

We would like to acknowledge and thank the maintainers of the following projects, without which `morph` would not be possible.

## Core Interface & Infrastructure
- **[Typer](https://typer.tiangolo.com/) & [Click](https://click.palletsprojects.com/)**: For the powerful, type-hinted command-line argument parsing.
- **[Rich](https://rich.readthedocs.io/) & [Textual](https://textual.textualize.io/)**: For the beautiful, responsive terminal output, progress bars, and the full interactive TUI.
- **[chardet](https://github.com/chardet/chardet)** & **[python-dateutil](https://github.com/dateutil/dateutil)**: For robust encoding detection and date parsing.

## Data & Tabular Formats
- **[pandas](https://pandas.pydata.org/)**: The heavy lifter for all tabular data routing and conversion.
- **[openpyxl](https://openpyxl.readthedocs.io/)**, **[xlsxwriter](https://xlsxwriter.readthedocs.io/)**, **[xlrd](https://xlrd.readthedocs.io/)**: For comprehensive reading and writing of Excel formats.
- **[pyarrow](https://arrow.apache.org/)**: For lightning-fast Parquet and Feather serialization.
- **[odfpy](https://github.com/eea/odfpy)**: For OpenDocument Spreadsheet (.ods) support.
- **[SQLAlchemy](https://www.sqlalchemy.org/)**: For seamless SQLite database ingestion and extraction.
- **[PyYAML](https://pyyaml.org/)** & **[tomlkit](https://github.com/sdispater/tomlkit)**: For structural configuration formats (with tomlkit specifically preserving comments and ordering).
- **[lxml](https://lxml.de/)**: For high-performance XML parsing.

## Images & Photos
- **[Pillow (PIL)](https://python-pillow.org/)**: The standard for raster image manipulation, resizing, and format conversion.
- **[pillow-heif](https://github.com/bigcat88/pillow_heif)** & **[pillow-avif-plugin](https://github.com/fdintino/pillow-avif-plugin)**: For extending Pillow with modern, highly compressed web image formats.
- **[cairosvg](https://cairosvg.org/)**: For rasterizing SVG vector graphics into PNGs/PDFs.
- **[vtracer](https://github.com/Ogeon/vtracer)**: For powerful, rust-backed raster-to-vector (SVG) tracing.
- **[rawpy](https://letmaik.github.io/rawpy/) / LibRaw**: For demosaicing and processing Camera RAW files (CR2, NEF, ARW, DNG, etc.).

## Documents, PDF & OCR
- **[pymupdf (fitz)](https://pymupdf.readthedocs.io/)**: For blazing-fast, accurate text, layout, and image extraction from digital PDFs.
- **[pdfplumber](https://github.com/jsvine/pdfplumber)**: For surgical table and structured data extraction from PDFs.
- **[pdf2docx](https://github.com/dothinking/pdf2docx)**: For layout-preserving conversion from PDF back to editable Word documents.
- **[img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf)**: For embedding images into PDF containers with zero transcoding or quality loss.
- **[WeasyPrint](https://weasyprint.org/)**: For faithful, browser-grade rendering of HTML and modern CSS directly to PDF.
- **[pytesseract](https://github.com/madmaze/pytesseract) / Tesseract OCR**: For extracting text from scanned documents and images.
- **[nbconvert](https://nbconvert.readthedocs.io/)**: For executing and accurately rendering Jupyter Notebooks (.ipynb) to HTML, PDF, and scripts.

## Web & Extraction
- **[trafilatura](https://trafilatura.readthedocs.io/)**: For incredibly accurate extraction of main article content from web pages, stripping out boilerplate and ads.
- **[markdownify](https://github.com/matthewwithanm/python-markdownify)**: For structured HTML-to-Markdown conversion that preserves tables and documentation formats.
- **[crawl4ai](https://crawl4ai.com/)** & **[Playwright](https://playwright.dev/)**: (Optional) For spinning up headless Chromium browsers to render JavaScript-heavy single-page applications before extraction.

## Media, Archives & Specialized Tools
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: For native, high-quality media extraction from thousands of video hosting sites.
- **[pysubs2](https://github.com/tkarabela/pysubs2)**: For timing and style-preserving conversion between subtitle formats (SRT, VTT, ASS, etc.).
- **[py7zr](https://github.com/miurahr/py7zr)** & **[rarfile](https://github.com/markokr/rarfile)**: For robust 7-Zip (read/write) and RAR (extract) archive support.
- **[fonttools](https://fonttools.readthedocs.io/)**: For parsing and converting between web and desktop font formats (TTF, OTF, WOFF).
- **[qrcode](https://github.com/lincolnloop/python-qrcode)** & **[pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar) / ZBar**: For generating and decoding QR codes and barcodes.
- **[bpy (Blender)](https://pypi.org/project/bpy/)**: (Optional) For headless 3D model conversion and scene rendering.

## External Binaries (Automated via Morph)
`morph` orchestrates these external tools when available or automatically installs them on demand:
- **[Pandoc](https://pandoc.org/)**: The universal document converter (handles Markdown, DOCX, LaTeX, EPUB, and more).
- **[FFmpeg](https://ffmpeg.org/)**: The industry standard for audio and video multiplexing, transcoding, and filtering.
- **[LibreOffice (soffice)](https://www.libreoffice.org/)**: For headless conversion of legacy binary office formats (.doc, .xls, .ppt).
- **[Calibre (ebook-convert)](https://calibre-ebook.com/)**: For DRM-free E-book format conversions.
- **LaTeX (XeLaTeX) / wkhtmltopdf**: Used by Pandoc as intermediate rendering engines for document-to-PDF paths.
