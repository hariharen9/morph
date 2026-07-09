"""
converters/fonts.py — font family, powered by fontTools.

ttf/otf are the "raw" outline formats; woff/woff2 are web-compression
wrappers around the same outline data. fontTools reads any of these and
re-saves with a different `flavor`, so one function covers every pair.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

from ..registry import ConversionResult, register

# format id -> fontTools "flavor" (None means a bare sfnt: .ttf or .otf)
_FLAVORS: dict[str, str | None] = {"ttf": None, "otf": None, "woff": "woff", "woff2": "woff2"}
FORMATS = list(_FLAVORS.keys())


def _font_convert(input_path: Path, output_path: Path, dst: str, **_options) -> ConversionResult:
    font = TTFont(input_path)

    # The real constraint isn't "ttf vs otf" as a pair — it's outline format
    # (glyf vs CFF/CFF2). woff/woff2 are just compression wrappers around
    # whichever outline table the font already has, so a multi-hop route
    # like ttf -> woff -> otf can silently smuggle a glyf-outline font into
    # a .otf file without ever hitting a direct ttf->otf edge. Check the
    # actual table contents at every hop that lands on a bare sfnt.
    if dst == "ttf" and "glyf" not in font:
        raise RuntimeError(
            "Refusing to save as .ttf: this font has no 'glyf' outline table "
            "(it's CFF-based, i.e. really an OTF). fontTools can't convert "
            "CFF outlines to TrueType outlines by just relabeling the file."
        )
    if dst == "otf" and "glyf" in font and "CFF " not in font and "CFF2" not in font:
        raise RuntimeError(
            "Refusing to save as .otf: this font has a 'glyf' outline table "
            "(it's TrueType-based, i.e. really a TTF). fontTools can't convert "
            "TrueType outlines to CFF outlines by just relabeling the file."
        )

    font.flavor = _FLAVORS[dst]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(output_path))
    name_table = font.get("name")
    family = None
    if name_table is not None:
        family = name_table.getDebugName(1)
    return ConversionResult(output=output_path, extra={"family": family})


def _make_converter(dst: str):
    def _convert(input_path: Path, output_path: Path, **options) -> ConversionResult:
        return _font_convert(input_path, output_path, dst, **options)
    return _convert


for _src in FORMATS:
    for _dst in FORMATS:
        if _dst == _src:
            continue
        # ttf <-> otf both being "no flavor" sfnt containers with genuinely
        # different outline formats (glyf vs CFF) isn't a safe blind resave —
        # fontTools won't convert glyph outlines between quadratic/cubic for you.
        if {_src, _dst} == {"ttf", "otf"}:
            continue
        register(
            _src, _dst, backend="fonttools", family="font",
            description=f"{_src} → {_dst} (fontTools)",
        )(_make_converter(_dst))
