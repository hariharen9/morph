"""
deps.py — detects and (with explicit confirmation) installs external binaries
that converters shell out to, like pandoc and ffmpeg.

Design rules:
  • morph NEVER installs anything silently. Every install shows the exact
    command first and asks for a yes.
  • morph NEVER auto-elevates. If a command needs sudo, it's part of the
    printed command — the user sees it and approves it explicitly.
  • Package manager + package name are resolved per-OS, since binary names
    differ (e.g. ffmpeg on winget is "Gyan.FFmpeg", not "ffmpeg").
"""

from __future__ import annotations

import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# ── package manager registry ──────────────────────────────────────────────

# order matters: first found wins on a given OS
_MANAGERS_BY_OS = {
    "Darwin":  ["brew", "port"],
    "Linux":   ["apt", "dnf", "pacman", "zypper", "apk"],
    "Windows": ["winget", "choco", "scoop"],
}

_INSTALL_CMD = {
    "brew":   "brew install {pkg}",
    "port":   "sudo port install {pkg}",
    "apt":    "sudo apt install -y {pkg}",
    "dnf":    "sudo dnf install -y {pkg}",
    "pacman": "sudo pacman -S --noconfirm {pkg}",
    "zypper": "sudo zypper install -y {pkg}",
    "apk":    "sudo apk add {pkg}",
    "winget": "winget install --id {pkg} -e",
    "choco":  "choco install {pkg} -y",
    "scoop":  "scoop install {pkg}",
}

# binary -> {package_manager: package_name}, only where it differs from the binary name
_PACKAGE_NAMES: dict[str, dict[str, str]] = {
    "ffmpeg": {"winget": "Gyan.FFmpeg", "scoop": "ffmpeg"},
    "pandoc": {"winget": "JohnMacFarlane.Pandoc"},
    "ebook-convert": {
        "apt": "calibre", "dnf": "calibre", "pacman": "calibre",
        "brew": "calibre", "winget": "calibre.calibre", "choco": "calibre",
    },
    "soffice": {  # LibreOffice headless binary
        "apt": "libreoffice", "dnf": "libreoffice", "pacman": "libreoffice-fresh",
        "brew": "libreoffice", "winget": "TheDocumentFoundation.LibreOffice",
        "choco": "libreoffice-fresh",
    },
}

# extra one-line context shown to the user about *why* they need this
_WHY = {
    "pandoc": "converts between document formats (docx, md, html, epub, ...)",
    "ffmpeg": "converts audio and video files",
    "soffice": "converts legacy office formats pandoc can't read directly",
    "wkhtmltopdf": "renders documents to PDF (a lightweight PDF engine)",
    "xelatex": "renders documents to PDF with full LaTeX/typography support",
    "ebook-convert": "converts ebook formats (epub, mobi, azw3) — ships as part of Calibre",
}


@dataclass
class DependencyStatus:
    binary: str
    installed: bool
    manager: Optional[str]
    install_cmd: Optional[str]


def detect_package_manager() -> Optional[str]:
    system = platform.system()
    for mgr in _MANAGERS_BY_OS.get(system, []):
        if shutil.which(mgr):
            return mgr
    return None


def is_installed(binary: str) -> bool:
    return shutil.which(binary) is not None


def check(binary: str) -> DependencyStatus:
    if is_installed(binary):
        return DependencyStatus(binary, True, None, None)
    mgr = detect_package_manager()
    if not mgr:
        return DependencyStatus(binary, False, None, None)
    pkg = _PACKAGE_NAMES.get(binary, {}).get(mgr, binary)
    cmd = _INSTALL_CMD[mgr].format(pkg=pkg)
    return DependencyStatus(binary, False, mgr, cmd)


def ensure(binary: str, console: Optional[Console] = None, *, assume_yes: bool = False) -> bool:
    """
    Make sure `binary` is available, prompting to install it if not.
    Returns True if the binary is usable by the time this returns.

    assume_yes=True skips the confirmation prompt (e.g. `morph convert -y`)
    but morph still ALWAYS shows the exact command before running it — the
    only thing -y skips is the interactive "are you sure?", never visibility.
    """
    console = console or Console()
    status = check(binary)
    if status.installed:
        return True

    why = _WHY.get(binary, "is required for this conversion")
    if not status.manager:
        console.print(Panel.fit(
            f"[warning]{binary}[/warning] {why}, but it isn't installed and "
            f"morph couldn't find a supported package manager on this system.\n\n"
            f"Install it manually, then re-run this command.",
            title="Missing dependency", border_style="yellow",
        ))
        return False

    console.print(Panel.fit(
        f"[bold white]{binary}[/bold white] {why}, but it isn't installed.\n\n"
        f"morph can install it with:\n  [accent]{status.install_cmd}[/accent]",
        title="Missing dependency", border_style="yellow",
    ))

    if not assume_yes and not Confirm.ask("Run this now?", default=True):
        console.print(f"[muted]Skipped. Install it yourself with:[/muted] {status.install_cmd}")
        return False

    console.print(f"[info]→ running:[/info] {status.install_cmd}")
    try:
        result = subprocess.run(shlex.split(status.install_cmd))
    except FileNotFoundError as e:
        console.print(f"[error]✗ Could not run installer:[/error] {e}")
        return False

    if result.returncode != 0:
        console.print(f"[error]✗ Install command exited with status {result.returncode}[/error]")
        return False

    if is_installed(binary):
        console.print(f"[success]✓ {binary} installed successfully[/success]")
        return True

    console.print(f"[error]✗ Install finished but {binary} still isn't on PATH.[/error]")
    return False


def ensure_all(binaries: list[str], console: Optional[Console] = None, *, assume_yes: bool = False) -> bool:
    """Ensure every binary in the list is available. Stops at first failure."""
    return all(ensure(b, console, assume_yes=assume_yes) for b in binaries)
