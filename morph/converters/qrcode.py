"""
converters/qrcode.py — QR code generation and decoding.

Generation: txt/url → png  (via qrcode library)
Decoding:   png/jpg/... → txt  (via pyzbar)

Example:
  morph "https://mysite.com" qr.png          # generate
  morph qr.png decoded.txt                   # decode

Requires:
  qrcode[pil]  — for generation  (pip install "qrcode[pil]")
  pyzbar       — for decoding    (pip install pyzbar)
                 On Linux also:  sudo apt install libzbar0
                 On macOS:       brew install zbar
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

# ── options ───────────────────────────────────────────────────────────────

_GEN_OPTIONS = [
    OptionSpec(
        "error_correction", ("--error-correction",),
        "Error correction level: L (7%), M (15%), Q (25%), H (30%). Default: M.",
        default="M",
    ),
    OptionSpec(
        "box_size", ("--box-size",),
        "Pixels per QR module box. Default: 10.",
        default=10, type=int,
    ),
    OptionSpec(
        "border", ("--border",),
        "Quiet-zone border width in boxes. Default: 4.",
        default=4, type=int,
    ),
    OptionSpec(
        "fill_color", ("--fill-color",),
        "Foreground colour (CSS name or hex). Default: black.",
        default="black",
    ),
    OptionSpec(
        "back_color", ("--back-color",),
        "Background colour (CSS name or hex). Default: white.",
        default="white",
    ),
]


# ── generation ────────────────────────────────────────────────────────────

def _require_qrcode():
    try:
        import qrcode
        return qrcode
    except ImportError:
        raise RuntimeError(
            "qrcode is required for QR code generation.\n"
            'Install it with: pip install "qrcode[pil]"'
        )


def _txt_to_qr(
    input_path: Path,
    output_path: Path,
    *,
    error_correction: str = "M",
    box_size: int = 10,
    border: int = 4,
    fill_color: str = "black",
    back_color: str = "white",
    **_options,
) -> ConversionResult:
    qrcode = _require_qrcode()

    text = input_path.read_text(encoding="utf-8").strip()

    ec_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    ec = ec_map.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)

    qr = qrcode.QRCode(
        error_correction=ec,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return ConversionResult(output=output_path)


# ── decoding ──────────────────────────────────────────────────────────────

def _require_pyzbar():
    try:
        from pyzbar import pyzbar
        return pyzbar
    except ImportError:
        raise RuntimeError(
            "pyzbar is required for QR/barcode decoding.\n"
            "Install it with: pip install pyzbar\n"
            "Linux also needs: sudo apt install libzbar0\n"
            "macOS also needs: brew install zbar"
        )


def _img_to_decoded(
    input_path: Path,
    output_path: Path,
    **_options,
) -> ConversionResult:
    from PIL import Image
    pyzbar = _require_pyzbar()

    img = Image.open(input_path)
    codes = pyzbar.decode(img)

    if not codes:
        raise RuntimeError(
            f"No QR code or barcode found in '{input_path.name}'.\n"
            "Ensure the image is clear and well-lit, and contains a valid code."
        )

    results = []
    for code in codes:
        data = code.data.decode("utf-8", errors="replace")
        kind = code.type
        results.append(f"[{kind}] {data}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(results), encoding="utf-8")
    return ConversionResult(output=output_path, extra={"codes_found": len(codes)})


# ── registration ──────────────────────────────────────────────────────────

# txt → png/jpg  (generate QR from text/URL content)
for _dst in ("png", "jpg"):
    register(
        "txt", _dst,
        backend="qrcode",
        family="image",
        description=f"txt -> {_dst} (QR code generation)",
        lossy=False,
        options=_GEN_OPTIONS,
    )(_txt_to_qr)

# Raster images → txt  (decode QR / barcode)
_DECODABLE = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"]
for _src in _DECODABLE:
    register(
        _src, "txt",
        backend="pyzbar",
        family="image",
        description=f"{_src} -> txt (QR/barcode decode)",
        lossy=True,
    )(_img_to_decoded)
