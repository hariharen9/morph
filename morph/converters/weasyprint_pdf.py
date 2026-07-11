"""
converters/weasyprint_pdf.py — direct HTML → PDF via WeasyPrint.

Pandoc's html→pdf route goes through a LaTeX intermediate, which destroys
CSS layout, custom fonts, flexbox/grid, and modern styling. WeasyPrint
renders HTML+CSS directly (like a browser) and produces much more faithful
output for CSS-heavy pages, design documents, and styled reports.

This module registers html → pdf with WeasyPrint, overwriting the pandoc
route (w > d alphabetically → this module loads after documents.py).

Requires: weasyprint (pip install weasyprint)
  On Linux also: system Cairo/Pango/etc. (apt install libpango-1.0-0 ...)
  On macOS: brew install pango
  On Windows: weasyprint ships wheels with bundled dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

OPTIONS = [
    OptionSpec(
        "base_url", ("--base-url",),
        "Base URL for resolving relative links in the HTML (default: file's directory).",
    ),
    OptionSpec(
        "stylesheets", ("--stylesheet",),
        "Path to an extra CSS file to inject before rendering.",
    ),
    OptionSpec(
        "presentational_hints", ("--presentational-hints",),
        "Respect HTML presentational attributes (bgcolor, width, etc.).",
        default=False, action="store_true",
    ),
]


def _require_weasyprint():
    try:
        import weasyprint
        return weasyprint
    except ImportError:
        raise RuntimeError(
            "weasyprint is required for CSS-faithful HTML → PDF rendering.\n"
            "Install it with: pip install weasyprint\n"
            "Linux also needs: sudo apt install libpango-1.0-0 libpangoft2-1.0-0"
        )


@register(
    "html", "pdf",
    backend="weasyprint",
    family="document",
    description="html -> pdf (CSS-faithful rendering via WeasyPrint)",
    lossy=False,
    options=OPTIONS,
)
def html_to_pdf(
    input_path: Path,
    output_path: Path,
    *,
    base_url: Optional[str] = None,
    stylesheets: Optional[str] = None,
    presentational_hints: bool = False,
    **_options,
) -> ConversionResult:
    weasyprint = _require_weasyprint()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Default base URL to the file's directory so relative assets resolve
    resolved_base = base_url or input_path.parent.as_uri()

    extra_css = []
    if stylesheets:
        extra_css.append(weasyprint.CSS(filename=stylesheets))

    html = weasyprint.HTML(
        filename=str(input_path),
        base_url=resolved_base,
    )
    html.write_pdf(
        str(output_path),
        stylesheets=extra_css or None,
        presentational_hints=presentational_hints,
    )

    return ConversionResult(output=output_path)
