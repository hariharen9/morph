#!/usr/bin/env python3
"""
morph — convert anything to anything, from the CLI.

  morph report.docx report.pdf
  morph data.csv data.xlsx --table-style TableStyleMedium2 --header-bg 2E7D32
  morph data.csv data.xlsx --help      (shows flags for THIS pair only)
  morph batch '*.mp4' mp3 --workers 4
  morph formats docx
  morph history
  morph deps
  morph                                 (no args -> launches the interactive TUI)

There is no "convert" subcommand — morph already means convert. Anything
that isn't a recognized subcommand (formats, deps, batch, history) is
treated as a conversion job and routed through the engine.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional
import yaml

# Ensure Unicode output works on Windows regardless of terminal encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.theme import Theme
from rich.tree import Tree
from typer.core import TyperGroup

from . import converters  # noqa: F401  (auto-discovers & registers every converter)
from . import deps
from .progress import run_hop
from .registry import detect_format, registry

THEME = Theme({
    "info": "bold cyan", "success": "bold green", "warning": "bold yellow",
    "error": "bold red", "muted": "dim white", "accent": "bold blue",
})
console = Console(theme=THEME)
err_console = Console(stderr=True, theme=THEME)

# Family display order and labels
_FAMILY_ORDER = ["document", "audio", "video", "image", "data", "archive", "font", "ebook"]
_FAMILY_LABELS = {
    "document": "document",
    "audio":    "audio",
    "video":    "video",
    "image":    "image",
    "data":     "data",
    "archive":  "archive",
    "font":     "font",
    "ebook":    "ebook",
}
_FAMILY_ICONS = {
    "document": "[cyan]*[/cyan]",
    "audio":    "[green]*[/green]",
    "video":    "[magenta]*[/magenta]",
    "image":    "[yellow]*[/yellow]",
    "data":     "[blue]*[/blue]",
    "archive":  "[red]*[/red]",
    "font":     "[cyan]*[/cyan]",
    "ebook":    "[green]*[/green]",
}


class MorphGroup(TyperGroup):
    """Makes `morph <file> <file> [flags]` work without a literal 'convert'
    subcommand: if the first token isn't a known subcommand name, it's
    forwarded to the hidden `run` command, which does the actual routing."""

    def resolve_command(self, ctx, args):
        # We explicitly allow "config" alongside whatever is in self.commands
        # just in case Typer hasn't fully populated the commands dict yet.
        known_commands = list(self.commands.keys()) + ["config", "init"]
        if args and args[0] not in known_commands:
            args = ["run", *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="morph",
    cls=MorphGroup,
    help="[bold cyan]morph[/bold cyan] — convert anything to anything, from the CLI.",
    rich_markup_mode="rich",
    invoke_without_command=True,
    pretty_exceptions_show_locals=False,
)


def _fmt_of(path: str | Path) -> str:
    path_str = str(path).lower()
    if path_str.startswith("http://") or path_str.startswith("https://"):
        return "url"
    if isinstance(path, str):
        path = Path(path)
    return detect_format(path)


def _print_route_help(input_file: str | Path, output_file: Path, path) -> None:
    src, dst = _fmt_of(input_file), _fmt_of(output_file)
    hop_str = " → ".join([src] + [s.dst for s in path])
    console.print(Panel.fit(f"[bold]{hop_str}[/bold]", title="morph — conversion route", border_style="cyan"))

    combined = registry.combined_options(path)
    console.print(f"\n[bold]Usage:[/bold] morph {input_file} {output_file} [OPTIONS]\n")
    console.print("[bold]Global options:[/bold]")
    console.print("  -y, --yes         Auto-confirm dependency installs")
    console.print("  --dry-run         Show the plan without running it")
    console.print("  -q, --quiet       Suppress banners and tables")

    if combined:
        console.print(f"\n[bold]Options for this conversion ({hop_str}):[/bold]")
        tbl = RichTable(box=box.SIMPLE, show_header=False, border_style="dim", pad_edge=False)
        tbl.add_column(style="accent", no_wrap=True)
        tbl.add_column(style="white")
        for opt in combined:
            flag_str = ", ".join(opt.flags)
            default_str = f"  [muted](default: {opt.default})[/muted]" if opt.default not in (None, False) else ""
            tbl.add_row(flag_str, f"{opt.help}{default_str}")
        console.print(tbl)
    else:
        console.print(f"\n[muted]No extra options for {hop_str} — just run it.[/muted]")


def _build_parser(options) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    for opt in options:
        kwargs = {"dest": opt.name, "default": opt.default, "help": opt.help}
        if opt.action:
            kwargs["action"] = opt.action
        else:
            kwargs["type"] = opt.type
        parser.add_argument(*opt.flags, **kwargs)
    return parser


def get_config_path() -> Path:
    return Path.home() / ".morphrc"

def load_config() -> dict:
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {}
            
            flat_config = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    flat_config.update(v)
                else:
                    flat_config[k] = v
            return flat_config
    except Exception as e:
        err_console.print(f"[warning]⚠ Failed to load {config_path}: {e}[/warning]")
        return {}


@app.command("config")
def init_config():
    """Generate a fully populated ~/.morphrc with best default values."""
    config_path = get_config_path()
    if config_path.exists():
        console.print(f"[warning]⚠ {config_path} already exists. Overwriting is not supported.[/warning]")
        raise typer.Exit(1)
        
    options_by_family = registry.all_options()
    
    yaml_lines = [
        "# Morph Configuration File",
        "# ------------------------",
        "# This file provides default options for all conversions.",
        "# Command line flags will always override these settings.",
        ""
    ]
    
    yaml_lines.extend([
        "global:",
        "  # Use headless browser to render JavaScript on URLs.",
        "  # js: false",
        "  # Auto-confirm dependency installs.",
        "  # yes: false",
        ""
    ])
    
    for family, options in sorted(options_by_family.items()):
        if not options:
            continue
        yaml_lines.append(f"{family}:")
        for opt in sorted(options, key=lambda x: x.name):
            if opt.help:
                yaml_lines.append(f"  # {opt.help}")
            
            default_val = opt.default
            if default_val is None:
                yaml_val = "null"
            elif isinstance(default_val, bool):
                yaml_val = str(default_val).lower()
            elif isinstance(default_val, str):
                yaml_val = repr(default_val)
            else:
                yaml_val = str(default_val)
                
            yaml_lines.append(f"  # {opt.name}: {yaml_val}")
        yaml_lines.append("")
        
    config_path.write_text("\\n".join(yaml_lines), encoding="utf-8")
    console.print(f"[success]✓ Generated full configuration file at {config_path}[/success]")


# ── run (hidden, handles direct file→file conversion) ────────────────────────

@app.command("run", hidden=True, context_settings={"ignore_unknown_options": True, "allow_extra_args": True, "help_option_names": []})
def run_cmd(
    ctx: typer.Context,
    input_file: str = typer.Argument(..., help="Source file or URL (http/https)."),
    output_file: Path = typer.Argument(..., help="Destination file (extension picks the target format)."),
    js: bool = typer.Option(False, "--js", help="Use headless browser to render JavaScript on URLs."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm dependency installs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the conversion plan without running it."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress banners and tables."),
) -> None:
    from . import history as hist

    src, dst = _fmt_of(input_file), _fmt_of(output_file)
    path = registry.find_path(src, dst)

    if path is None:
        err_console.print(f"[error]✗ No conversion path found from[/error] .{src} [error]to[/error] .{dst}")
        reachable = sorted(registry.reachable_targets(src).keys())
        if reachable:
            err_console.print(f"[muted]From .{src} morph can currently reach:[/muted] {', '.join(reachable)}")
        raise typer.Exit(1)

    if "--help" in ctx.args or "-h" in ctx.args:
        _print_route_help(input_file, output_file, path)
        raise typer.Exit(0)

    combined_opts = registry.combined_options(path)
    parser = _build_parser(combined_opts)
    
    # Merge ~/.morphrc values as defaults before parsing CLI arguments
    parser.set_defaults(**load_config())
    
    parsed, unknown = parser.parse_known_args(ctx.args)
    if unknown:
        err_console.print(f"[warning]⚠ Ignoring unrecognized option(s):[/warning] {' '.join(unknown)}")
    options_dict = vars(parsed)
    options_dict["js"] = js
    
    if js and path and path[0].src == "url":
        import dataclasses
        path[0] = dataclasses.replace(path[0], backend="crawl4ai")

    is_url = src == "url"
    input_path = input_file if is_url else Path(input_file)

    if not is_url and not input_path.exists():
        err_console.print(f"[error]✗ File not found:[/error] {input_file}")
        raise typer.Exit(1)

    hop_str = " → ".join([src] + [s.dst for s in path])
    display_name = input_file if is_url else input_path.name
    if not quiet:
        console.print(Panel.fit(
            f"[bold]{display_name}[/bold] → [bold]{output_file.name}[/bold]\n"
            f"[muted]route:[/muted] {hop_str}"
            + ("  [warning](lossy step involved)[/warning]" if any(s.lossy for s in path) else ""),
            title="morph", border_style="cyan",
        ))

    if dry_run:
        for i, spec in enumerate(path, 1):
            dep = f"  [muted](requires {spec.requires_binary})[/muted]" if spec.requires_binary else ""
            console.print(f"  {i}. {spec.src} → {spec.dst}  [muted]via {spec.backend}[/muted]{dep}")
        raise typer.Exit(0)

    needed = registry.required_binaries(path)
    if needed and not deps.ensure_all(needed, console, assume_yes=yes):
        err_console.print("[error]✗ Required dependency not available — aborting.[/error]")
        raise typer.Exit(1)

    current_input = input_path
    result = None
    t_start = time.perf_counter()
    success = False
    error_msg: Optional[str] = None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, spec in enumerate(path):
                is_last = i == len(path) - 1
                hop_out = output_file if is_last else Path(tmpdir) / f"hop{i}.{spec.dst}"
                hop_options = {opt.name: options_dict[opt.name] for opt in spec.options}
                result = run_hop(spec, current_input, hop_out, hop_options, console, quiet=quiet)
                current_input = result.output
        success = True
    except Exception as exc:
        error_msg = str(exc)
        err_console.print(f"\n[error]✗ Conversion failed at step '{spec.src} → {spec.dst}':[/error] {exc}")
        raise typer.Exit(1)
    finally:
        elapsed = time.perf_counter() - t_start
        backends = ", ".join(dict.fromkeys(s.backend for s in path))
        entry = hist.make_entry(
            input_path, src, output_file, dst,
            hop_str, backends, success, elapsed,
            error=error_msg,
        )
        hist.append_entry(entry)

    if not quiet and result is not None:
        extras = []
        if result.rows is not None:
            extras.append(f"{result.rows:,} rows")
        if result.pages is not None:
            extras.append(f"{result.pages} pages")
        extra_str = f"  ({', '.join(extras)})" if extras else ""
        console.print(f"[success]✓ Done![/success]  → [accent]{output_file}[/accent]{extra_str}\n")


# ── batch ─────────────────────────────────────────────────────────────────────

@app.command(
    "batch",
    help="Convert multiple files in parallel. Last argument is the target format.",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def batch_cmd(
    ctx: typer.Context,
    inputs: List[str] = typer.Argument(..., help="Glob patterns or directories. Last entry is the target format."),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", "-o", help="Output directory (default: alongside input)."),
    mirror: bool = typer.Option(False, "--mirror", help="Mirror input directory structure inside --out-dir."),
    rename: Optional[str] = typer.Option(None, "--rename", help="Filename template, e.g. '{stem}_audio'. Variables: {stem} {fmt} {src_fmt}."),
    workers: int = typer.Option(4, "-w", "--workers", help="Parallel worker threads.", min=1, max=32),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Walk subdirectories."),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip files whose output already exists."),
    newer_only: bool = typer.Option(False, "--newer-only", help="Skip files whose output is already newer than the input."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Abort on first failure."),
    error_log: Optional[Path] = typer.Option(None, "--error-log", help="Write failed paths to this file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be converted without running."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm dependency installs."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="No live display — just print summary."),
) -> None:
    from .batch import collect_inputs, run_batch

    if len(inputs) < 2:
        err_console.print("[error]✗ Provide at least one input pattern and a target format.[/error]")
        err_console.print("  [muted]Example: morph batch '*.mp4' mp3[/muted]")
        raise typer.Exit(1)

    # Last argument is always the target format
    *patterns, target_fmt = inputs
    target_fmt = target_fmt.lower().lstrip(".")

    # Validate target format is known
    if not registry.all_formats() or target_fmt not in registry.all_formats():
        err_console.print(f"[error]✗ Unknown target format:[/error] [bold]{target_fmt}[/bold]")
        known = sorted(registry.all_formats())
        err_console.print(f"[muted]Known formats: {', '.join(known)}[/muted]")
        raise typer.Exit(1)

    # Determine base_dir for --mirror (use common parent of patterns if dir)
    base_dir: Optional[Path] = None
    if mirror and out_dir:
        candidate = Path(patterns[0])
        if candidate.is_dir():
            base_dir = candidate.resolve()

    # Collect jobs
    jobs = collect_inputs(
        patterns, target_fmt,
        recursive=recursive,
        out_dir=out_dir,
        mirror=mirror,
        rename_template=rename,
        skip_existing=skip_existing,
        newer_only=newer_only,
        base_dir=base_dir,
    )

    if not jobs:
        console.print("[warning]No matching files found.[/warning]")
        raise typer.Exit(0)

    # Gather any extra options from ctx.args (passthrough to converters)
    # Parse known converter options for the target format's routes
    from .batch import JobState
    convertible_jobs = [j for j in jobs if j.state == JobState.WAITING and j.conv_path]
    options_dict: dict = {}
    if convertible_jobs:
        sample_path = convertible_jobs[0].conv_path
        combined_opts = registry.combined_options(sample_path)
        if combined_opts and ctx.args:
            parser = _build_parser(combined_opts)
            parsed, _ = parser.parse_known_args(ctx.args)
            options_dict = vars(parsed)

    if dry_run:
        console.print(Panel.fit(
            f"[bold]morph batch — dry run[/bold]\n"
            f"Target: [cyan]{target_fmt}[/cyan]  Workers: {workers}",
            border_style="cyan",
        ))
        from .batch import JobState, _SYMBOLS
        for j in jobs:
            sym = _SYMBOLS.get(j.state, "·")
            if j.state == JobState.WAITING:
                route = " → ".join([j.src_fmt] + [s.dst for s in j.conv_path])
                console.print(f"  {sym} [white]{j.input_path}[/white]  [dim]→ {j.output_path.name}  ({route})[/dim]")
            else:
                console.print(f"  {sym} [dim]{j.input_path}  ({j.error})[/dim]")
        raise typer.Exit(0)

    result = run_batch(
        jobs, target_fmt, options_dict, console,
        workers=workers,
        fail_fast=fail_fast,
        error_log=error_log,
        quiet=quiet,
    )

    raise typer.Exit(0 if result.failed == 0 else 1)


# ── formats ───────────────────────────────────────────────────────────────────

@app.command("formats", help="List formats morph can convert, optionally filtered by source format.")
def formats_cmd(
    source: Optional[str] = typer.Argument(None, help="e.g. 'docx' to see everything reachable from docx."),
) -> None:
    if source:
        # Per-format table (existing behaviour — already good)
        targets = registry.reachable_targets(source)
        if not targets:
            console.print(f"[warning]No known conversions from .{source}[/warning]")
            raise typer.Exit(0)
        tbl = RichTable(box=box.ROUNDED, border_style="cyan")
        tbl.add_column("Target", style="bold white")
        tbl.add_column("Route", style="muted")
        tbl.add_column("Hops", justify="right", style="green")
        for dst, hop_path in sorted(targets.items()):
            hop_str = " → ".join([source] + [s.dst for s in hop_path])
            tbl.add_row(dst, hop_str, str(len(hop_path)))
        console.print(tbl)
        return

    # Tree view grouped by family
    all_formats = registry.all_formats()
    by_family = registry.formats_by_family()
    by_edges = registry.edges_by_family()
    backends = registry.family_backends()

    total_fmts = len(all_formats)
    total_families = len(by_family)

    console.print()
    console.print(f"  [bold cyan]morph[/bold cyan] — [bold]{total_fmts}[/bold] formats across [bold]{total_families}[/bold] families\n")

    # Render each family in defined order, then any unknown ones
    order = [f for f in _FAMILY_ORDER if f in by_family]
    extras = [f for f in sorted(by_family) if f not in order]

    for family in order + extras:
        fmts = sorted(by_family[family])
        edges = by_edges.get(family, [])
        be = sorted(backends.get(family, set()))
        icon = _FAMILY_ICONS.get(family, "▸")
        label = _FAMILY_LABELS.get(family, family)
        be_str = f"via {', '.join(be)}" if be else ""

        tree = Tree(
            f"{icon}  [bold]{label}[/bold]  [dim]({len(fmts)} formats"
            + (f", {be_str}" if be_str else "")
            + f", {len(edges)} direct routes)[/dim]",
            guide_style="dim cyan",
        )

        # Per-format: show top direct targets
        src_targets: dict[str, list[str]] = {}
        for spec in edges:
            src_targets.setdefault(spec.src, []).append(spec.dst)

        fmt_lines = []
        for fmt in fmts:
            targets_for = sorted(src_targets.get(fmt, []))
            if targets_for:
                t_str = "  [dim]→ " + " ".join(targets_for) + "[/dim]"
            else:
                t_str = ""
            fmt_lines.append(f"[bold white]{fmt}[/bold white]{t_str}")

        for line in fmt_lines:
            tree.add(line)

        console.print(tree)

    console.print()
    console.print("  [muted]Run [bold]morph formats <format>[/bold] to see all reachable targets from any format.[/muted]")
    console.print()


# ── history ───────────────────────────────────────────────────────────────────

@app.command("history", help="Show recent conversion history.")
def history_cmd(
    n: int = typer.Option(20, "-n", help="Number of entries to show."),
    failed: bool = typer.Option(False, "--failed", help="Show only failed conversions."),
    fmt: Optional[str] = typer.Option(None, "--fmt", help="Filter by source or target format (e.g. mp4)."),
    clear: bool = typer.Option(False, "--clear", help="Delete the history file."),
    json_out: bool = typer.Option(False, "--json", help="Print raw JSON Lines."),
) -> None:
    from . import history as hist
    import json

    if clear:
        if typer.confirm("Delete all conversion history?"):
            existed = hist.clear()
            console.print("[success]✓ History cleared.[/success]" if existed else "[muted]History was already empty.[/muted]")
        return

    entries = hist.read_entries(limit=n, failed_only=failed, fmt_filter=fmt)

    if not entries:
        console.print("[muted]No history entries found.[/muted]")
        if not hist.HISTORY_FILE.exists():
            console.print(f"[muted]History file: {hist.HISTORY_FILE}[/muted]")
        return

    if json_out:
        from dataclasses import asdict
        for e in entries:
            console.print(json.dumps(asdict(e), ensure_ascii=False))
        return

    # Pretty table
    from datetime import datetime

    def _fmt_time(ts: str) -> str:
        try:
            dt = datetime.fromisoformat(ts)
            now = datetime.now()
            diff = (now - dt).total_seconds()
            if diff < 3600:
                return f"{int(diff // 60)}m ago"
            if diff < 86400:
                return f"{int(diff // 3600)}h ago"
            if diff < 172800:
                return "yesterday"
            return dt.strftime("%b %d")
        except Exception:
            return ts[:16]

    tbl = RichTable(box=box.ROUNDED, border_style="cyan", show_header=True)
    tbl.add_column("When", style="dim", width=11, no_wrap=True)
    tbl.add_column("From", style="bold white", width=7, no_wrap=True)
    tbl.add_column("To", style="bold cyan", width=7, no_wrap=True)
    tbl.add_column("File", style="white", ratio=1, no_wrap=True)
    tbl.add_column("Mode", style="dim", width=7, no_wrap=True)
    tbl.add_column("Status", width=14, no_wrap=True)

    for e in reversed(entries):
        name = Path(e.src_path).name
        if len(name) > 40:
            name = name[:37] + "..."

        if e.success:
            status = f"[green]✓ {e.elapsed_s:.1f}s[/green]"
        else:
            err_short = (e.error or "error")[:20]
            status = f"[red]✗ {err_short}[/red]"

        tbl.add_row(
            _fmt_time(e.ts),
            e.src_fmt, e.dst_fmt,
            name,
            e.mode,
            status,
        )

    title_parts = [f"last {len(entries)}"]
    if failed:
        title_parts.append("failures")
    if fmt:
        title_parts.append(f"format={fmt}")
    title = "morph history — " + ", ".join(title_parts)

    console.print()
    console.print(tbl)

    total = len(entries)
    ok = sum(1 for e in entries if e.success)
    bad = total - ok
    console.print(
        f"  [dim]{total} shown  "
        f"[green]{ok} successful[/green]  "
        + (f"[red]{bad} failed[/red]" if bad else "[dim]0 failed[/dim]")
        + f"  history: {hist.HISTORY_FILE}[/dim]"
    )
    console.print()


# ── deps ──────────────────────────────────────────────────────────────────────

@app.command("deps", help="Check status of external tools morph relies on.")
def deps_cmd() -> None:
    binaries = sorted(registry.known_binaries())
    tbl = RichTable(box=box.ROUNDED, border_style="cyan")
    tbl.add_column("Tool", style="bold white")
    tbl.add_column("Status")
    tbl.add_column("Install command", style="muted")
    for b in binaries:
        status = deps.check(b)
        state = "[success]✓ installed[/success]" if status.installed else "[error]✗ missing[/error]"
        tbl.add_row(b, state, status.install_cmd or "[muted]no package manager detected[/muted]")
    console.print(tbl)


# ── entry point ───────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from .tui import run_tui
        run_tui()


if __name__ == "__main__":
    app()
