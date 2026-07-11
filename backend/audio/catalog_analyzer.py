"""Offline, read-only ffprobe analysis for catalog candidate audio assets."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Final

from .models import (
    AudioAnalysis,
    AudioAnalyzerUnavailableError,
    AudioAssetMissingError,
    AudioStreamMissingError,
    AudioValidationStatus,
    UnreadableAudioError,
    UnsupportedAudioFormatError,
)


SUPPORTED_AUDIO_EXTENSIONS: Final = frozenset(
    {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
)
SUPPORTED_AUDIO_CODECS: Final = frozenset(
    {
        "aac",
        "alac",
        "flac",
        "mp3",
        "opus",
        "pcm_alaw",
        "pcm_f32be",
        "pcm_f32le",
        "pcm_f64be",
        "pcm_f64le",
        "pcm_mulaw",
        "pcm_s16be",
        "pcm_s16le",
        "pcm_s24be",
        "pcm_s24le",
        "pcm_s32be",
        "pcm_s32le",
        "pcm_s8",
        "pcm_u8",
        "vorbis",
    }
)
FfprobeBinary = str | Path | Sequence[str | Path]


def analyze_audio(
    source_path: str | Path, *, ffprobe_binary: FfprobeBinary = "ffprobe"
) -> AudioAnalysis:
    """Return stable source metadata or raise an error that prevents cataloging.

    This function invokes only ffprobe and reads the source to calculate its
    checksum; it never writes, renames, or normalizes the source asset.
    """

    source = Path(source_path).resolve()
    if not source.is_file():
        raise AudioAssetMissingError("audio source is missing or not a regular file")
    if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise UnsupportedAudioFormatError("audio source uses an unsupported file extension")

    probe_data = _probe(source, ffprobe_binary)
    stream = _audio_stream(probe_data)
    duration_seconds = _duration_seconds(probe_data)
    sample_rate_hz = _positive_int(stream.get("sample_rate"))
    channels = _positive_int(stream.get("channels"))
    codec = stream.get("codec_name")
    if sample_rate_hz is None or channels is None or not isinstance(codec, str) or not codec:
        raise UnreadableAudioError("ffprobe returned incomplete audio metadata")
    if codec not in SUPPORTED_AUDIO_CODECS:
        raise UnreadableAudioError("ffprobe returned unsupported audio codec")

    return AudioAnalysis(
        source_path=source,
        duration_seconds=duration_seconds,
        integrated_lufs=None,
        true_peak_dbtp=None,
        leading_silence_seconds=None,
        trailing_silence_seconds=None,
        cue_in_seconds=None,
        cue_out_seconds=None,
        bpm=None,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        codec=codec,
        checksum_sha256=_checksum_sha256(source),
        validation_status=AudioValidationStatus.VALID,
    )


def _probe(source: Path, ffprobe_binary: FfprobeBinary) -> dict[str, Any]:
    command = [
        *_ffprobe_command(ffprobe_binary),
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,sample_rate,channels",
        "-of",
        "json",
        str(source),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=False, text=True)
    except OSError as error:
        raise AudioAnalyzerUnavailableError("ffprobe is unavailable") from error
    if result.returncode != 0:
        raise UnreadableAudioError("ffprobe could not read audio metadata")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise UnreadableAudioError("ffprobe returned invalid metadata") from error
    if not isinstance(data, dict):
        raise UnreadableAudioError("ffprobe returned invalid metadata")
    return data


def _ffprobe_command(ffprobe_binary: FfprobeBinary) -> list[str]:
    if isinstance(ffprobe_binary, (str, Path)):
        return [str(ffprobe_binary)]
    command = [str(part) for part in ffprobe_binary]
    if not command:
        raise AudioAnalyzerUnavailableError("ffprobe is unavailable")
    return command


def _audio_stream(probe_data: dict[str, Any]) -> dict[str, Any]:
    streams = probe_data.get("streams")
    if not isinstance(streams, list):
        raise AudioStreamMissingError("ffprobe found no audio stream")
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "audio":
            return stream
    raise AudioStreamMissingError("ffprobe found no audio stream")


def _duration_seconds(probe_data: dict[str, Any]) -> float:
    format_data = probe_data.get("format")
    duration = format_data.get("duration") if isinstance(format_data, dict) else None
    parsed_duration = _positive_float(duration)
    if parsed_duration is None:
        raise UnreadableAudioError("ffprobe returned no positive duration")
    return parsed_duration


def _checksum_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    try:
        with source.open("rb") as audio_file:
            for chunk in iter(lambda: audio_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise UnreadableAudioError("audio source could not be read for checksum") from error
    return digest.hexdigest()


def _positive_int(value: object) -> int | None:
    try:
        parsed_value = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed_value if parsed_value > 0 else None


def _positive_float(value: object) -> float | None:
    try:
        parsed_value = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed_value if math.isfinite(parsed_value) and parsed_value > 0 else None
