"""
converters/ebooks.py — ebook family (epub/mobi/azw3), via calibre's
ebook-convert. epub -> pdf/docx/html/etc already exist through pandoc
(documents.py); this file fills in the ebook-reader-specific formats pandoc
doesn't understand, so mobi and azw3 join the graph and can reach everything
epub can reach, transitively, for free.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..registry import ConversionResult, register

FORMATS = ["epub", "mobi", "azw3"]


def _ebook_convert(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ebook-convert", str(input_path), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-8:] or result.stdout.strip().splitlines()[-8:])
        raise RuntimeError(f"ebook-convert failed:\n{tail}")
    return ConversionResult(output=output_path)


for _src in FORMATS:
    for _dst in FORMATS:
        if _dst == _src:
            continue
        register(
            _src, _dst, backend="calibre", requires_binary="ebook-convert", family="ebook",
            description=f"{_src} → {_dst} (calibre)",
        )(_ebook_convert)
