"""
converters/archives.py — archive family (zip <-> tar variants), stdlib only.

Conversion here means: extract every member from the source archive, then
repack them into the destination format, preserving relative paths.
"""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path

from ..registry import ConversionResult, OptionSpec, register

# format id -> tarfile mode suffix ("" for plain tar, or compression codec)
_TAR_MODES = {"tar": "", "tar.gz": "gz", "tar.bz2": "bz2", "tar.xz": "xz"}
FORMATS = ["zip", *_TAR_MODES.keys()]

OPTIONS = [
    OptionSpec("strip_top_level", ("--strip-top-level",),
               "Drop a single shared top-level folder when repacking, if every member has one.",
               default=False, action="store_true"),
]


def _extract(input_path: Path, dst_dir: Path, fmt: str) -> None:
    if fmt == "zip":
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(dst_dir)
    else:
        with tarfile.open(input_path, f"r:{_TAR_MODES[fmt]}" if _TAR_MODES[fmt] else "r:") as tf:
            tf.extractall(dst_dir, filter="data")


def _maybe_strip_top_level(root: Path) -> Path:
    entries = list(root.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


def _pack(src_dir: Path, output_path: Path, fmt: str) -> int:
    count = 0
    if fmt == "zip":
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(src_dir))
                    count += 1
    else:
        mode = f"w:{_TAR_MODES[fmt]}" if _TAR_MODES[fmt] else "w"
        with tarfile.open(output_path, mode) as tf:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    tf.add(f, f.relative_to(src_dir))
                    count += 1
    return count


def _make_converter(src_fmt: str, dst_fmt: str):
    def _convert(input_path: Path, output_path: Path, *, strip_top_level: bool = False,
                 **_options) -> ConversionResult:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _extract(input_path, tmp_path, src_fmt)
            pack_root = _maybe_strip_top_level(tmp_path) if strip_top_level else tmp_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            n_files = _pack(pack_root, output_path, dst_fmt)
        return ConversionResult(output=output_path, extra={"files": n_files})
    return _convert


for _src in FORMATS:
    for _dst in FORMATS:
        if _dst == _src:
            continue
        register(
            _src, _dst,
            backend="stdlib",
            family="archive",
            description=f"{_src} → {_dst}",
            options=OPTIONS,
        )(_make_converter(_src, _dst))
