"""
converters/audio.py — audio family, powered by ffmpeg.

ffmpeg picks a sensible default codec per container from the output
extension alone in almost all cases, so the base conversion needs no
codec-specific logic — options here just override the defaults.

Every hop reports real fractional progress (not just a spinner) via
ffmpeg's -progress stream, parsed in ffmpeg_utils.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..ffmpeg_utils import ProgressCallback, run_ffmpeg
from ..registry import ConversionResult, OptionSpec, register

FORMATS = ["mp3", "wav", "flac", "ogg", "aac", "m4a", "opus", "wma"]

OPTIONS = [
    OptionSpec("bitrate", ("-b", "--bitrate"), "Audio bitrate, e.g. '192k'. Default: ffmpeg's per-codec default."),
    OptionSpec("sample_rate", ("--sample-rate",), "Output sample rate in Hz, e.g. 44100.", type=int),
    OptionSpec("channels", ("--channels",), "Output channel count: 1 (mono) or 2 (stereo).", type=int),
]


def _audio_convert(input_path: Path, output_path: Path, *, bitrate: Optional[str] = None,
                    sample_rate: Optional[int] = None, channels: Optional[int] = None,
                    _progress: Optional[ProgressCallback] = None, **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(input_path)]
    if bitrate:
        cmd += ["-b:a", bitrate]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    if channels:
        cmd += ["-ac", str(channels)]
    cmd.append(str(output_path))
    run_ffmpeg(cmd, input_path=input_path, progress=_progress)
    return ConversionResult(output=output_path)


for _src in FORMATS:
    for _dst in FORMATS:
        if _dst == _src:
            continue
        register(
            _src, _dst,
            backend="ffmpeg",
            requires_binary="ffmpeg",
            family="audio",
            description=f"{_src} → {_dst} (ffmpeg)",
            lossy=(_dst in ("mp3", "aac", "ogg", "m4a")),
            options=OPTIONS,
            supports_progress=True,
        )(_audio_convert)
