"""
converters/archives.py — archive family (zip <-> tar <-> 7z, rar extract-only).

Conversion means: extract every member from the source archive, then repack
them into the destination format, preserving relative paths.

Supported formats and their backing libraries:
  zip       — stdlib zipfile        (read + write)
  tar.*     — stdlib tarfile        (read + write)
  7z        — py7zr (optional)      (read + write)
  rar       — rarfile (optional)    (read only — RAR creation is proprietary)

py7zr and rarfile are optional; a clear error with install hint is raised if
the user tries a conversion that needs one and it isn't installed.
"""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path

from ..registry import ConversionResult, OptionSpec, register

# ── format tables ──────────────────────────────────────────────────────────

# tarfile compression mode suffix (empty string = uncompressed tar)
_TAR_MODES = {"tar": "", "tar.gz": "gz", "tar.bz2": "bz2", "tar.xz": "xz"}

# Formats that can be both read and written (appear as src AND dst)
RW_FORMATS = ["zip", *_TAR_MODES.keys(), "7z"]

# Formats that can only be read (appear as src only — never a pack target)
RO_FORMATS = ["rar"]

ALL_SRC_FORMATS = RW_FORMATS + RO_FORMATS

OPTIONS = [
    OptionSpec("strip_top_level", ("--strip-top-level",),
               "Drop a single shared top-level folder when repacking, if every member has one.",
               default=False, action="store_true"),
]


# ── optional library helpers ───────────────────────────────────────────────

def _require_py7zr():
    try:
        import py7zr
        return py7zr
    except ImportError:
        raise RuntimeError(
            "py7zr is required for 7z archive support.\n"
            "Install it with: pip install py7zr"
        )


def _require_rarfile():
    try:
        import rarfile
        return rarfile
    except ImportError:
        raise RuntimeError(
            "rarfile is required for RAR archive extraction.\n"
            "Install it with: pip install rarfile\n"
            "Note: unrar or bsdtar must also be on your PATH."
        )


# ── extract ───────────────────────────────────────────────────────────────

def _extract(input_path: Path, dst_dir: Path, fmt: str) -> None:
    if fmt == "zip":
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(dst_dir)
    elif fmt in _TAR_MODES:
        mode = f"r:{_TAR_MODES[fmt]}" if _TAR_MODES[fmt] else "r:"
        with tarfile.open(input_path, mode) as tf:
            tf.extractall(dst_dir, filter="data")
    elif fmt == "7z":
        py7zr = _require_py7zr()
        with py7zr.SevenZipFile(input_path, mode="r") as sz:
            sz.extractall(path=dst_dir)
    elif fmt == "rar":
        rarfile = _require_rarfile()
        with rarfile.RarFile(input_path) as rf:
            rf.extractall(path=dst_dir)
    else:
        raise ValueError(f"Unsupported source archive format: {fmt!r}")


# ── strip top-level ───────────────────────────────────────────────────────

def _maybe_strip_top_level(root: Path) -> Path:
    entries = list(root.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


# ── pack ──────────────────────────────────────────────────────────────────

def _pack(src_dir: Path, output_path: Path, fmt: str) -> int:
    count = 0
    if fmt == "zip":
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(src_dir))
                    count += 1
    elif fmt in _TAR_MODES:
        mode = f"w:{_TAR_MODES[fmt]}" if _TAR_MODES[fmt] else "w"
        with tarfile.open(output_path, mode) as tf:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    tf.add(f, f.relative_to(src_dir))
                    count += 1
    elif fmt == "7z":
        py7zr = _require_py7zr()
        with py7zr.SevenZipFile(output_path, mode="w") as sz:
            for f in src_dir.rglob("*"):
                if f.is_file():
                    sz.write(f, f.relative_to(src_dir))
                    count += 1
    else:
        raise ValueError(f"Unsupported destination archive format: {fmt!r}")
    return count


# ── converter factory ─────────────────────────────────────────────────────

def _make_converter(src_fmt: str, dst_fmt: str):
    def _convert(
        input_path: Path,
        output_path: Path,
        *,
        strip_top_level: bool = False,
        **_options,
    ) -> ConversionResult:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _extract(input_path, tmp_path, src_fmt)
            pack_root = _maybe_strip_top_level(tmp_path) if strip_top_level else tmp_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            n_files = _pack(pack_root, output_path, dst_fmt)
        return ConversionResult(output=output_path, extra={"files": n_files})
    _convert.__name__ = f"convert_{src_fmt}_to_{dst_fmt}"
    return _convert


# ── registration ──────────────────────────────────────────────────────────

# Backend label per source format
_SRC_BACKEND = {
    "zip":     "stdlib",
    "tar":     "stdlib",
    "tar.gz":  "stdlib",
    "tar.bz2": "stdlib",
    "tar.xz":  "stdlib",
    "7z":      "py7zr",
    "rar":     "rarfile",
}

# Backend label per destination format
_DST_BACKEND = {
    "zip":     "stdlib",
    "tar":     "stdlib",
    "tar.gz":  "stdlib",
    "tar.bz2": "stdlib",
    "tar.xz":  "stdlib",
    "7z":      "py7zr",
}

for _src in ALL_SRC_FORMATS:
    for _dst in RW_FORMATS:          # RAR is extract-only; never a destination
        if _dst == _src:
            continue
        _sb = _SRC_BACKEND[_src]
        _db = _DST_BACKEND[_dst]
        _backend = f"{_sb}+{_db}" if _sb != _db else _sb
        register(
            _src, _dst,
            backend=_backend,
            family="archive",
            description=f"{_src} -> {_dst}",
            options=OPTIONS,
        )(_make_converter(_src, _dst))
