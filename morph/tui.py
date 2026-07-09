"""
tui.py — morph's fully keyboard-driven interactive mode.

Navigation:
  [f]           focus the file input from anywhere
  [↓]           open filesystem autocomplete dropdown from file input
  [↑↓]          navigate suggestions or the format list
  [Enter]       confirm (file path, suggestion, format)
  [Esc]         close the autocomplete dropdown
  [Tab]         cycle focus: file → formats → options → convert → file
  [Shift+Tab]   reverse cycle
  [c]           convert (when not typing in a text field)
  [q]           quit

The options panel updates live as you move through the format list —
no need to press Enter just to preview what flags are available.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Header, Input, Label, ListItem, ListView, Log,
    ProgressBar, Static, Switch,
)

from . import converters  # noqa: F401  — registers all converters at import time
from . import deps
from .registry import ConverterSpec, OptionSpec, detect_format, registry


# ─────────────────────────────────────────────────────────────────────────────
# Autocomplete suggestion list
# ─────────────────────────────────────────────────────────────────────────────

class SuggestionList(ListView):
    """
    ListView that emits custom messages instead of silently eating Esc
    and ↑-at-top, so PathInput can return focus to the Input on both.
    """

    class Escaped(Message):
        """Esc pressed while dropdown is focused."""

    class UpAtTop(Message):
        """↑ pressed while already at the first item."""

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.post_message(self.Escaped())
            event.stop()
        elif event.key == "up" and (self.index is None or self.index == 0):
            self.post_message(self.UpAtTop())
            event.stop()


class SuggestionItem(ListItem):
    def __init__(self, path: Path) -> None:
        is_dir = path.is_dir()
        icon = "📁" if is_dir else "📄"
        name = path.name + ("/" if is_dir else "")
        markup = f"{icon} [bold]{name}[/bold]" if is_dir else f"{icon} {name}"
        super().__init__(Label(markup))
        self.suggestion_path = path


# ─────────────────────────────────────────────────────────────────────────────
# PathInput — file input with live filesystem autocomplete
# ─────────────────────────────────────────────────────────────────────────────

class PathInput(Vertical):
    """
    Composite widget: a single-line Input + a SuggestionList dropdown.

    Keyboard contract
    ─────────────────
    ↓  (Input focused)    open + focus dropdown
    ↑↓ (dropdown)         navigate entries
    ↑  at first entry     close dropdown, return to Input
    Enter (dropdown)      dirs → navigate into; files → confirm and close
    Esc (dropdown)        close dropdown, return to Input
    Enter (Input)         confirm whatever is typed (no autocomplete needed)
    """

    class FileConfirmed(Message):
        """Emitted when the user has committed a concrete file path."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="path/to/file  (↓ for autocomplete)",
            id="path_field",
        )
        yield SuggestionList(id="suggestions", classes="dropdown")

    def on_mount(self) -> None:
        self._dropdown_open = False
        self.query_one("#suggestions", SuggestionList).display = False

    # ── suggestion population ─────────────────────────────────────────────────

    @on(Input.Changed, "#path_field")
    def _on_text_changed(self, event: Input.Changed) -> None:
        self._populate(event.value)

    def _populate(self, text: str) -> None:
        lv = self.query_one("#suggestions", SuggestionList)
        lv.clear()
        if not text.strip():
            self._close()
            return
        try:
            p = Path(text).expanduser()
            if text[-1] in "/\\":
                parent, stem = p, ""
            else:
                parent, stem = p.parent, p.name.lower()
            if not parent.is_dir():
                self._close()
                return
            hits = sorted(
                [c for c in parent.iterdir() if c.name.lower().startswith(stem)],
                key=lambda c: (c.is_file(), c.name.lower()),
            )[:8]
            if not hits:
                self._close()
                return
            for h in hits:
                lv.append(SuggestionItem(h))
            self._open()
        except Exception:
            self._close()

    def _open(self) -> None:
        self.query_one("#suggestions", SuggestionList).display = True
        self._dropdown_open = True

    def _close(self) -> None:
        self.query_one("#suggestions", SuggestionList).display = False
        self._dropdown_open = False

    # ── key handling ──────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        inp = self.query_one("#path_field", Input)
        if not inp.has_focus:
            return
        if event.key == "down":
            self._populate(inp.value)
            if self._dropdown_open:
                lv = self.query_one("#suggestions", SuggestionList)
                lv.index = 0
                lv.focus()
                event.stop()
        elif event.key == "enter":
            self._close()
            path = Path(inp.value.strip()).expanduser()
            self.post_message(self.FileConfirmed(path))
            event.stop()

    # ── dropdown → Input coordination ─────────────────────────────────────────

    def on_suggestion_list_escaped(self, _: SuggestionList.Escaped) -> None:
        self._close()
        self.query_one("#path_field", Input).focus()

    def on_suggestion_list_up_at_top(self, _: SuggestionList.UpAtTop) -> None:
        self._close()
        self.query_one("#path_field", Input).focus()

    @on(ListView.Selected, "#suggestions")
    def _on_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, SuggestionItem):
            return
        p = item.suggestion_path
        inp = self.query_one("#path_field", Input)
        if p.is_dir():
            # Navigate into the directory — keep dropdown open with new contents
            inp.value = str(p) + "/"
            inp.cursor_position = len(inp.value)
            self._close()
            inp.focus()
            self._populate(inp.value)
        else:
            inp.value = str(p)
            inp.cursor_position = len(inp.value)
            self._close()
            inp.focus()
            self.post_message(self.FileConfirmed(p))

    # ── public api ───────────────────────────────────────────────────────────

    def focus_input(self) -> None:
        self.query_one("#path_field", Input).focus()

    @property
    def current_value(self) -> str:
        return self.query_one("#path_field", Input).value


