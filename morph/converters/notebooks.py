"""
converters/notebooks.py — Jupyter notebook export via nbconvert.

Replaces the pandoc-generated ipynb → * edges from documents.py with proper
nbconvert-backed ones. nbconvert is the canonical tool for notebook export:
it renders real cell outputs, embedded images, and execution results.

Since this module is auto-imported alphabetically after documents.py (n > d),
its register() calls overwrite the pandoc edges for the same (src, dst) pairs.

Supported output formats:
  html      — full notebook rendering with outputs, plots, widgets
  pdf       — via LaTeX (requires xelatex/pdflatex on PATH)
  py        — Python script, stripped of markdown/output cells
  md        — Markdown with cell outputs as code blocks
  rst       — reStructuredText
  latex     — LaTeX source
  slides    — Reveal.js HTML slideshow (markdown cells → slides)
  asciidoc  — AsciiDoc

Requires: nbconvert  (pip install nbconvert)
PDF additionally requires a LaTeX engine on PATH (xelatex recommended).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..registry import ConversionResult, OptionSpec, register

# nbconvert --to token -> (morph dst format, output file extension, lossy)
_EXPORTERS: dict[str, tuple[str, str, bool]] = {
    "html":      ("html",     "html",  False),
    "pdf":       ("pdf",      "pdf",   True),
    "script":    ("py",       "py",    True),   # strips markdown/output cells
    "markdown":  ("md",       "md",    True),
    "rst":       ("rst",      "rst",   True),
    "latex":     ("latex",    "tex",   False),
    "slides":    ("slides",   "html",  True),
    "asciidoc":  ("asciidoc", "adoc",  True),
}

_EXECUTE_OPT = OptionSpec(
    "execute", ("--execute",),
    "Re-execute all cells before exporting (requires the notebook's kernel).",
    default=False, action="store_true",
)
_TIMEOUT_OPT = OptionSpec(
    "timeout", ("--timeout",),
    "Cell execution timeout in seconds (used with --execute). Default: 120.",
    default=120, type=int,
)
_KERNEL_OPT = OptionSpec(
    "kernel", ("--kernel",),
    "Kernel name to use when --execute is set (e.g. 'python3'). Default: notebook default.",
)
_TEMPLATE_OPT = OptionSpec(
    "template", ("--template",),
    "nbconvert template name or path (e.g. 'lab', 'classic', 'reveal').",
)

_OPTIONS = [_EXECUTE_OPT, _TIMEOUT_OPT, _KERNEL_OPT, _TEMPLATE_OPT]


def _require_nbconvert() -> None:
    if not shutil.which("jupyter") and not shutil.which("nbconvert"):
        try:
            import nbconvert  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "nbconvert is required for notebook export.\n"
                "Install it with: pip install nbconvert\n"
                "For PDF export also install a LaTeX engine (e.g. xelatex)."
            )


def _nbconvert(
    input_path: Path,
    output_path: Path,
    *,
    nbconvert_to: str,
    out_ext: str,
    execute: bool = False,
    timeout: int = 120,
    kernel: Optional[str] = None,
    template: Optional[str] = None,
    **_options,
) -> ConversionResult:
    _require_nbconvert()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "jupyter", "nbconvert",
            "--to", nbconvert_to,
            "--output-dir", tmpdir,
        ]

        if execute:
            cmd += ["--execute", "--ExecutePreprocessor.timeout", str(timeout)]
            if kernel:
                cmd += ["--ExecutePreprocessor.kernel_name", kernel]

        if template:
            cmd += ["--template", template]

        cmd.append(str(input_path))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"nbconvert failed:\n{result.stderr.strip() or result.stdout.strip()}"
            )

        # nbconvert names the output after the notebook stem
        produced_stem = input_path.stem
        # slides export also uses html extension
        produced = Path(tmpdir) / f"{produced_stem}.{out_ext}"

        if not produced.exists():
            candidates = list(Path(tmpdir).glob(f"*.{out_ext}"))
            if not candidates:
                # last resort: any file in tmpdir
                candidates = [f for f in Path(tmpdir).iterdir() if f.is_file()]
            if not candidates:
                raise RuntimeError(
                    f"nbconvert ran successfully but produced no .{out_ext} file.\n"
                    f"tmpdir contents: {list(Path(tmpdir).iterdir())}"
                )
            produced = candidates[0]

        shutil.copy2(str(produced), str(output_path))

    return ConversionResult(output=output_path)


def _make_converter(nbconvert_to: str, out_ext: str):
    def _convert(input_path: Path, output_path: Path, **opts) -> ConversionResult:
        return _nbconvert(
            input_path, output_path,
            nbconvert_to=nbconvert_to, out_ext=out_ext,
            **opts,
        )
    _convert.__name__ = f"ipynb_to_{nbconvert_to}"
    return _convert


# ── registration ──────────────────────────────────────────────────────────
# These deliberately overwrite the weaker pandoc-backed edges that documents.py
# registered for the same (ipynb, dst) pairs.

for _nbfmt, (_morph_dst, _ext, _lossy) in _EXPORTERS.items():
    register(
        "ipynb", _morph_dst,
        backend="nbconvert",
        requires_binary="jupyter",
        family="document",
        description=f"ipynb -> {_morph_dst} (nbconvert, with cell outputs)",
        lossy=_lossy,
        options=_OPTIONS,
    )(_make_converter(_nbfmt, _ext))
