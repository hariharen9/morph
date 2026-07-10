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
    return subprocess.run(cmd, capture_output=True, text=True)


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
    for engine in candidates:
        result = _run_pandoc(input_path, output_path, src_fmt=src_fmt, dst_fmt=dst_fmt,
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
