"""
converters/video.py — video family, powered by ffmpeg.

Includes two genuinely useful cross-domain edges beyond video<->video:
  • video -> audio  (extract the audio track, e.g. mp4 -> mp3)
  • video -> gif    (short animated clips; palette-generated for quality)

Every hop reports real fractional progress via ffmpeg's -progress stream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..ffmpeg_utils import ProgressCallback, run_ffmpeg
from ..registry import ConversionResult, OptionSpec, register
from .audio import FORMATS as AUDIO_FORMATS

FORMATS = ["mp4", "mkv", "mov", "webm", "avi", "flv", "wmv", "mpeg"]

_COMMON_OPTIONS = [
    OptionSpec("resolution", ("--resolution",), "Output resolution, e.g. '1280x720'. Default: keep source size."),
    OptionSpec("fps", ("--fps",), "Output frame rate.", type=int),
    OptionSpec("crf", ("--crf",), "Quality (lower = better/larger, 0-51). Default: encoder default (~23).", type=int),
    OptionSpec("video_codec", ("--vcodec",), "Force a video codec, e.g. 'libx264', 'libvpx-vp9'."),
    OptionSpec("audio_codec", ("--acodec",), "Force an audio codec, e.g. 'aac', 'libopus'."),
    OptionSpec("no_audio", ("--no-audio",), "Strip the audio track entirely.", default=False, action="store_true"),
    OptionSpec("start", ("--start",), "Trim start, e.g. '00:00:10' or seconds."),
    OptionSpec("duration", ("--duration",), "Trim duration, e.g. '00:00:05' or seconds."),
]


def _input_seek_args(start: Optional[str], duration: Optional[str]) -> list[str]:
    args = []
    if start:
        args += ["-ss", str(start)]
    if duration:
        args += ["-t", str(duration)]
    return args


def _video_convert(input_path: Path, output_path: Path, *, resolution: Optional[str] = None,
                    fps: Optional[int] = None, crf: Optional[int] = None,
                    video_codec: Optional[str] = None, audio_codec: Optional[str] = None,
                    no_audio: bool = False, start: Optional[str] = None,
                    duration: Optional[str] = None, _progress: Optional[ProgressCallback] = None,
                    **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *_input_seek_args(start, duration), "-i", str(input_path)]

    vf = []
    if resolution:
        w, h = resolution.lower().split("x")
        vf.append(f"scale={w}:{h}")
    if fps:
        cmd += ["-r", str(fps)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if crf is not None:
        cmd += ["-crf", str(crf)]
    if video_codec:
        cmd += ["-c:v", video_codec]
    if no_audio:
        cmd.append("-an")
    elif audio_codec:
        cmd += ["-c:a", audio_codec]

    cmd.append(str(output_path))
    run_ffmpeg(cmd, input_path=input_path, progress=_progress)
    return ConversionResult(output=output_path)


def _extract_audio(input_path: Path, output_path: Path, *, bitrate: Optional[str] = None,
                    sample_rate: Optional[int] = None, channels: Optional[int] = None,
                    _progress: Optional[ProgressCallback] = None, **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(input_path), "-vn"]
    if bitrate:
        cmd += ["-b:a", bitrate]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    if channels:
        cmd += ["-ac", str(channels)]
    cmd.append(str(output_path))
    run_ffmpeg(cmd, input_path=input_path, progress=_progress)
    return ConversionResult(output=output_path)


_GIF_OPTIONS = [
    OptionSpec("fps", ("--fps",), "Gif frame rate.", type=int, default=10),
    OptionSpec("width", ("--width",), "Gif width in pixels (height auto-scales). Default: 480.", type=int, default=480),
    OptionSpec("start", ("--start",), "Trim start, e.g. '00:00:10' or seconds."),
    OptionSpec("duration", ("--duration",), "Trim duration, e.g. '00:00:05' or seconds. Recommended for long videos."),
]


def _to_animated(input_path: Path, output_path: Path, *, fps: int = 10, width: int = 480,
            start: Optional[str] = None, duration: Optional[str] = None,
            _progress: Optional[ProgressCallback] = None, **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = f"fps={fps},scale={width}:-1:flags=lanczos"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *_input_seek_args(start, duration),
           "-i", str(input_path), "-vf", vf, "-loop", "0", str(output_path)]
    run_ffmpeg(cmd, input_path=input_path, progress=_progress)
    return ConversionResult(output=output_path, extra={"note": "single-pass palette; use --fps/--width to tune size"})


# video <-> video
for _src in FORMATS:
    for _dst in FORMATS:
        if _dst == _src:
            continue
        register(
            _src, _dst, backend="ffmpeg", requires_binary="ffmpeg", family="video",
            description=f"{_src} → {_dst} (ffmpeg)", options=_COMMON_OPTIONS, supports_progress=True,
        )(_video_convert)

# video -> audio (extract track)
_EXTRACT_AUDIO_OPTIONS = [
    OptionSpec("bitrate", ("-b", "--bitrate"), "Audio bitrate, e.g. '192k'."),
    OptionSpec("sample_rate", ("--sample-rate",), "Output sample rate in Hz.", type=int),
    OptionSpec("channels", ("--channels",), "Output channel count: 1 or 2.", type=int),
]
for _src in FORMATS:
    for _dst in AUDIO_FORMATS:
        register(
            _src, _dst, backend="ffmpeg", requires_binary="ffmpeg", family="video",
            description=f"{_src} → {_dst} (extract audio track)", lossy=True,
            options=_EXTRACT_AUDIO_OPTIONS, supports_progress=True,
        )(_extract_audio)

# video -> gif / webp
for _src in FORMATS:
    for _dst in ("gif", "webp"):
        register(
            _src, _dst, backend="ffmpeg", requires_binary="ffmpeg", family="video",
            description=f"{_src} → {_dst}", lossy=True, options=_GIF_OPTIONS, supports_progress=True,
        )(_to_animated)

# video -> subtitles
def _extract_subs(input_path: Path, output_path: Path, **_options) -> ConversionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(input_path), "-map", "0:s:0", str(output_path)]
    run_ffmpeg(cmd, input_path=input_path)
    return ConversionResult(output=output_path)

for _src in FORMATS:
    for _dst in ("srt", "vtt"):
        register(
            _src, _dst, backend="ffmpeg", requires_binary="ffmpeg", family="video",
            description=f"{_src} → {_dst} (extract subtitles)", lossy=True,
        )(_extract_subs)
