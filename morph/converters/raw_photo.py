"""
converters/raw_photo.py — Camera RAW → jpg/png via rawpy.

rawpy (backed by LibRaw) reads virtually every camera manufacturer's
proprietary RAW format: .CR2/.CR3 (Canon), .NEF/.NRW (Nikon),
.ARW/.SRF (Sony), .DNG (Adobe universal), .RAF (Fuji), .ORF (Olympus),
.RW2 (Panasonic), .PEF (Pentax), .SRW (Samsung), and many more.

The output is a half-processed (demosaiced, white-balanced, colour-corrected)
RGB image written with Pillow. Default postprocess parameters mirror
rawpy's "use_camera_wb=True, half_size=False, no_auto_bright=False"
defaults, which give a result very close to what the camera's JPEG engine
would produce.

Requires: rawpy (pip install rawpy)  — wraps LibRaw (C library)
  pip install rawpy
  # LibRaw ships as a wheel on all major platforms; no separate install needed.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

# Every extension LibRaw can open (non-exhaustive — rawpy accepts more)
RAW_FORMATS = [
    "cr2", "cr3",          # Canon
    "nef", "nrw",          # Nikon
    "arw", "srf", "sr2",   # Sony
    "dng",                 # Adobe universal
    "raf",                 # Fujifilm
    "orf",                 # Olympus
    "rw2",                 # Panasonic
    "pef",                 # Pentax
    "srw",                 # Samsung
    "x3f",                 # Sigma
    "3fr",                 # Hasselblad
    "mef",                 # Mamiya
    "mrw",                 # Minolta
    "raw", "rwl",          # Leica
    "erf",                 # Epson
    "kdc", "dcr",          # Kodak
]

OUTPUT_FORMATS = ["jpg", "png", "tiff", "webp"]

OPTIONS = [
    OptionSpec(
        "use_camera_wb", ("--camera-wb",),
        "Use camera white balance (default: True).",
        default=True, action="store_true",
    ),
    OptionSpec(
        "half_size", ("--half-size",),
        "Decode at half resolution (faster, smaller output).",
        default=False, action="store_true",
    ),
    OptionSpec(
        "no_auto_bright", ("--no-auto-bright",),
        "Disable automatic brightness adjustment.",
        default=False, action="store_true",
    ),
    OptionSpec(
        "output_bps", ("--bps",),
        "Bits per sample: 8 or 16. Default: 8.",
        default=8, type=int,
    ),
]


def _require_rawpy():
    try:
        import rawpy
        return rawpy
    except ImportError:
        raise RuntimeError(
            "rawpy is required for Camera RAW conversion.\n"
            "Install it with: pip install rawpy\n"
            "(LibRaw ships bundled in the wheel — no separate C library needed.)"
        )


def _raw_convert(
    input_path: Path,
    output_path: Path,
    *,
    dst_fmt: str,
    use_camera_wb: bool = True,
    half_size: bool = False,
    no_auto_bright: bool = False,
    output_bps: int = 8,
    **_options,
) -> ConversionResult:
    rawpy = _require_rawpy()
    from PIL import Image

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rawpy.imread(str(input_path)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=use_camera_wb,
            half_size=half_size,
            no_auto_bright=no_auto_bright,
            output_bps=output_bps,
        )

    img = Image.fromarray(rgb)

    pil_fmt_map = {
        "jpg": "JPEG", "jpeg": "JPEG",
        "png": "PNG",
        "tiff": "TIFF",
        "webp": "WEBP",
    }
    pil_fmt = pil_fmt_map.get(dst_fmt, dst_fmt.upper())

    # JPEG can't handle 16-bit or alpha
    if pil_fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")

    img.save(output_path, format=pil_fmt)
    return ConversionResult(output=output_path, extra={"size": img.size})


def _make_converter(dst_fmt: str):
    def _convert(input_path: Path, output_path: Path, **opts) -> ConversionResult:
        return _raw_convert(input_path, output_path, dst_fmt=dst_fmt, **opts)
    _convert.__name__ = f"raw_to_{dst_fmt}"
    return _convert


# Register every raw_format -> output_format pair
for _raw in RAW_FORMATS:
    for _dst in OUTPUT_FORMATS:
        register(
            _raw, _dst,
            backend="rawpy",
            family="image",
            description=f"{_raw} -> {_dst} (Camera RAW via rawpy/LibRaw)",
            lossy=(_dst in ("jpg", "webp")),
            options=OPTIONS,
        )(_make_converter(_dst))
