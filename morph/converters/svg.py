"""
converters/svg.py — SVG family, powered by cairosvg.

SVG is output-only in reverse (raster -> vector requires actual tracing,
which is a fundamentally different, much lossier operation morph doesn't
attempt) — so this file only registers svg -> {png, jpg, pdf}.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

_RASTER_OPTIONS = [
    OptionSpec("width", ("--width",), "Output width in pixels. Default: SVG's intrinsic size.", type=int),
    OptionSpec("height", ("--height",), "Output height in pixels. Default: SVG's intrinsic size / aspect-correct.", type=int),
    OptionSpec("background", ("--background",), "Background color for transparent areas, e.g. 'white' or '#fff'. "
               "Default: transparent (png) / white (jpg)."),
]


def _svg_to_png(input_path: Path, output_path: Path, *, width: Optional[int] = None,
                 height: Optional[int] = None, background: Optional[str] = None,
                 **_options) -> ConversionResult:
    import cairosvg
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(url=str(input_path), write_to=str(output_path),
                      output_width=width, output_height=height, background_color=background)
    return ConversionResult(output=output_path)


def _svg_to_jpg(input_path: Path, output_path: Path, *, width: Optional[int] = None,
                 height: Optional[int] = None, background: Optional[str] = None,
                 **_options) -> ConversionResult:
    # cairosvg has no native JPEG writer — render to PNG in memory, then let
    # Pillow flatten transparency and encode as JPEG.
    import io
    import cairosvg
    from PIL import Image

    png_bytes = cairosvg.svg2png(url=str(input_path), output_width=width, output_height=height,
                                  background_color=background or "white")
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="JPEG")
    return ConversionResult(output=output_path)


def _svg_to_pdf(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    import cairosvg
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2pdf(url=str(input_path), write_to=str(output_path))
    return ConversionResult(output=output_path)


register("svg", "png", backend="cairosvg", family="image",
          description="svg → png (rasterize)", options=_RASTER_OPTIONS)(_svg_to_png)
register("svg", "jpg", backend="cairosvg", family="image",
          description="svg → jpg (rasterize, flattened)", lossy=True, options=_RASTER_OPTIONS)(_svg_to_jpg)
register("svg", "pdf", backend="cairosvg", family="document",
          description="svg → pdf (vector-preserving)")(_svg_to_pdf)
