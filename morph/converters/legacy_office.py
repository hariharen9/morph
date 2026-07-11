"""
converters/legacy_office.py — legacy binary Office formats via LibreOffice headless.

Pandoc cannot read the old binary Office formats (.doc, .xls, .ppt). LibreOffice
headless (soffice) can. This module registers edges from each legacy format into
its modern Open XML equivalent, after which morph's BFS graph handles everything
else automatically:

    doc  → docx  (soffice)   then docx → md/html/pdf/epub/... (pandoc)
    xls  → xlsx  (soffice)   then xlsx → csv/json/parquet/...  (pandas)
    ppt  → pptx  (soffice)   then pptx → pdf/...               (pandoc)

soffice --convert-to writes the output file into a directory (not a specific
path), using the original stem + the new extension. We tell it to use a
temporary directory and then move the result to output_path.

Requires: LibreOffice installed and `soffice` on PATH.
  • Linux/macOS:  sudo apt install libreoffice  / brew install --cask libreoffice
  • Windows:      winget install --id TheDocumentFoundation.LibreOffice
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import deps
from ..registry import ConversionResult, register

# ── soffice target format tokens ──────────────────────────────────────────
# Maps the soffice --convert-to token to the output file extension it produces.
# soffice always names the output as <input_stem>.<ext>.
_SOFFICE_TARGET: dict[str, str] = {
    "docx": "docx",
    "xlsx": "xlsx",
    "pptx": "pptx",
    "pdf":  "pdf",
    "csv":  "csv",
    "txt":  "txt",
    "html": "html",
    "odt":  "odt",
    "ods":  "ods",
    "odp":  "odp",
}


def _soffice_convert(
    input_path: Path,
    output_path: Path,
    *,
    soffice_target: str,
    **_options,
) -> ConversionResult:
    """
    Run:  soffice --headless --convert-to <soffice_target> --outdir <tmpdir> <input>
    Then move the produced file to output_path.
    """
    import os

    if not deps.is_installed("soffice"):
        raise RuntimeError(
            "LibreOffice (soffice) is required to convert legacy Office files.\n"
            "Install it with your package manager, or let morph install it:\n"
            "  morph deps install soffice"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "soffice", "--headless",
            "--convert-to", soffice_target,
            "--outdir", tmpdir,
            str(input_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"soffice conversion failed:\n{result.stderr.strip() or result.stdout.strip()}"
            )

        ext = _SOFFICE_TARGET.get(soffice_target, soffice_target)
        produced = Path(tmpdir) / f"{input_path.stem}.{ext}"

        if not produced.exists():
            # soffice sometimes appends the filter name — find anything with the right ext
            candidates = list(Path(tmpdir).glob(f"*.{ext}"))
            if not candidates:
                raise RuntimeError(
                    f"soffice ran successfully but produced no .{ext} file in {tmpdir}.\n"
                    f"tmpdir contents: {list(Path(tmpdir).iterdir())}"
                )
            produced = candidates[0]

        shutil.move(str(produced), str(output_path))

    return ConversionResult(output=output_path)


# ── factory ───────────────────────────────────────────────────────────────

def _make_converter(soffice_target: str):
    def _convert(input_path: Path, output_path: Path, **options) -> ConversionResult:
        return _soffice_convert(
            input_path, output_path, soffice_target=soffice_target, **options
        )
    _convert.__name__ = f"soffice_to_{soffice_target}"
    return _convert


# ── registration ──────────────────────────────────────────────────────────
#
# Strategy: register each legacy format → its natural modern counterpart.
# The BFS graph then provides the rest for free:
#
#   doc → docx  ──(pandoc)──► md / html / pdf / epub / rst / ...
#   xls → xlsx  ──(pandas)──► csv / json / parquet / ods / ...
#   ppt → pptx  ──(pandoc)──► pdf / ...
#
# We also add a few high-value direct routes (→ pdf, → txt) to avoid a
# two-hop conversion for the most common use-cases, at the cost of going
# through soffice's own renderer which is often higher quality for those.

_LEGACY_FORMATS: list[tuple[str, str, str, bool]] = [
    # (src, soffice_target_token, description_suffix, lossy)
    # ── .doc ──────────────────────────────────────────────────────────────
    ("doc",  "docx", "modern Word document",      False),
    ("doc",  "odt",  "ODF text document",         False),
    ("doc",  "pdf",  "PDF (via LibreOffice)",      True),
    ("doc",  "txt",  "plain text",                 True),
    ("doc",  "html", "HTML",                       False),
    # ── .xls ──────────────────────────────────────────────────────────────
    ("xls",  "xlsx", "modern Excel workbook",     False),
    ("xls",  "ods",  "ODF spreadsheet",           False),
    ("xls",  "csv",  "CSV (first sheet)",          True),
    ("xls",  "pdf",  "PDF (via LibreOffice)",      True),
    # ── .ppt ──────────────────────────────────────────────────────────────
    ("ppt",  "pptx", "modern PowerPoint file",    False),
    ("ppt",  "odp",  "ODF presentation",          False),
    ("ppt",  "pdf",  "PDF (via LibreOffice)",      True),
]

for _src, _target, _desc, _lossy in _LEGACY_FORMATS:
    register(
        _src, _target,
        backend="soffice",
        requires_binary="soffice",
        family="document",
        description=f"{_src} → {_target} ({_desc}, via LibreOffice headless)",
        lossy=_lossy,
    )(_make_converter(_target))
