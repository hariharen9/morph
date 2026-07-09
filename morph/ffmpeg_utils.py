"""
ffmpeg_utils.py — shared ffmpeg execution with live progress reporting.

ffmpeg supports `-progress pipe:1`, which streams machine-readable
`key=value` lines as it works (out_time_ms=..., speed=..., progress=end).
Combined with the total duration from ffprobe, that's enough to compute a
real fractional progress — not just a spinner — for every audio/video hop.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Callable[[float, str], None]


def probe_duration(path: Path) -> Optional[float]:
    """Total duration in seconds, via ffprobe. None if it can't be determined
    (e.g. some live/streamed inputs) — callers fall back to a spinner."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def run_ffmpeg(cmd: list[str], *, input_path: Optional[Path] = None,
               progress: Optional[ProgressCallback] = None) -> None:
    """Run an ffmpeg command. `cmd[0]` must be 'ffmpeg'.

    If `progress` is given, streams -progress output and calls
    `progress(fraction_0_to_1, status_text)` as it becomes known. Falls back
    to a single call at frac=None-equivalent (never called) if duration is
    unavailable — the caller should already be showing an indeterminate
    spinner in that case, this just upgrades it when it can.
    """
    if progress is None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = "\n".join(result.stderr.strip().splitlines()[-6:])
            raise RuntimeError(f"ffmpeg failed:\n{tail}")
        return

    total = probe_duration(input_path) if input_path else None
    live_cmd = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]

    proc = subprocess.Popen(live_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, bufsize=1)
    speed = ""
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key == "speed":
                speed = value.strip()
            elif key == "out_time_ms" and total:
                try:
                    seconds = int(value) / 1_000_000
                    frac = max(0.0, min(seconds / total, 1.0))
                    progress(frac, speed)
                except ValueError:
                    pass
            elif key == "progress" and value == "end":
                progress(1.0, speed)
    finally:
        stderr_output = proc.stderr.read() if proc.stderr else ""
        proc.wait()

    if proc.returncode != 0:
        tail = "\n".join(stderr_output.strip().splitlines()[-6:])
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