# ─────────────────────────────────────────────────────────────────────────────
# Format list item
# ─────────────────────────────────────────────────────────────────────────────

class FormatItem(ListItem):
    def __init__(self, fmt: str, hops: int, route: str) -> None:
        hop_tag = f"  [dim]{hops} hops[/dim]" if hops > 1 else ""
        super().__init__(Label(f"[bold]{fmt:<8}[/bold] [dim]{route}[/dim]{hop_tag}"))
        self.fmt = fmt


# ─────────────────────────────────────────────────────────────────────────────
# Option row — one OptionSpec rendered as a labeled input or switch
# ─────────────────────────────────────────────────────────────────────────────

class OptionRow(Horizontal):
    def __init__(self, opt: OptionSpec) -> None:
        super().__init__(classes="option-row")
        self.opt = opt

    def compose(self) -> ComposeResult:
        flag = self.opt.flags[-1]
        yield Label(flag, classes="option-label")
        if self.opt.action in ("store_true", "store_false"):
            default_on = bool(self.opt.default) if self.opt.action == "store_true" else False
            yield Switch(value=default_on, id=f"opt_{self.opt.name}")
        else:
            placeholder = str(self.opt.default) if self.opt.default is not None else ""
            yield Input(
                placeholder=placeholder,
                id=f"opt_{self.opt.name}",
                classes="opt-input",
            )
        yield Label(f"[dim]{self.opt.help}[/dim]", classes="option-help")

    def current_value(self) -> object:
        if self.opt.action in ("store_true", "store_false"):
            on = self.query_one(Switch).value
            return on if self.opt.action == "store_true" else (
                not on if on else self.opt.default
            )
        raw = self.query_one(Input).value.strip()
        if not raw:
            return self.opt.default
        try:
            if self.opt.type is int:
                return int(raw)
            if self.opt.type is float:
                return float(raw)
        except ValueError:
            return self.opt.default
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# Install confirm modal — fully keyboard navigable
# ─────────────────────────────────────────────────────────────────────────────

