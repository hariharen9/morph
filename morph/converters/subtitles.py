"""
converters/subtitles.py — standalone subtitle format conversion via pysubs2.

pysubs2 natively reads and writes all major subtitle formats while preserving
timing, styling, and positioning metadata. This module registers every valid
(src, dst) pair across those formats.

Supported formats:
  srt   — SubRip (most common, plain text timing + dialogue)
  vtt   — WebVTT (web standard, used by HTML5 <track>)
  ass   — Advanced SubStation Alpha (full styling: fonts, colours, positions)
  ssa   — SubStation Alpha (predecessor to ASS, still common in anime)
  sub   — MicroDVD (frame-number based timing)
  sami  — SAMI / .smi (Windows Media Player format)

Note on .sub / MicroDVD: timing is frame-number-based, so accurate conversion
to/from time-based formats requires knowing the source FPS. pysubs2 defaults
to 23.976 fps if none is detected; use --fps to override.

Requires: pysubs2 (pure Python, no system binaries needed)
  pip install pysubs2
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

# pysubs2 format id -> file extension
# Keys are the strings pysubs2.SSAFile.save() accepts as format_
FORMATS: dict[str, str] = {
    "srt":  "srt",
    "vtt":  "vtt",
    "ass":  "ass",
    "ssa":  "ssa",
    "sub":  "sub",   # MicroDVD
    "sami": "sami",
}

# pysubs2 uses these internal format names (different from extension in some cases)
_PYSUBS2_FMT: dict[str, str] = {
    "srt":  "srt",
    "vtt":  "vtt",
    "ass":  "ass",
    "ssa":  "ssa",
    "sub":  "microdvd",
    "sami": "sami",
}

OPTIONS = [
    OptionSpec(
        "fps", ("--fps",),
        "Frames per second for MicroDVD (.sub) timing conversion. "
        "Default: auto-detect, fallback to 23.976.",
        type=float,
    ),
    OptionSpec(
        "encoding", ("--encoding",),
        "Character encoding of the input subtitle file. Default: auto-detect (utf-8-sig, utf-8, latin-1).",
        default="utf-8-sig",
    ),
]


def _require_pysubs2():
    try:
        import pysubs2
        return pysubs2
    except ImportError:
        raise RuntimeError(
            "pysubs2 is required for subtitle format conversion.\n"
            "Install it with: pip install pysubs2"
        )


def _sub_convert(
    input_path: Path,
    output_path: Path,
    *,
    src_fmt: str,
    dst_fmt: str,
    fps: Optional[float] = None,
    encoding: str = "utf-8-sig",
    **_options,
) -> ConversionResult:
    pysubs2 = _require_pysubs2()

    # Load — try the requested encoding first, fall back gracefully
    try:
        subs = pysubs2.load(str(input_path), encoding=encoding, fps=fps)
    except (UnicodeDecodeError, LookupError):
        # Fallback encoding chain for files without BOM
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                subs = pysubs2.load(str(input_path), encoding=enc, fps=fps)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            raise RuntimeError(
                f"Could not decode '{input_path.name}' with any supported encoding. "
                "Try passing --encoding explicitly."
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # MicroDVD output requires FPS; if not supplied, use detected or default
    save_fps = fps or subs.fps or 23.976

    dst_pysubs2_fmt = _PYSUBS2_FMT[dst_fmt]

    if dst_fmt == "sub":
        subs.save(str(output_path), format_=dst_pysubs2_fmt, fps=save_fps)
    else:
        subs.save(str(output_path), format_=dst_pysubs2_fmt)

    return ConversionResult(output=output_path, extra={"events": len(subs)})


# ── registration ──────────────────────────────────────────────────────────

def _make_converter(src: str, dst: str):
    def _convert(input_path: Path, output_path: Path, **opts) -> ConversionResult:
        return _sub_convert(input_path, output_path, src_fmt=src, dst_fmt=dst, **opts)
    _convert.__name__ = f"sub_{src}_to_{dst}"
    return _convert


# Lossy conversions: anything -> srt/sub loses styling; anything -> vtt loses some ASS tags
_LOSSY_DST = {"srt", "sub", "vtt"}

for _src in FORMATS:
    for _dst in FORMATS:
        if _src == _dst:
            continue
        register(
            _src, _dst,
            backend="pysubs2",
            family="subtitle",
            description=f"{_src} -> {_dst} (pysubs2)",
            lossy=(_dst in _LOSSY_DST),
            options=OPTIONS,
        )(_make_converter(_src, _dst))
