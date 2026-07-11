from __future__ import annotations

import json
import math
import os
import re
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


class AudioValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioMeasurement:
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    integrated_lufs: float
    true_peak_dbtp: float


def inspect_wav(path: Path) -> tuple[float, int, int]:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            if wav.getcomptype() != "NONE":
                raise AudioValidationError("WAV must be uncompressed PCM")
            payload = wav.readframes(frames)
    except AudioValidationError:
        raise
    except (wave.Error, OSError, EOFError) as exc:
        raise AudioValidationError("invalid WAV container") from exc

    if channels != 1:
        raise AudioValidationError("WAV must be mono")
    if width != 2:
        raise AudioValidationError("WAV must be PCM-16")
    if frames <= 0:
        raise AudioValidationError("WAV has no frames")
    if rate < 16000 or rate > 48000:
        raise AudioValidationError("WAV sample rate is outside 16-48 kHz")
    if len(payload) != frames * channels * width:
        raise AudioValidationError("WAV frame payload is truncated")

    samples = struct.unpack(f"<{frames}h", payload)
    if max(abs(sample) for sample in samples) >= 32767:
        raise AudioValidationError("WAV is clipped")
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    if rms < 8:
        raise AudioValidationError("WAV is silent")
    return frames / rate, rate, channels


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise AudioValidationError("FFmpeg is required for Qwen WAV finishing") from exc


def _json_object(text: str) -> dict[str, str]:
    matches = re.findall(r"\{[^{}]+\}", text, re.DOTALL)
    if not matches:
        raise AudioValidationError("FFmpeg loudnorm analysis was missing")
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError as exc:
        raise AudioValidationError("FFmpeg loudnorm analysis was invalid") from exc


def _run_loudnorm(source: Path, destination: Path, loudness: float, peak: float) -> None:
    analysis = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(source),
            "-af",
            f"loudnorm=I={loudness}:TP={peak}:LRA=11:print_format=json",
            "-f",
            "null",
            "pipe:1",
        ]
    )
    if analysis.returncode:
        raise AudioValidationError("FFmpeg loudness analysis failed")
    values = _json_object(analysis.stderr + analysis.stdout)
    try:
        filter_value = (
            f"loudnorm=I={loudness}:TP={peak}:LRA=11:"
            f"measured_I={values['input_i']}:measured_TP={values['input_tp']}:"
            f"measured_LRA={values['input_lra']}:"
            f"measured_thresh={values['input_thresh']}:"
            f"offset={values['target_offset']}:linear=true,aresample=24000"
        )
    except KeyError as exc:
        raise AudioValidationError("FFmpeg loudnorm measurements were incomplete") from exc
    finished = _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-i",
            str(source),
            "-af",
            filter_value,
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(destination),
        ]
    )
    if finished.returncode:
        raise AudioValidationError("FFmpeg loudness finishing failed")


def measure_loudness(path: Path) -> tuple[float, float]:
    run = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]
    )
    if run.returncode:
        raise AudioValidationError("FFmpeg EBU R128 measurement failed")
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", run.stderr)
    peaks = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", run.stderr)
    if not integrated or not peaks:
        raise AudioValidationError("FFmpeg measurement summary was missing")
    return float(integrated[-1]), float(peaks[-1])


def finish_qwen_wav(
    source: Path,
    destination: Path,
    *,
    loudness_lufs: float,
    true_peak_dbtp: float,
) -> AudioMeasurement:
    if float(loudness_lufs) != -16.0 or float(true_peak_dbtp) != -1.0:
        raise ValueError("RadioTEDU finishing policy is fixed at -16 LUFS and -1 dBTP")
    if source.resolve() == destination.resolve():
        raise AudioValidationError("source and destination must be different WAV files")

    inspect_wav(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=".qwen-finish-", suffix=".partial.wav"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        _run_loudnorm(source, temporary, -16.0, -1.0)
        duration, rate, channels = inspect_wav(temporary)
        integrated, peak = measure_loudness(temporary)
        if abs(integrated - (-16.0)) > 1.0 or peak > -1.0:
            raise AudioValidationError(
                f"loudness qualification failed: {integrated} LUFS, {peak} dBTP"
            )
        os.replace(temporary, destination)
        return AudioMeasurement(duration, rate, channels, integrated, peak)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
