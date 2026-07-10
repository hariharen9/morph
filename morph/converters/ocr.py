"""
converters/ocr.py — OCR extraction from images via pytesseract (Tesseract).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image

from ..registry import ConversionResult, OptionSpec, register
from .images import FORMATS as IMAGE_FORMATS

_OCR_OPTIONS = [
    OptionSpec("lang", ("-l", "--lang"), "Language code(s) for OCR, e.g. 'eng', 'eng+fra'. Default: 'eng'."),
    OptionSpec("psm", ("--psm",), "Page Segmentation Mode (0-13). Default: 3 (Fully automatic).", type=int),
]

def _extract_text(input_path: Path, output_path: Path, *, lang: Optional[str] = None, psm: Optional[int] = None, **_options) -> ConversionResult:
    try:
        img = Image.open(input_path)
    except Exception as e:
        raise RuntimeError(f"Failed to open image for OCR: {e}")

    # Build config string
    config = ""
    if psm is not None:
        config += f"--psm {psm} "

    # Run OCR
    try:
        text = pytesseract.image_to_string(img, lang=lang, config=config.strip())
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError("tesseract executable not found. Please install Tesseract OCR and ensure it is on your PATH.")
    except Exception as e:
        raise RuntimeError(f"OCR failed: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    
    return ConversionResult(output=output_path)

# Register from all valid image inputs to txt
for _src in IMAGE_FORMATS:
    register(
        _src, "txt", backend="tesseract", requires_binary="tesseract", family="ocr",
        description=f"{_src} → txt (OCR)", lossy=True, options=_OCR_OPTIONS
    )(_extract_text)
