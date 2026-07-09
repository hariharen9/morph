#!/usr/bin/env python3
"""
morph — convert anything to anything, from the CLI.

  morph report.docx report.pdf
  morph data.csv data.xlsx --table-style TableStyleMedium2 --header-bg 2E7D32
  morph data.csv data.xlsx --help      (shows flags for THIS pair only)
  morph formats docx
  morph deps
  morph                                 (no args -> launches the interactive TUI)

There is no "convert" subcommand — morph already means convert. Anything
that isn't a recognized subcommand (formats, deps) is treated as a
conversion job and routed through the engine.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.theme import Theme
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


class MorphGroup(TyperGroup):
    """Makes `morph <file> <file> [flags]` work without a literal 'convert'
    subcommand: if the first token isn't a known subcommand name, it's
    forwarded to the hidden `run` command, which does the actual routing."""

    def resolve_command(self, ctx, args):
        if args and args[0] not in self.commands:
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


def _fmt_of(path: Path) -> str:
    return detect_format(path)


def _print_route_help(input_file: Path, output_file: Path, path) -> None:
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


@app.command("run", hidden=True, context_settings={"ignore_unknown_options": True, "allow_extra_args": True, "help_option_names": []})
def run_cmd(
    ctx: typer.Context,
    input_file: Path = typer.Argument(..., help="Source file."),
    output_file: Path = typer.Argument(..., help="Destination file (extension picks the target format)."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm dependency installs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the conversion plan without running it."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress banners and tables."),
) -> None:
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
    parsed, unknown = parser.parse_known_args(ctx.args)
    if unknown:
        err_console.print(f"[warning]⚠ Ignoring unrecognized option(s):[/warning] {' '.join(unknown)}")
    options_dict = vars(parsed)

    if not input_file.exists():
        err_console.print(f"[error]✗ File not found:[/error] {input_file}")
        raise typer.Exit(1)

    hop_str = " → ".join([src] + [s.dst for s in path])
    if not quiet:
        console.print(Panel.fit(
            f"[bold]{input_file.name}[/bold] → [bold]{output_file.name}[/bold]\n"
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

    current_input = input_file
    result = None
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, spec in enumerate(path):
                is_last = i == len(path) - 1
                hop_out = output_file if is_last else Path(tmpdir) / f"hop{i}.{spec.dst}"
                hop_options = {opt.name: options_dict[opt.name] for opt in spec.options}
                result = run_hop(spec, current_input, hop_out, hop_options, console, quiet=quiet)
                current_input = result.output
    except Exception as exc:
        err_console.print(f"\n[error]✗ Conversion failed at step '{spec.src} → {spec.dst}':[/error] {exc}")
        raise typer.Exit(1)

    if not quiet and result is not None:
        extras = []
        if result.rows is not None:
            extras.append(f"{result.rows:,} rows")
        if result.pages is not None:
            extras.append(f"{result.pages} pages")
        extra_str = f"  ({', '.join(extras)})" if extras else ""
        console.print(f"[success]✓ Done![/success]  → [accent]{output_file}[/accent]{extra_str}\n")


@app.command("formats", help="List formats morph can convert, optionally filtered by source format.")
def formats_cmd(source: Optional[str] = typer.Argument(None, help="e.g. 'docx' to see everything reachable from docx.")) -> None:
    if source:
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
    else:
        fmts = sorted(registry.all_formats())
        console.print(Panel.fit(", ".join(fmts), title=f"{len(fmts)} known formats", border_style="cyan"))
        console.print("[muted]Run `morph formats <format>` to see everything reachable from it.[/muted]")


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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from .tui import run_tui
        run_tui()


if __name__ == "__main__":
    app()
