"""
converters/vtracer_converter.py — raster-to-SVG vectorization wrapper, powered by vtracer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

OPTIONS = [
    OptionSpec("mode", ("--mode",), "Curve fitting mode ('spline' for smooth curves, 'polygon' for sharp shapes).", default="spline"),
    OptionSpec("colormode", ("--colormode",), "Color mode ('color' or 'binary').", default="color"),
    OptionSpec("hierarchical", ("--hierarchical",), "Shape layout style ('stacked' for layered shapes, 'cutout' for no overlaps).", default="stacked"),
    OptionSpec("filter_speckle", ("--filter-speckle",), "Filter speckle noise (pixels, e.g. 4).", default=4, type=int),
    OptionSpec("color_precision", ("--color-precision",), "Color precision (number of significant bits, 1-8).", default=6, type=int),
    OptionSpec("layer_difference", ("--layer-difference",), "Color difference threshold for layering (1-255).", default=16, type=int),
    OptionSpec("corner_threshold", ("--corner-threshold",), "Corner threshold (degrees, 0-180).", default=60, type=int),
    OptionSpec("length_threshold", ("--length-threshold",), "Length threshold for splines.", default=4.0, type=float),
    OptionSpec("max_iterations", ("--max-iterations",), "Max iterations for spline fitting.", default=10, type=int),
    OptionSpec("splice_threshold", ("--splice-threshold",), "Splice threshold (degrees, 0-180).", default=45, type=int),
    OptionSpec("path_precision", ("--path-precision",), "Path decimal precision (number of decimal places).", default=2, type=int),
]


def _image_to_svg(
    input_path: Path,
    output_path: Path,
    *,
    mode: str = "spline",
    colormode: str = "color",
    hierarchical: str = "stacked",
    filter_speckle: int = 4,
    color_precision: int = 6,
    layer_difference: int = 16,
    corner_threshold: int = 60,
    length_threshold: float = 4.0,
    max_iterations: int = 10,
    splice_threshold: int = 45,
    path_precision: int = 2,
    **_options,
) -> ConversionResult:
    import subprocess
    import sys

    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    code = f"""
import vtracer
vtracer.convert_image_to_svg_py(
    {repr(str(input_path))},
    {repr(str(output_path))},
    {repr(colormode)},
    {repr(hierarchical)},
    {repr(mode)},
    {filter_speckle},
    {color_precision},
    {layer_difference},
    {corner_threshold},
    {length_threshold},
    {max_iterations},
    {splice_threshold},
    {path_precision}
)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"vtracer tracing failed:\n{result.stderr.strip()}")
        
    return ConversionResult(output=output_path)


# Register all common raster formats to SVG
for src in ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"):
    register(
        src,
        "svg",
        backend="vtracer",
        family="image",
        description=f"{src} → svg (vectorize via vtracer)",
        lossy=True,
        options=OPTIONS,
    )(_image_to_svg)
