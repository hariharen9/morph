"""
history.py — persistent conversion log.

Every conversion (single or batch) appends one line to
~/.morph_history.jsonl.  Entries record source, destination,
route, timing, and success/failure.  The `morph history`
subcommand reads this file back and renders a rich table.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

HISTORY_FILE = Path.home() / ".morph_history.jsonl"


@dataclass
class HistoryEntry:
    ts: str
    src_path: str
    src_fmt: str
    dst_path: str
    dst_fmt: str
    route: str
    backend: str
    success: bool
    elapsed_s: float
    mode: str = "single"          # "single" | "batch"
    batch_id: Optional[str] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)


def append_entry(entry: HistoryEntry) -> None:
    """Append one entry to the history JSONL file."""
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    except OSError:
        pass  # never let history I/O break a conversion


def read_entries(
    *,
    limit: int = 20,
    failed_only: bool = False,
    fmt_filter: Optional[str] = None,
) -> list[HistoryEntry]:
    """Read the last `limit` entries, optionally filtered."""
    if not HISTORY_FILE.exists():
        return []
    entries: list[HistoryEntry] = []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = HistoryEntry(
                    ts=d.get("ts", ""),
                    src_path=d.get("src_path", ""),
                    src_fmt=d.get("src_fmt", ""),
                    dst_path=d.get("dst_path", ""),
                    dst_fmt=d.get("dst_fmt", ""),
                    route=d.get("route", ""),
                    backend=d.get("backend", ""),
                    success=d.get("success", True),
                    elapsed_s=d.get("elapsed_s", 0.0),
                    mode=d.get("mode", "single"),
                    batch_id=d.get("batch_id"),
                    error=d.get("error"),
                    extra=d.get("extra", {}),
                )
                if failed_only and entry.success:
                    continue
                if fmt_filter:
                    norm = fmt_filter.lower().lstrip(".")
                    if norm not in (entry.src_fmt.lower(), entry.dst_fmt.lower()):
                        continue
                entries.append(entry)
    except OSError:
        return []
    return entries[-limit:]


def clear() -> bool:
    """Delete the history file.  Returns True if it existed."""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
        return True
    return False


def make_entry(
    src_path: Path,
    src_fmt: str,
    dst_path: Path,
    dst_fmt: str,
    route: str,
    backend: str,
    success: bool,
    elapsed_s: float,
    *,
    mode: str = "single",
    batch_id: Optional[str] = None,
    error: Optional[str] = None,
) -> HistoryEntry:
    """Helper to build and return a HistoryEntry."""
    return HistoryEntry(
        ts=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        src_path=str(src_path),
        src_fmt=src_fmt,
        dst_path=str(dst_path),
        dst_fmt=dst_fmt,
        route=route,
        backend=backend,
        success=success,
        elapsed_s=round(elapsed_s, 2),
        mode=mode,
        batch_id=batch_id,
        error=error,
    )


def generate_batch_id() -> str:
    """Short unique id for grouping batch entries."""
    return f"b-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
