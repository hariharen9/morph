"""
batch.py — parallel batch conversion with live Rich progress display.

Usage from the CLI:

    morph batch '*.mp4' mp3
    morph batch ./videos/ mp3 --recursive --workers 4
    morph batch '*.flac' '*.wav' mp3 --out-dir ./converted/ --skip-existing
    morph batch '*.mp4' mp3 --rename '{stem}_audio' --bitrate 192k

All the heavy lifting lives here; cli.py just parses args and calls
`run_batch()`.  The live display uses a Rich Live table that updates
every 200 ms showing per-file status, an overall progress bar, and a
summary report on completion.
"""

from __future__ import annotations

import glob
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table as RichTable
from rich.theme import Theme

from . import deps
from .history import HistoryEntry, append_entry, generate_batch_id, make_entry
from .registry import ConversionResult, ConverterSpec, detect_format, registry


# ── data types ────────────────────────────────────────────────────────────────

class JobState(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Job:
    input_path: Path
    output_path: Path
    src_fmt: str
    dst_fmt: str
    conv_path: list[ConverterSpec]
    state: JobState = JobState.WAITING
    elapsed: float = 0.0
    error: Optional[str] = None
    input_size: int = 0
    output_size: int = 0


@dataclass
class BatchResult:
    total: int = 0
    converted: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed: float = 0.0
    errors: list[tuple[str, str]] = field(default_factory=list)


# ── input collection ──────────────────────────────────────────────────────────

def collect_inputs(
    patterns: list[str],
    target_fmt: str,
    *,
    recursive: bool = False,
    out_dir: Optional[Path] = None,
    mirror: bool = False,
    rename_template: Optional[str] = None,
    skip_existing: bool = False,
    newer_only: bool = False,
    base_dir: Optional[Path] = None,
) -> list[Job]:
    """
    Resolve input patterns / directories into a list of Job objects,
    each with its input_path, computed output_path, and conversion path.
    """
    raw_files: list[Path] = []

    for pattern in patterns:
        p = Path(pattern)
        if p.is_dir():
            if recursive:
                raw_files.extend(f for f in p.rglob("*") if f.is_file())
            else:
                raw_files.extend(f for f in p.iterdir() if f.is_file())
        else:
            expanded = glob.glob(pattern, recursive=recursive)
            raw_files.extend(Path(f) for f in expanded if Path(f).is_file())

    # Deduplicate, preserving order
    seen: set[Path] = set()
    files: list[Path] = []
    for f in raw_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(f)

    target_fmt = target_fmt.lower().lstrip(".")
    jobs: list[Job] = []

    for file in files:
        src_fmt = detect_format(file)
        if src_fmt == target_fmt:
            # Same format → skip
            jobs.append(Job(
                input_path=file,
                output_path=file,
                src_fmt=src_fmt,
                dst_fmt=target_fmt,
                conv_path=[],
                state=JobState.SKIPPED,
                error="same format",
            ))
            continue

        conv_path = registry.find_path(src_fmt, target_fmt)
        if conv_path is None:
            jobs.append(Job(
                input_path=file,
                output_path=file,
                src_fmt=src_fmt,
                dst_fmt=target_fmt,
                conv_path=[],
                state=JobState.SKIPPED,
                error=f"no route from .{src_fmt}",
            ))
            continue

        output_path = _compute_output(
            file, target_fmt,
            out_dir=out_dir, mirror=mirror,
            rename_template=rename_template,
            base_dir=base_dir,
        )

        if skip_existing and output_path.exists():
            jobs.append(Job(
                input_path=file, output_path=output_path,
                src_fmt=src_fmt, dst_fmt=target_fmt, conv_path=conv_path,
                state=JobState.SKIPPED, error="output exists",
            ))
            continue

        if newer_only and output_path.exists():
            if output_path.stat().st_mtime >= file.stat().st_mtime:
                jobs.append(Job(
                    input_path=file, output_path=output_path,
                    src_fmt=src_fmt, dst_fmt=target_fmt, conv_path=conv_path,
                    state=JobState.SKIPPED, error="output is newer",
                ))
                continue

        jobs.append(Job(
            input_path=file, output_path=output_path,
            src_fmt=src_fmt, dst_fmt=target_fmt, conv_path=conv_path,
            input_size=file.stat().st_size if file.exists() else 0,
        ))

    return jobs


def _compute_output(
    input_path: Path,
    target_fmt: str,
    *,
    out_dir: Optional[Path] = None,
    mirror: bool = False,
    rename_template: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> Path:
    stem = input_path.stem
    src_fmt = detect_format(input_path)

    if rename_template:
        name = rename_template.format(
            stem=stem, fmt=target_fmt, src_fmt=src_fmt,
        ) + f".{target_fmt}"
    else:
        name = f"{stem}.{target_fmt}"

    if out_dir:
        if mirror and base_dir:
            try:
                rel = input_path.parent.relative_to(base_dir)
            except ValueError:
                rel = Path()
            dest = out_dir / rel / name
        else:
            dest = out_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    return input_path.parent / name


# ── per-job conversion (runs in a thread) ─────────────────────────────────────

def _convert_one(
    job: Job,
    options_dict: dict[str, Any],
    lock: threading.Lock,
) -> Job:
    """Run the full conversion chain for a single job, updating its state."""
    with lock:
        job.state = JobState.RUNNING

    start = time.perf_counter()
    current_input = job.input_path

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, spec in enumerate(job.conv_path):
                is_last = i == len(job.conv_path) - 1
                hop_out = (
                    job.output_path if is_last
                    else Path(tmpdir) / f"hop{i}.{spec.dst}"
                )
                hop_options = {
                    opt.name: options_dict.get(opt.name, opt.default)
                    for opt in spec.options
                }
                result = spec.func(current_input, hop_out, **hop_options)
                current_input = result.output
    except Exception as exc:
        with lock:
            job.state = JobState.FAILED
            job.elapsed = time.perf_counter() - start
            job.error = str(exc)
        return job

    with lock:
        job.state = JobState.DONE
        job.elapsed = time.perf_counter() - start
        if job.output_path.exists():
            job.output_size = job.output_path.stat().st_size

    return job


# ── size formatting ───────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    if n == 0:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


# ── live display ──────────────────────────────────────────────────────────────

_SYMBOLS = {
    JobState.WAITING: "[dim]·[/dim]",
    JobState.RUNNING: "[cyan]▶[/cyan]",
    JobState.DONE:    "[green]✓[/green]",
    JobState.FAILED:  "[red]✗[/red]",
    JobState.SKIPPED: "[yellow]⊘[/yellow]",
}

_STATUS_STYLE = {
    JobState.WAITING: "dim",
    JobState.RUNNING: "cyan",
    JobState.DONE:    "green",
    JobState.FAILED:  "red",
    JobState.SKIPPED: "yellow",
}


def _build_display(jobs: list[Job], target_fmt: str, elapsed: float) -> RichTable:
    """Build the full live display table."""
    done_count = sum(1 for j in jobs if j.state == JobState.DONE)
    fail_count = sum(1 for j in jobs if j.state == JobState.FAILED)
    skip_count = sum(1 for j in jobs if j.state == JobState.SKIPPED)
    total = len(jobs)
    convertible = total - skip_count

    tbl = RichTable(
        box=box.ROUNDED, border_style="cyan",
        title=f"morph batch — {total} files → {target_fmt}",
        title_style="bold cyan",
        caption=(
            f"[green]✓ {done_count}[/green]  "
            f"[red]✗ {fail_count}[/red]  "
            f"[yellow]⊘ {skip_count}[/yellow]  "
            f"[dim]⏱ {elapsed:.1f}s[/dim]"
        ),
        show_edge=True,
        pad_edge=True,
    )
    tbl.add_column("", width=2, no_wrap=True)
    tbl.add_column("File", style="white", ratio=3, no_wrap=True)
    tbl.add_column("Status", ratio=2, no_wrap=True)
    tbl.add_column("Time", justify="right", width=8, no_wrap=True)
    tbl.add_column("Size", justify="right", width=18, no_wrap=True)

    for j in jobs:
        sym = _SYMBOLS[j.state]
        style = _STATUS_STYLE[j.state]

        name = j.input_path.name
        if len(name) > 35:
            name = name[:32] + "..."

        if j.state == JobState.DONE:
            status = "done"
            time_str = f"{j.elapsed:.1f}s"
            in_s = _fmt_size(j.input_size)
            out_s = _fmt_size(j.output_size)
            size_str = f"{in_s} → {out_s}" if in_s else ""
        elif j.state == JobState.RUNNING:
            status = "converting…"
            time_str = ""
            size_str = _fmt_size(j.input_size)
        elif j.state == JobState.FAILED:
            status = j.error or "error"
            if len(status) > 30:
                status = status[:27] + "..."
            time_str = f"{j.elapsed:.1f}s"
            size_str = ""
        elif j.state == JobState.SKIPPED:
            status = j.error or "skipped"
            time_str = ""
            size_str = ""
        else:
            status = "waiting"
            time_str = ""
            size_str = ""

        tbl.add_row(sym, name, f"[{style}]{status}[/{style}]", time_str, size_str)

    return tbl


# ── main entry point ──────────────────────────────────────────────────────────

def run_batch(
    jobs: list[Job],
    target_fmt: str,
    options_dict: dict[str, Any],
    console: Console,
    *,
    workers: int = 4,
    fail_fast: bool = False,
    error_log: Optional[Path] = None,
    quiet: bool = False,
) -> BatchResult:
    """
    Execute all convertible jobs in parallel with a live Rich display,
    returning a BatchResult summary.
    """
    batch_id = generate_batch_id()
    lock = threading.Lock()
    start_time = time.perf_counter()

    convertible = [j for j in jobs if j.state == JobState.WAITING]
    result = BatchResult(total=len(jobs), skipped=sum(1 for j in jobs if j.state == JobState.SKIPPED))

    if not convertible:
        if not quiet:
            console.print("[warning]No files to convert.[/warning]")
        return result

    # Pre-check dependencies for all unique routes
    needed: set[str] = set()
    for j in convertible:
        needed.update(registry.required_binaries(j.conv_path))
    if needed and not deps.ensure_all(list(needed), console, assume_yes=False):
        console.print("[error]✗ Required dependency not available — aborting batch.[/error]")
        return result

    # Error log file handle
    err_fh = None
    if error_log:
        try:
            err_fh = open(error_log, "a", encoding="utf-8")
        except OSError:
            console.print(f"[warning]Could not open error log: {error_log}[/warning]")

    stop_flag = threading.Event()

    def _submit_and_track(executor: ThreadPoolExecutor) -> None:
        futures: dict[Future, Job] = {}
        for j in convertible:
            if stop_flag.is_set():
                break
            f = executor.submit(_convert_one, j, options_dict, lock)
            futures[f] = j

        for future in as_completed(futures):
            j = futures[future]
            try:
                future.result()
            except Exception as exc:
                with lock:
                    j.state = JobState.FAILED
                    j.error = str(exc)

            # History
            route = " → ".join([j.src_fmt] + [s.dst for s in j.conv_path])
            backends = ", ".join(dict.fromkeys(s.backend for s in j.conv_path))
            entry = make_entry(
                j.input_path, j.src_fmt, j.output_path, j.dst_fmt,
                route, backends, j.state == JobState.DONE, j.elapsed,
                mode="batch", batch_id=batch_id,
                error=j.error,
            )
            append_entry(entry)

            if j.state == JobState.FAILED:
                if err_fh:
                    try:
                        err_fh.write(f"{j.input_path}: {j.error}\n")
                        err_fh.flush()
                    except OSError:
                        pass
                if fail_fast:
                    stop_flag.set()

    if quiet:
        # No live display — just run and print summary
        with ThreadPoolExecutor(max_workers=workers) as executor:
            _submit_and_track(executor)
    else:
        with Live(
            _build_display(jobs, target_fmt, 0),
            console=console, refresh_per_second=5, transient=False,
        ) as live:
            def _refresh_loop() -> None:
                while not _done.is_set():
                    elapsed = time.perf_counter() - start_time
                    live.update(_build_display(jobs, target_fmt, elapsed))
                    _done.wait(0.2)
                elapsed = time.perf_counter() - start_time
                live.update(_build_display(jobs, target_fmt, elapsed))

            _done = threading.Event()
            refresh_thread = threading.Thread(target=_refresh_loop, daemon=True)
            refresh_thread.start()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                _submit_and_track(executor)

            _done.set()
            refresh_thread.join(timeout=2)

    if err_fh:
        err_fh.close()

    total_elapsed = time.perf_counter() - start_time
    result.converted = sum(1 for j in jobs if j.state == JobState.DONE)
    result.failed = sum(1 for j in jobs if j.state == JobState.FAILED)
    result.elapsed = total_elapsed
    result.errors = [(str(j.input_path.name), j.error or "unknown") for j in jobs if j.state == JobState.FAILED]

    # Summary panel
    if not quiet:
        console.print()
        parts = [
            f"[green]✓ {result.converted} converted[/green]",
            f"[red]✗ {result.failed} failed[/red]",
        ]
        if result.skipped:
            parts.append(f"[yellow]⊘ {result.skipped} skipped[/yellow]")
        parts.append(f"[dim]⏱ {result.elapsed:.1f}s[/dim]")
        console.print(Panel.fit("  ".join(parts), title="morph batch — complete", border_style="cyan"))

        if result.errors:
            console.print()
            for name, err in result.errors:
                console.print(f"  [red]✗[/red] {name} — {err}")

    return result
