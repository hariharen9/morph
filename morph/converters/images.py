"""
converters/images.py — raster image family, powered by Pillow.

Same pattern as documents.py: one shared FORMATS table + one shared convert
function, looped to register every (src, dst) pair. Pure Python, no external
binary required, so this domain works the moment `pip install morph` finishes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
import pillow_heif
import pillow_avif

pillow_heif.register_heif_opener()

from ..registry import ConversionResult, OptionSpec, register

# format id -> Pillow format name
FORMATS: dict[str, str] = {
    "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP",
    "bmp": "BMP", "gif": "GIF", "tiff": "TIFF", "ico": "ICO",
    "heic": "HEIF", "avif": "AVIF", "pdf": "PDF", "icns": "ICNS",
}

# formats whose writer supports a quality setting
_QUALITY_FORMATS = {"JPEG", "WEBP", "HEIF", "AVIF"}

# formats that can't store an alpha channel — need RGB flattening first
_NO_ALPHA_FORMATS = {"JPEG", "BMP", "PDF"}


def _parse_resize(spec: str, size: tuple[int, int]) -> tuple[int, int]:
    """'800x600' -> (800, 600); '800x' or 'x600' keeps the other dimension
    proportional; a bare '50%' scales both dimensions."""
    w, h = size
    if spec.endswith("%"):
        pct = float(spec[:-1]) / 100
        return (max(1, round(w * pct)), max(1, round(h * pct)))
    parts = spec.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid --resize value: {spec!r} (expected WIDTHxHEIGHT, e.g. 800x600)")
    new_w = int(parts[0]) if parts[0] else None
    new_h = int(parts[1]) if parts[1] else None
    if new_w and not new_h:
        new_h = round(h * (new_w / w))
    elif new_h and not new_w:
        new_w = round(w * (new_h / h))
    if not new_w or not new_h:
        raise ValueError(f"Invalid --resize value: {spec!r}")
    return (new_w, new_h)


def _image_convert(input_path: Path, output_path: Path, *, dst_pil: str,
                    quality: Optional[int] = None, resize: Optional[str] = None,
                    **_options) -> ConversionResult:
    img = Image.open(input_path)

    if resize:
        img = img.resize(_parse_resize(resize, img.size))

    if dst_pil in _NO_ALPHA_FORMATS and img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif dst_pil == "ICO":
        img = img.convert("RGBA")

    save_kwargs: dict = {}
    if quality is not None and dst_pil in _QUALITY_FORMATS:
        save_kwargs["quality"] = quality
    if dst_pil == "ICO":
        save_kwargs["sizes"] = [(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= max(img.size)] or [(256, 256)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format=dst_pil, **save_kwargs)
    return ConversionResult(output=output_path, extra={"size": img.size})


def _make_converter(dst_pil: str):
    def _convert(input_path: Path, output_path: Path, **options) -> ConversionResult:
        return _image_convert(input_path, output_path, dst_pil=dst_pil, **options)
    return _convert


_OPTIONS_BY_DST = {
    "jpg": [
        OptionSpec("quality", ("--quality",), "Output quality 1-100 (JPEG). Default: Pillow's default (~75).", type=int),
        OptionSpec("resize", ("--resize",), "Resize before saving: '800x600', '800x' (keep ratio), or '50%'."),
    ],
    "jpeg": [
        OptionSpec("quality", ("--quality",), "Output quality 1-100 (JPEG). Default: Pillow's default (~75).", type=int),
        OptionSpec("resize", ("--resize",), "Resize before saving: '800x600', '800x' (keep ratio), or '50%'."),
    ],
    "webp": [
        OptionSpec("quality", ("--quality",), "Output quality 1-100 (WEBP). Default: 80.", type=int, default=80),
        OptionSpec("resize", ("--resize",), "Resize before saving: '800x600', '800x' (keep ratio), or '50%'."),
    ],
}
_DEFAULT_OPTIONS = [
    OptionSpec("resize", ("--resize",), "Resize before saving: '800x600', '800x' (keep ratio), or '50%'."),
]

for _src in FORMATS:
    if _src == "pdf":
        continue  # Pillow can save to PDF, but cannot rasterize arbitrary PDFs
    for _dst, _dst_pil in FORMATS.items():
        if _dst == _src:
            continue
        register(
            _src, _dst,
            backend="pillow",
            family="image",
            description=f"{_src} → {_dst} (Pillow)",
            lossy=(_dst_pil in _QUALITY_FORMATS or _dst == "ico"),
            options=_OPTIONS_BY_DST.get(_dst, _DEFAULT_OPTIONS),
        )(_make_converter(_dst_pil))


# ── img2pdf: lossless image → PDF (overwrites Pillow's re-encoding routes) ──
#
# Pillow's PDF writer transcodes — a JPEG saved to PDF becomes a re-encoded
# JPEG, losing quality. img2pdf embeds the original image bytes directly,
# producing smaller files with zero quality loss. Supported source types:
#   JPEG/JPG  — embedded as-is (best case)
#   PNG       — embedded as-is if no alpha; RGB-flattened then embedded
#   TIFF      — embedded as-is
#   WEBP/BMP/GIF/etc. — converted to PNG internally by img2pdf, then embedded
#
# img2pdf does NOT support alpha channels, so we pre-flatten RGBA sources.

def _require_img2pdf():
    try:
        import img2pdf
        return img2pdf
    except ImportError:
        raise RuntimeError(
            "img2pdf is required for lossless image-to-PDF conversion.\n"
            "Install it with: pip install img2pdf"
        )


def _img_to_pdf(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    """Embed image bytes directly into PDF without transcoding."""
    img2pdf = _require_img2pdf()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for alpha channel — img2pdf requires opaque images
    with Image.open(input_path) as img:
        has_alpha = img.mode in ("RGBA", "LA", "P") and "transparency" in img.info or img.mode in ("RGBA", "LA")

    if has_alpha:
        # Flatten alpha onto white background, save to temp PNG, then embed
        import tempfile
        with Image.open(input_path) as img:
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                background.save(tmp_path, format="PNG")
        try:
            pdf_bytes = img2pdf.convert(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        pdf_bytes = img2pdf.convert(str(input_path))

    output_path.write_bytes(pdf_bytes)
    return ConversionResult(output=output_path)


# Formats img2pdf handles (all raster sources except pdf itself)
_IMG2PDF_SRCS = [s for s in FORMATS if s != "pdf"]

for _src in _IMG2PDF_SRCS:
    register(
        _src, "pdf",
        backend="img2pdf",
        family="image",
        description=f"{_src} -> pdf (lossless, img2pdf)",
        lossy=False,  # img2pdf embeds original bytes — truly lossless
    )(_img_to_pdf)
