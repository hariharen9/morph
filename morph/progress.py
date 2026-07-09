"""
progress.py — live status while a hop runs.

Every conversion function is a blocking call (subprocess.run, Pillow, a
pandas loop, ...). To show *something* live instead of a dead terminal:

  • If the spec supports real progress (currently: ffmpeg-backed hops), the
    function is called in a background thread with a `_progress(frac, status)`
    callback injected, and a determinate Rich progress bar tracks it.
  • Otherwise, the function still runs in a background thread, but the
    foreground just shows an indeterminate spinner with the backend name
    ("via pandoc", "via ffmpeg", ...) — so it's always visible *what* is
    doing the work, even when we can't say how far along it is.

Rich's Progress has its own auto-refreshing Live display, so a plain
`thread.join()` on the main thread is enough — no manual polling loop needed.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .registry import ConversionResult, ConverterSpec


def run_hop(spec: ConverterSpec, input_path: Path, output_path: Path,
            options: dict[str, Any], console: Console, *, quiet: bool = False) -> ConversionResult:
    if quiet:
        call_options = dict(options)
        if spec.supports_progress:
            call_options["_progress"] = lambda frac, status: None
        return spec.func(input_path, output_path, **call_options)

    label = f"{spec.src} → {spec.dst}"
    tool_tag = f"[muted]via {spec.backend}[/muted]"

    result_box: dict[str, Any] = {}
    error_box: dict[str, BaseException] = {}

    columns = [
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28),
        TextColumn("[muted]{task.fields[status]}[/muted]"),
        TimeElapsedColumn(),
    ]

    with Progress(*columns, console=console, transient=True) as progress:
        total = 100 if spec.supports_progress else None
        task_id = progress.add_task(f"{label}  {tool_tag}", total=total, status="")

        def _on_progress(frac: float, status: str) -> None:
            progress.update(task_id, completed=frac * 100, status=status)

        def _target() -> None:
            try:
                call_options = dict(options)
                if spec.supports_progress:
                    call_options["_progress"] = _on_progress
                result_box["result"] = spec.func(input_path, output_path, **call_options)
            except BaseException as exc:  # noqa: BLE001 — re-raised on the main thread below
                error_box["error"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if not error_box:
            progress.update(task_id, completed=100, status="done")

    if "error" in error_box:
        raise error_box["error"]
    return result_box["result"]