class InstallConfirmModal(ModalScreen[bool]):
    """
    Blocks until the user accepts or rejects a dep install.
    Once accepted, streams the installer output live.
    Keys: [Enter] → install, [Esc] → cancel.
    """

    DEFAULT_CSS = """
    InstallConfirmModal { align: center middle; }
    #modal_box {
        width: 72; height: auto; max-height: 26;
        border: heavy #d29922;
        padding: 1 2;
        background: #161b22;
    }
    #modal_log {
        height: 8; margin-top: 1;
        border: round #30363d;
        background: #0d1117;
    }
    #modal_btns { height: auto; margin-top: 1; align: right middle; }
    #btn_install { margin-left: 1; }
    """
    BINDINGS = [
        Binding("escape", "do_cancel", "Cancel"),
        Binding("enter", "do_install", "Install"),
    ]

    def __init__(self, binary: str, status) -> None:
        super().__init__()
        self.binary = binary
        self.status = status

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_box"):
            yield Static(
                f"[bold yellow]{self.binary}[/bold yellow] is required but not installed.\n\n"
                f"morph will run:\n  [cyan]{self.status.install_cmd}[/cyan]\n\n"
                f"[dim]  Enter → install    Esc → cancel[/dim]"
            )
            yield Log(id="modal_log", classes="hidden")
            with Horizontal(id="modal_btns"):
                yield Button("Cancel  (Esc)", id="btn_cancel", variant="default")
                yield Button("Install  (Enter)", id="btn_install", variant="warning")

    def action_do_cancel(self) -> None:
        self.dismiss(False)

    def action_do_install(self) -> None:
        self._run_install()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_install":
            self._run_install()

    @work(thread=True)
    def _run_install(self) -> None:
        log = self.query_one("#modal_log", Log)
        self.call_from_thread(log.remove_class, "hidden")
        btn = self.query_one("#btn_install", Button)
        self.call_from_thread(btn.__setattr__, "disabled", True)

        proc = subprocess.Popen(
            self.status.install_cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            self.call_from_thread(log.write_line, line.rstrip())
        proc.wait()

        ok = proc.returncode == 0 and deps.is_installed(self.binary)
        self.call_from_thread(log.write_line, "✓ done" if ok else "✗ install failed")
        self.call_from_thread(self.dismiss, ok)


# ─────────────────────────────────────────────────────────────────────────────
# Context-sensitive status bar hints
# ─────────────────────────────────────────────────────────────────────────────

_HINTS: dict[str, str] = {
    "path_field":     "  ↓ autocomplete   Enter confirm   Tab jump to formats   q quit",
    "suggestions":    "  ↑↓ navigate   Enter select   Esc cancel",
    "target_list":    "  ↑↓ navigate (options update live)   Enter jump to options   c convert   q quit",
    "options_scroll": "  Tab next field   Shift+Tab prev   c convert   q quit",
    "convert_btn":    "  Enter / c convert   Shift+Tab back to options   q quit",
    "_default":       "  f file input   Tab next panel   c convert   q quit",
}


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class MorphApp(App):

    CSS = """
    /* ── base ──────────────────────────────────────────────────────────── */
    Screen {
        background: #0d1117;
        layout: vertical;
    }
    Header {
        background: #161b22;
        color: #58a6ff;
        text-style: bold;
    }

    /* ── file section ───────────────────────────────────────────────────── */
    #file_section {
        height: auto;
        padding: 1 2 0 2;
    }
    #file_label {
        color: #8b949e;
        padding: 0 1;
        text-style: bold;
        margin-bottom: 0;
    }
    PathInput { height: auto; }
    #path_field {
        background: #161b22;
        border: tall #30363d;
        color: #c9d1d9;
    }
    #path_field:focus { border: tall #58a6ff; }
    .dropdown {
        background: #0d1117;
        border: round #21262d;
        height: auto;
        max-height: 9;
    }
    .dropdown > ListItem          { padding: 0 1; color: #c9d1d9; }
    .dropdown > ListItem.--highlight { background: #1f3d6e; color: #79c0ff; }

    /* ── body ───────────────────────────────────────────────────────────── */
    #body {
        height: 1fr;
        padding: 1 2;
    }

    /* ── format panel ───────────────────────────────────────────────────── */
    #formats_panel {
        width: 38%;
        border: round #30363d;
        background: #161b22;
        margin-right: 1;
    }
    #formats_panel:focus-within { border: heavy #58a6ff; }
    #formats_label {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
        width: 100%;
    }
    #target_list { background: #161b22; }
    #target_list > ListItem          { padding: 0 1; color: #c9d1d9; }
    #target_list > ListItem.--highlight { background: #1f3d6e; color: #79c0ff; }

    /* ── right panel ────────────────────────────────────────────────────── */
    #right_panel { width: 62%; layout: vertical; }

    /* options block */
    #options_block {
        height: auto;
        border: round #30363d;
        background: #161b22;
        margin-bottom: 1;
    }
    #options_block:focus-within { border: heavy #58a6ff; }
    #options_label {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
        width: 100%;
    }
    #options_scroll {
        height: auto;
        max-height: 13;
        padding: 0 1;
    }
    #no_opts_msg { color: #6e7681; padding: 1; }

    .option-row   { height: 3; align: left middle; }
    .option-label { width: 22; color: #8b949e; text-style: bold; }
    .opt-input {
        width: 18;
        background: #0d1117;
        border: tall #30363d;
        color: #c9d1d9;
    }
    .opt-input:focus { border: tall #58a6ff; }
    Switch        { margin: 0 1; }
    .option-help  { color: #6e7681; margin-left: 1; width: 1fr; }

    /* convert row */
    #convert_row { height: 3; padding: 0 1; align: right middle; }
    #convert_btn {
        background: #238636;
        color: #ffffff;
        text-style: bold;
        min-width: 20;
        border: tall #2ea043;
    }
    #convert_btn:focus  { background: #2ea043; border: tall #3fb950; }
    #convert_btn:disabled { background: #21262d; color: #484f58; border: tall #30363d; }

    /* ── log panel ──────────────────────────────────────────────────────── */
    #log_panel {
        border: round #30363d;
        background: #161b22;
        height: 1fr;
    }
    #log_label {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
        width: 100%;
    }
    #progress_bar { margin: 0 1; }
    #log_view     { padding: 0 1; }

    /* ── status bar ─────────────────────────────────────────────────────── */
    #status_bar {
        height: 1;
        background: #21262d;
        color: #6e7681;
        padding: 0 1;
        dock: bottom;
    }

    .hidden { display: none; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("f", "focus_file", "File", show=False),
        Binding("c", "convert", "Convert", show=False),
    ]

    # ── reactive state ────────────────────────────────────────────────────────
    input_file:   reactive[str]  = reactive("")
    src_format:   reactive[str]  = reactive("")
    selected_dst: reactive[str]  = reactive("")
    current_path: reactive[list] = reactive(list)

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # File input + autocomplete
        with Vertical(id="file_section"):
            yield Label("SOURCE FILE", id="file_label")
            yield PathInput(id="path_input_widget")

        # Main body
        with Horizontal(id="body"):
            # Left — format list
            with Vertical(id="formats_panel"):
                yield Label(" TARGET FORMAT", id="formats_label")
                yield ListView(id="target_list")

            # Right — options + log
            with Vertical(id="right_panel"):
                # Options block
                with Vertical(id="options_block"):
                    yield Label(" OPTIONS", id="options_label")
                    with VerticalScroll(id="options_scroll"):
                        yield Static(
                            "[dim]Select a target format to see its options.[/dim]",
                            id="no_opts_msg",
                        )
                    with Horizontal(id="convert_row"):
                        yield Button(
                            "  Convert  (c)",
                            id="convert_btn",
                            variant="success",
                            disabled=True,
                        )
                # Log block
                with Vertical(id="log_panel"):
                    yield Label(" LOG", id="log_label")
                    yield ProgressBar(id="progress_bar", classes="hidden")
                    yield Log(id="log_view")

        yield Static("", id="status_bar")

    def on_mount(self) -> None:
        log = self.query_one("#log_view", Log)
        log.write_line("morph  —  keyboard-first file converter")
        log.write_line("type a file path above, then press ↓ for autocomplete or Enter to confirm")
        self.query_one(PathInput).focus_input()
        self._set_hint("path_field")

    # ── status bar ────────────────────────────────────────────────────────────

    def _set_hint(self, widget_id: str) -> None:
        self.query_one("#status_bar", Static).update(
            _HINTS.get(widget_id, _HINTS["_default"])
        )

    def watch_focused(self, focused) -> None:
        """Update the status bar hint whenever focus moves."""
        if focused is not None:
            self._set_hint(focused.id or "_default")

    # ── file confirmed ────────────────────────────────────────────────────────

    @on(PathInput.FileConfirmed)
    def _on_file_confirmed(self, event: PathInput.FileConfirmed) -> None:
        path = event.path
        log = self.query_one("#log_view", Log)
        target_list = self.query_one("#target_list", ListView)

        # Reset state
        target_list.clear()
        self._clear_options()
        self.query_one("#convert_btn", Button).disabled = True
        self.selected_dst = ""
        self.current_path = []

        if not path.exists():
            log.write_line(f"  ✗  Not found: {path}")
            return
        if path.is_dir():
            log.write_line(f"  ✗  That's a directory: {path}")
            return

        src = detect_format(path)
        self.input_file = str(path)
        self.src_format = src
        reachable = registry.reachable_targets(src)

        if not reachable:
            log.write_line(f"  ✗  No known conversions from .{src}")
            return

        log.write_line(
            f"  ✓  {path.name}  [{src}]  →  {len(reachable)} reachable format(s)"
        )
        for dst, hop_path in sorted(reachable.items()):
            route = " → ".join([src] + [s.dst for s in hop_path])
            target_list.append(FormatItem(dst, len(hop_path), route))

        # Jump focus to the format list
        self.query_one("#target_list", ListView).focus()

    # ── format list — live options update on highlight ────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Options panel updates live as the user arrows through formats."""
        if event.list_view.id != "target_list":
            return
        item = event.item
        if not isinstance(item, FormatItem) or not self.input_file:
            return
        self._load_format(item.fmt, jump_focus=False)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a format → load options AND jump focus to the options panel."""
        if event.list_view.id != "target_list":
            return
        item = event.item
        if not isinstance(item, FormatItem) or not self.input_file:
            return
        self._load_format(item.fmt, jump_focus=True)

    def _load_format(self, fmt: str, *, jump_focus: bool = False) -> None:
        conv_path = registry.find_path(self.src_format, fmt)
        if conv_path is None:
            return
        self.selected_dst = fmt
        self.current_path = conv_path

        # Re-render options panel
        self._clear_options()
        scroll = self.query_one("#options_scroll", VerticalScroll)
        no_msg = self.query_one("#no_opts_msg", Static)
        combined = registry.combined_options(conv_path)

        if combined:
            no_msg.display = False
            for opt in combined:
                scroll.mount(OptionRow(opt))
        else:
            no_msg.display = True
            no_msg.update("[dim]No extra options for this conversion.[/dim]")

        self.query_one("#convert_btn", Button).disabled = False

        # Log the route (only on first select to avoid log spam on highlight)
        if jump_focus:
            log = self.query_one("#log_view", Log)
            hop_str = " → ".join([self.src_format] + [s.dst for s in conv_path])
            lossy_tag = "  [dim](lossy)[/dim]" if any(s.lossy for s in conv_path) else ""
            log.write_line(f"  route: {hop_str}{lossy_tag}")
            self.query_one("#options_scroll", VerticalScroll).focus()

    def _clear_options(self) -> None:
        scroll = self.query_one("#options_scroll", VerticalScroll)
        for row in list(scroll.query(OptionRow)):
            row.remove()

    # ── convert ───────────────────────────────────────────────────────────────

    def action_convert(self) -> None:
        # Don't intercept 'c' typed into a text Input field
        if isinstance(self.focused, Input):
            return
        if not self.current_path or not self.input_file:
            self.query_one("#log_view", Log).write_line(
                "  Select a file and a target format first."
            )
            return
        self._convert_worker()

    def action_focus_file(self) -> None:
        self.query_one(PathInput).focus_input()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "convert_btn":
            # Direct button press — always allowed
            if not self.current_path or not self.input_file:
                return
            self._convert_worker()

    def _collect_options(self) -> dict:
        return {row.opt.name: row.current_value() for row in self.query(OptionRow)}

    @work(thread=True)
    def _convert_worker(self) -> None:
        log = self.query_one("#log_view", Log)
        path: list[ConverterSpec] = self.current_path
        options = self._collect_options()
        input_path = Path(self.input_file)
        output_path = input_path.with_suffix(f".{path[-1].dst}")

        # ── dependency check ─────────────────────────────────────────────────
        needed = registry.required_binaries(path)
        for binary in needed:
            status = deps.check(binary)
            if status.installed:
                continue
            if not status.manager:
                self.call_from_thread(
                    log.write_line,
                    f"  ✗  {binary} not found — install it manually and retry.",
                )
                return
            confirmed = self.call_from_thread(self._ask_install, binary, status)
            if not confirmed:
                self.call_from_thread(log.write_line, f"  Skipped — {binary} is required.")
                return

        # ── conversion ───────────────────────────────────────────────────────
        self.call_from_thread(
            log.write_line,
            f"\n  ▶ {input_path.name}  →  {output_path.name}",
        )
        bar = self.query_one(ProgressBar)
        self.call_from_thread(bar.remove_class, "hidden")

        current_input = input_path
        try:
            for i, spec in enumerate(path):
                is_last = i == len(path) - 1
                hop_out = (
                    output_path if is_last
                    else input_path.with_suffix(f".hop{i}.{spec.dst}")
                )
                hop_options = {opt.name: options.get(opt.name) for opt in spec.options}

                # Progress callback (only wired for specs that support it)
                def _cb(frac: float, _s: str, _bar=bar) -> None:
                    self.call_from_thread(_bar.update, progress=frac * 100)

                if spec.supports_progress:
                    self.call_from_thread(bar.update, total=100, progress=0)
                    hop_options["_progress"] = _cb
                else:
                    self.call_from_thread(bar.update, total=None, progress=0)

                self.call_from_thread(
                    log.write_line,
                    f"    {spec.src} → {spec.dst}  via {spec.backend}",
                )
                result = spec.func(current_input, hop_out, **hop_options)
                current_input = result.output

                if spec.supports_progress:
                    self.call_from_thread(bar.update, total=100, progress=100)

        except Exception as exc:
            self.call_from_thread(log.write_line, f"  ✗  Failed: {exc}")
            self.call_from_thread(bar.add_class, "hidden")
            return

        self.call_from_thread(log.write_line, f"  ✓  Done  →  {output_path}\n")
        self.call_from_thread(bar.add_class, "hidden")

    def _ask_install(self, binary: str, status) -> bool:
        # push_screen_wait blocks the worker thread while the modal runs on the
        # UI thread — that's exactly what we want before touching a required binary.
        return self.push_screen_wait(InstallConfirmModal(binary, status))


# ─────────────────────────────────────────────────────────────────────────────

def run_tui() -> None:
    MorphApp().run()


if __name__ == "__main__":
    run_tui()
