"""
tui.py — morph's interactive mode.

A full Textual app with real per-conversion controls: pick a file, pick a
target format, adjust that pair's actual flags (built from the same
OptionSpecs the CLI uses — nothing is hand-duplicated), watch a live
progress bar while it runs, and get prompted before morph installs anything.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem, ListView, Log,
    ProgressBar, Static, Switch,
)

from . import deps
from . import converters  # noqa: F401  (auto-discovers & registers every converter)
from .ffmpeg_utils import ProgressCallback
from .registry import ConverterSpec, OptionSpec, detect_format, registry


class FormatItem(ListItem):
    def __init__(self, fmt: str, hops: int, route: str) -> None:
        super().__init__(Label(f"{fmt:<8} {route}" + ("" if hops == 1 else f"   [dim]{hops} hops[/dim]")))
        self.fmt = fmt


class OptionRow(Horizontal):
    """One flag from an OptionSpec, rendered as a labeled input or switch."""

    def __init__(self, opt: OptionSpec) -> None:
        super().__init__(classes="option-row")
        self.opt = opt

    def compose(self) -> ComposeResult:
        yield Label(self._label_text(), classes="option-label")
        if self.opt.action in ("store_true", "store_false"):
            yield Switch(value=bool(self.opt.default) if self.opt.action == "store_true" else False,
                         id=f"opt_{self.opt.name}")
        else:
            yield Input(placeholder=str(self.opt.default) if self.opt.default is not None else "",
                       id=f"opt_{self.opt.name}")

    def _label_text(self) -> str:
        flag = self.opt.flags[-1]
        return f"{flag}"

    def value(self) -> object:
        if self.opt.action in ("store_true", "store_false"):
            switch = self.query_one(Switch)
            on = switch.value
            if self.opt.action == "store_true":
                return on
            return (not on) if on else self.opt.default  # store_false: default True, switch flips it off
        raw = self.query_one(Input).value.strip()
        if not raw:
            return self.opt.default
        if self.opt.type is int:
            try:
                return int(raw)
            except ValueError:
                return self.opt.default
        if self.opt.type is float:
            try:
                return float(raw)
            except ValueError:
                return self.opt.default
        return raw


class InstallConfirmModal(ModalScreen[bool]):
    """Blocks on a yes/no before morph installs anything, with live command
    output streamed in once confirmed — same "always ask, always show the
    command" principle as the CLI, just rendered as a modal."""

    DEFAULT_CSS = """
    InstallConfirmModal { align: center middle; }
    #modal_box { width: 70; height: auto; max-height: 20; border: round $warning; padding: 1 2; background: $surface; }
    #modal_log { height: 8; margin-top: 1; border: round $primary; }
    #modal_buttons { height: auto; margin-top: 1; align: right middle; }
    """

    def __init__(self, binary: str, status) -> None:
        super().__init__()
        self.binary = binary
        self.status = status
        self._log: Optional[Log] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_box"):
            yield Static(
                f"[bold]{self.binary}[/bold] is required but not installed.\n\n"
                f"morph can install it with:\n  [cyan]{self.status.install_cmd}[/cyan]"
            )
            yield Log(id="modal_log", classes="hidden")
            with Horizontal(id="modal_buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Install", id="install", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        self._run_install()

    @work(thread=True)
    def _run_install(self) -> None:
        log = self.query_one("#modal_log", Log)
        self.call_from_thread(lambda: setattr(log, "classes", ""))
        self.call_from_thread(self.query_one("#install", Button).__setattr__, "disabled", True)
        proc = subprocess.Popen(self.status.install_cmd, shell=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            self.call_from_thread(log.write_line, line.rstrip())
        proc.wait()
        success = proc.returncode == 0 and deps.is_installed(self.binary)
        self.call_from_thread(log.write_line, "✓ done" if success else "✗ install failed")
        self.call_from_thread(self.dismiss, success)


class MorphApp(App):
    CSS = """
    Screen { layout: vertical; }
    #top { height: auto; padding: 1 2; border: round $accent; }
    #body { height: 1fr; }
    #left { width: 38%; border: round $primary; }
    #right { width: 62%; border: round $primary; }
    #options_panel { height: auto; padding: 1; }
    .option-row { height: 3; align: left middle; }
    .option-label { width: 22; color: $text-muted; }
    #convert_row { height: auto; padding: 1; align: right middle; }
    #progress_bar { margin: 1 1 0 1; }
    .hidden { display: none; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("c", "convert", "Convert")]

    input_file: reactive[str] = reactive("")
    src_format: reactive[str] = reactive("")
    selected_dst: reactive[str] = reactive("")
    current_path: reactive[list] = reactive(list)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="top"):
            yield Label("[bold]morph[/bold] — point at a file, pick where it goes, tune the flags")
            yield Input(placeholder="path/to/file.docx", id="file_input")
        with Horizontal(id="body"):
            with VerticalScroll(id="left"):
                yield Label("[bold]Reachable formats[/bold]")
                yield ListView(id="target_list")
            with VerticalScroll(id="right"):
                yield Label("[bold]Options[/bold]", id="options_title")
                yield Vertical(id="options_panel")
                with Horizontal(id="convert_row"):
                    yield Button("Convert", id="convert_btn", variant="success", disabled=True)
                yield ProgressBar(id="progress_bar", classes="hidden")
                yield Log(id="log_view", classes="")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log_view", Log).write_line(
            "Type a file path above and press Enter to see what morph can convert it to."
        )

    # ── file input -> reachable targets ─────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "file_input":
            return
        path = Path(event.value).expanduser()
        log = self.query_one("#log_view", Log)
        target_list = self.query_one("#target_list", ListView)
        target_list.clear()
        self.query_one("#options_panel", Vertical).remove_children()
        self.query_one("#convert_btn", Button).disabled = True

        if not path.exists():
            log.write_line(f"✗ File not found: {path}")
            return

        src = detect_format(path)
        self.input_file = str(path)
        self.src_format = src
        reachable = registry.reachable_targets(src)

        if not reachable:
            log.write_line(f"No known conversions from .{src} yet.")
            return

        log.write_line(f"{path.name} — {len(reachable)} reachable format(s). Pick one on the left →")
        for dst, hop_path in sorted(reachable.items()):
            route = " → ".join([src] + [s.dst for s in hop_path])
            target_list.append(FormatItem(dst, len(hop_path), route))

    # ── target selection -> dynamic options form ────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, FormatItem) or not self.input_file:
            return
        self.selected_dst = item.fmt
        path = registry.find_path(self.src_format, item.fmt)
        if path is None:
            return
        self.current_path = path

        panel = self.query_one("#options_panel", Vertical)
        panel.remove_children()
        combined = registry.combined_options(path)
        if combined:
            for opt in combined:
                panel.mount(OptionRow(opt))
        else:
            panel.mount(Static("[dim]No extra options for this pair.[/dim]"))

        self.query_one("#convert_btn", Button).disabled = False
        log = self.query_one("#log_view", Log)
        hop_str = " → ".join([self.src_format] + [s.dst for s in path])
        log.write_line(f"Selected: {hop_str}" + ("  (lossy step involved)" if any(s.lossy for s in path) else ""))

    # ── conversion ───────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "convert_btn":
            self.action_convert()

    def action_convert(self) -> None:
        if not self.current_path or not self.input_file:
            return
        self._convert_worker()

    def _collect_options(self) -> dict:
        values = {}
        for row in self.query(OptionRow):
            values[row.opt.name] = row.value()
        return values

    @work(thread=True)
    def _convert_worker(self) -> None:
        log = self.query_one("#log_view", Log)
        path: list[ConverterSpec] = self.current_path
        options = self._collect_options()
        input_path = Path(self.input_file)
        output_path = input_path.with_suffix(f".{path[-1].dst}")

        needed = registry.required_binaries(path)
        for binary in needed:
            status = deps.check(binary)
            if status.installed:
                continue
            if not status.manager:
                self.call_from_thread(log.write_line, f"✗ {binary} missing and no package manager found.")
                return
            confirmed = self.call_from_thread(self._ask_install, binary, status)
            if not confirmed:
                self.call_from_thread(log.write_line, f"Skipped — {binary} still required.")
                return

        self.call_from_thread(log.write_line, f"Converting {input_path.name} → {output_path.name} ...")
        bar = self.query_one(ProgressBar)
        self.call_from_thread(lambda: setattr(bar, "classes", ""))

        current_input = input_path
        try:
            for i, spec in enumerate(path):
                is_last = i == len(path) - 1
                hop_out = output_path if is_last else input_path.with_suffix(f".hop{i}.{spec.dst}")
                hop_options = {opt.name: options.get(opt.name) for opt in spec.options}

                def _on_progress(frac: float, status_text: str, _bar=bar) -> None:
                    self.call_from_thread(_bar.update, progress=frac * 100)

                if spec.supports_progress:
                    self.call_from_thread(bar.update, total=100, progress=0)
                    hop_options["_progress"] = _on_progress
                else:
                    # no per-hop progress signal available (pandoc, Pillow, ...) —
                    # total=None puts the bar in Textual's real indeterminate mode
                    # rather than us faking a percentage we don't have.
                    self.call_from_thread(bar.update, total=None, progress=0)

                self.call_from_thread(log.write_line, f"  → {spec.src} → {spec.dst}  (via {spec.backend})")
                result = spec.func(current_input, hop_out, **hop_options)
                current_input = result.output
                if spec.supports_progress:
                    self.call_from_thread(bar.update, total=100, progress=100)
        except Exception as exc:
            self.call_from_thread(log.write_line, f"✗ Failed: {exc}")
            self.call_from_thread(lambda: setattr(bar, "classes", "hidden"))
            return

        self.call_from_thread(log.write_line, f"✓ Done → {output_path}")
        self.call_from_thread(lambda: setattr(bar, "classes", "hidden"))

    def _ask_install(self, binary: str, status) -> bool:
        # Textual worker threads can't `await` a screen directly; push_screen_wait
        # blocks the *calling* thread (this worker) while the modal runs on the
        # UI thread — exactly what we want here.
        return self.push_screen_wait(InstallConfirmModal(binary, status))


def run_tui() -> None:
    MorphApp().run()


if __name__ == "__main__":
    run_tui()
