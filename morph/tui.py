"""
tui.py — morph's interactive mode.

"Best of both worlds": a real full-screen Textual app (mouse support, live
panels, keyboard-driven) that stays lightweight — no file-manager browsing,
no nested screens for simple jobs. Type a path, pick a target format from
what's actually reachable, hit enter, watch it run. Dependency prompts and
the conversion engine are the exact same code path as `morph convert`.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from . import deps
from . import converters  # noqa: F401
from .registry import detect_format, registry


class FormatItem(ListItem):
    def __init__(self, fmt: str, hops: int, route: str) -> None:
        super().__init__(Label(f"{fmt:<8} {route}" + ("" if hops == 1 else f"   [{hops} hops]")))
        self.fmt = fmt


class MorphApp(App):
    CSS = """
    Screen { layout: vertical; }
    #top { height: auto; padding: 1 2; border: round $accent; }
    #body { height: 1fr; }
    #targets { width: 40%; border: round $primary; }
    #log { width: 60%; border: round $primary; }
    #input_row { height: 3; }
    Input { width: 1fr; }
    #convert_btn { width: auto; margin-left: 1; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("enter", "noop", "")]

    input_file: reactive[str] = reactive("")
    src_format: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="top"):
            yield Label("[bold]morph[/bold] — point at a file, pick where it goes")
            with Horizontal(id="input_row"):
                yield Input(placeholder="path/to/file.docx", id="file_input")
        with Horizontal(id="body"):
            with VerticalScroll(id="targets"):
                yield Label("[bold]Reachable formats[/bold]", id="targets_label")
                yield ListView(id="target_list")
            with VerticalScroll(id="log"):
                yield RichLog(id="log_view", wrap=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log_view", RichLog).write(
            "[dim]Type a file path above and press Enter to see what morph can convert it to.[/dim]"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path = Path(event.value).expanduser()
        log = self.query_one("#log_view", RichLog)
        target_list = self.query_one("#target_list", ListView)
        target_list.clear()

        if not path.exists():
            log.write(f"[red]File not found: {path}[/red]")
            return

        src = detect_format(path)
        self.input_file = str(path)
        self.src_format = src
        reachable = registry.reachable_targets(src)

        if not reachable:
            log.write(f"[yellow]No known conversions from .{src} yet.[/yellow]")
            return

        log.write(f"[green]{path.name}[/green] — {len(reachable)} reachable format(s). Pick one →")
        for dst, hop_path in sorted(reachable.items()):
            route = " → ".join([src] + [s.dst for s in hop_path])
            target_list.append(FormatItem(dst, len(hop_path), route))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, FormatItem) or not self.input_file:
            return
        self._run_conversion(Path(self.input_file), item.fmt)

    def _run_conversion(self, input_path: Path, dst_fmt: str) -> None:
        log = self.query_one("#log_view", RichLog)
        path = registry.find_path(self.src_format, dst_fmt)
        if path is None:
            log.write(f"[red]No route to .{dst_fmt}[/red]")
            return

        output_path = input_path.with_suffix(f".{path[-1].dst}")
        needed = registry.required_binaries(path)

        for binary in needed:
            status = deps.check(binary)
            if not status.installed:
                if status.manager is None:
                    log.write(f"[red]{binary} missing and no package manager found — install it manually.[/red]")
                    return
                log.write(f"[yellow]{binary} is required but not installed.[/yellow]")
                log.write(f"[dim]Install command:[/dim] {status.install_cmd}")
                log.write("[dim]Run this in a terminal, then retry from here — the TUI won't auto-run "
                          "installer commands without a visible confirmation, and this panel can't prompt "
                          "for one safely mid-render.[/dim]")
                return

        log.write(f"[cyan]Converting[/cyan] {input_path.name} → {output_path.name} "
                  f"[dim]({' → '.join([self.src_format] + [s.dst for s in path])})[/dim] ...")

        current_input = input_path
        try:
            for i, spec in enumerate(path):
                is_last = i == len(path) - 1
                hop_out = output_path if is_last else input_path.with_suffix(f".hop{i}.{spec.dst}")
                result = spec.func(current_input, hop_out)
                current_input = result.output
        except Exception as exc:
            log.write(f"[red]✗ Failed: {exc}[/red]")
            return

        log.write(f"[green]✓ Done → {output_path}[/green]")


def run_tui() -> None:
    MorphApp().run()


if __name__ == "__main__":
    run_tui()
