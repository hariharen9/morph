"""
converters/documents.py — document family, powered by pandoc.

Pandoc already handles most-to-most conversion natively in a single command
(pandoc understands both the source and target format directly), so instead
of writing one function per format pair we generate every valid (src, dst)
edge from one shared FORMATS table and one shared _pandoc_convert() function.

PDF is output-only: pandoc can't reliably *read* PDFs back into structured
text, so "pdf" only ever appears as a destination here.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

# format id -> (pandoc reader name or None if input unsupported, pandoc writer name, default extension)
FORMATS: dict[str, dict] = {
    "md":     {"read": "markdown",  "write": "markdown", "ext": "md"},
    "html":   {"read": "html",      "write": "html",     "ext": "html"},
    "docx":   {"read": "docx",      "write": "docx",     "ext": "docx"},
    "odt":    {"read": "odt",       "write": "odt",      "ext": "odt"},
    "rtf":    {"read": "rtf",       "write": "rtf",      "ext": "rtf"},
    "epub":   {"read": "epub",      "write": "epub",     "ext": "epub"},
    "latex":  {"read": "latex",     "write": "latex",    "ext": "tex"},
    "rst":    {"read": "rst",       "write": "rst",      "ext": "rst"},
    "txt":    {"read": "markdown",  "write": "plain",    "ext": "txt"},
    "pdf":    {"read": None,        "write": "pdf",      "ext": "pdf"},
    "ipynb":  {"read": "ipynb",     "write": "ipynb",    "ext": "ipynb"},
    "pptx":   {"read": "pptx",      "write": "pptx",     "ext": "pptx"},
    "adoc":   {"read": "asciidoc",  "write": "asciidoc", "ext": "adoc"},
    "org":    {"read": "org",       "write": "org",      "ext": "org"},
    "opml":   {"read": "opml",      "write": "opml",     "ext": "opml"},
    "man":    {"read": "man",       "write": "man",      "ext": "man"},
}

# tried in order; first one found on PATH is used
_PDF_ENGINES = ["xelatex", "pdflatex", "wkhtmltopdf", "weasyprint", "tectonic"]


def _available_pdf_engines() -> list[str]:
    """All PDF engines that are actually on PATH, in preference order.

    Being on PATH doesn't guarantee an engine works (e.g. a LaTeX install
    missing packages like lmodern.sty still puts xelatex on PATH but fails
    at render time) — see _pandoc_convert's fallback loop for how that's
    handled.
    """
    return [e for e in _PDF_ENGINES if shutil.which(e)]


def _run_pandoc(input_path: Path, output_path: Path, *, src_fmt: str, dst_fmt: str,
                 dst: str, engine: Optional[str], extra_args: Optional[list[str]]) -> subprocess.CompletedProcess:
    cmd = ["pandoc", str(input_path), "-f", src_fmt, "-t", dst_fmt, "-o", str(output_path)]
    if dst not in ("pdf", "txt"):
        cmd.append("--standalone")
    if engine:
        cmd += ["--pdf-engine", engine]
    if extra_args:
        cmd += extra_args
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _preprocess_svgs(input_path: Path, tmpdir: Path, src: str) -> Path:
    if src not in ("md", "html", "txt"):
        return input_path

    try:
        content = input_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return input_path

    import re
    import hashlib
    import urllib.request

    try:
        import cairosvg
        # Trigger DLL loading immediately to verify if C libraries are functional
        cairosvg.svg2pdf(bytestring=b"<svg></svg>")
        has_cairo = True
    except Exception:
        has_cairo = False

    converted_cache: dict[str, Path] = {}
    modified = False

    def get_converted_pdf(img_src: str) -> Optional[str]:
        if not has_cairo:
            return None

        if img_src in converted_cache:
            return converted_cache[img_src].as_posix()

        # Generate a stable filename based on the hash of the image source
        src_hash = hashlib.md5(img_src.encode("utf-8")).hexdigest()
        pdf_path = tmpdir / f"svg_img_{src_hash}.pdf"

        try:
            is_url = img_src.startswith(("http://", "https://"))
            if is_url:
                req = urllib.request.Request(
                    img_src,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antigravity/1.0'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    svg_bytes = response.read()
                cairosvg.svg2pdf(bytestring=svg_bytes, write_to=str(pdf_path))
            else:
                # Local file: resolve relative to input_path's parent directory
                local_path = (input_path.parent / img_src).resolve()
                if not local_path.exists():
                    # Try directly as absolute or relative path
                    local_path = Path(img_src).resolve()
                if local_path.exists():
                    cairosvg.svg2pdf(url=str(local_path), write_to=str(pdf_path))
                else:
                    return None

            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                converted_cache[img_src] = pdf_path
                return pdf_path.as_posix()
        except Exception:
            pass

        return None

    # Replace markdown images: ![alt](img.svg)
    def md_repl(match):
        nonlocal modified
        prefix, img_src, suffix = match.groups()
        pdf_url = get_converted_pdf(img_src)
        if pdf_url:
            modified = True
            return f"{prefix}{pdf_url}{suffix}"
        else:
            # Convert image inclusion to a standard hyperlink to avoid LaTeX error
            modified = True
            # prefix is like '![alt]('
            link_prefix = prefix.lstrip("!")
            return f"{link_prefix}{img_src}{suffix}"

    md_pattern = re.compile(r'(!\[.*?\]\()([^)]*?\.svg(?:[?#][^)]*)?)(\))', re.IGNORECASE)
    content = md_pattern.sub(md_repl, content)

    # Replace HTML images: <img src="img.svg" ...>
    def html_repl(match):
        nonlocal modified
        prefix, img_src, suffix = match.groups()
        pdf_url = get_converted_pdf(img_src)
        if pdf_url:
            modified = True
            return f"{prefix}{pdf_url}{suffix}"
        else:
            modified = True
            return f'<a href="{img_src}">[SVG Image]</a>'

    html_pattern = re.compile(r'(<img\s+[^>]*src=["\'])([^"\']+\.svg(?:[?#][^"\']*)?)(["\'])', re.IGNORECASE)
    content = html_pattern.sub(html_repl, content)

    if modified:
        temp_input = tmpdir / f"preprocessed_{input_path.name}"
        temp_input.write_text(content, encoding="utf-8")
        return temp_input

    return input_path


def _pandoc_convert(input_path: Path, output_path: Path, *, src: str, dst: str,
                     pdf_engine: Optional[str] = None, extra_args: Optional[list[str]] = None,
                     **_options) -> ConversionResult:
    src_fmt = FORMATS[src]["read"]
    dst_fmt = FORMATS[dst]["write"]

    if dst != "pdf":
        result = _run_pandoc(input_path, output_path, src_fmt=src_fmt, dst_fmt=dst_fmt,
                              dst=dst, engine=None, extra_args=extra_args)
        if result.returncode != 0:
            raise RuntimeError(f"pandoc failed:\n{result.stderr.strip()}")
        return ConversionResult(output=output_path)

    # PDF: being on PATH doesn't mean an engine actually works (e.g. a LaTeX
    # install missing lmodern.sty still resolves xelatex on PATH but fails at
    # render time), so if the user didn't force one, try every available
    # engine in preference order and only give up once they've all failed.
    candidates = [pdf_engine] if pdf_engine else _available_pdf_engines()
    if not candidates:
        raise RuntimeError(
            "No PDF engine found. Install one of: xelatex, pdflatex, wkhtmltopdf, "
            "weasyprint, tectonic (morph can install wkhtmltopdf for you)."
        )

    errors: list[str] = []
    import tempfile
    with tempfile.TemporaryDirectory() as pdftmp:
        preprocessed_input = _preprocess_svgs(input_path, Path(pdftmp), src)
        for engine in candidates:
            result = _run_pandoc(preprocessed_input, output_path, src_fmt=src_fmt, dst_fmt=dst_fmt,
                                  dst=dst, engine=engine, extra_args=extra_args)
            if result.returncode == 0:
                return ConversionResult(output=output_path, pages=_count_pdf_pages(output_path),
                                         extra={"pdf_engine": engine})
            errors.append(f"  {engine}: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'failed'}")

    raise RuntimeError(
        f"All available PDF engines failed ({', '.join(candidates)}):\n" + "\n".join(errors)
    )


def _count_pdf_pages(pdf_path: Path) -> Optional[int]:
    try:
        raw = pdf_path.read_bytes()
        return raw.count(b"/Type/Page") or raw.count(b"/Type /Page") or None
    except Exception:
        return None


def _make_converter(src: str, dst: str):
    def _convert(input_path: Path, output_path: Path, **options) -> ConversionResult:
        return _pandoc_convert(input_path, output_path, src=src, dst=dst, **options)
    _convert.__name__ = f"convert_{src}_to_{dst}"
    return _convert


_PDF_OPTIONS = [
    OptionSpec("pdf_engine", ("--pdf-engine",),
               "Force a specific PDF engine (xelatex, pdflatex, wkhtmltopdf, weasyprint, tectonic). "
               "Default: try each available one until one works."),
]

# ── register every valid pandoc pair ────────────────────────────────────────
for _src, _src_info in FORMATS.items():
    if _src_info["read"] is None:
        continue  # pdf: input not supported
    for _dst, _dst_info in FORMATS.items():
        if _dst == _src:
            continue
        register(
            _src, _dst,
            backend="pandoc",
            requires_binary="pandoc",
            family="document",
            description=f"{_src} → {_dst} (pandoc)",
            lossy=(_dst in ("txt", "pdf")),  # plain text and pdf drop structure/aren't re-editable
            options=_PDF_OPTIONS if _dst == "pdf" else [],
        )(_make_converter(_src, _dst))
