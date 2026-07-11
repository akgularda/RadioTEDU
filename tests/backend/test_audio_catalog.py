from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path

import pytest

from backend.audio.catalog_analyzer import analyze_audio
from backend.audio.models import (
    AudioAssetMissingError,
    AudioValidationStatus,
    BROADCAST_AUDIO_POLICY,
    UnreadableAudioError,
    UnsupportedAudioFormatError,
)


def _write_wave(path: Path) -> None:
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(8_000)
        audio_file.writeframes(b"\x00\x00" * 800)


def _write_ffprobe_fixture(
    path: Path, duration: str, *, codec: str = "pcm_s16le"
) -> tuple[str, str]:
    metadata = {
        "format": {"duration": duration},
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": codec,
                "sample_rate": "8000",
                "channels": 1,
            }
        ],
    }
    path.write_text(
        f"print({json.dumps(metadata)!r})\n",
        encoding="utf-8",
    )
    return (sys.executable, str(path))


def test_broadcast_audio_policy_freezes_professional_qualification_inputs() -> None:
    assert BROADCAST_AUDIO_POLICY.integrated_lufs_target == -16.0
    assert BROADCAST_AUDIO_POLICY.integrated_lufs_tolerance_lu == 1.0
    assert BROADCAST_AUDIO_POLICY.true_peak_ceiling_dbtp == -1.0
    assert BROADCAST_AUDIO_POLICY.silence_threshold_dbfs == -60.0
    assert BROADCAST_AUDIO_POLICY.silence_degraded_primary_seconds == 1.0
    assert BROADCAST_AUDIO_POLICY.silence_fallback_seconds == 1.5
    assert BROADCAST_AUDIO_POLICY.listener_visible_silence_limit_seconds == 2.0
    assert BROADCAST_AUDIO_POLICY.talk_over_minimum_intro_confidence == 0.85
    assert BROADCAST_AUDIO_POLICY.talk_over_minimum_instrumental_intro_seconds == 3.0
    assert BROADCAST_AUDIO_POLICY.speech_target_before_intro_end_seconds == 0.5
    assert BROADCAST_AUDIO_POLICY.speech_target_before_intro_end_min_seconds == 0.3
    assert BROADCAST_AUDIO_POLICY.speech_target_before_intro_end_max_seconds == 0.7


def test_analyze_audio_returns_deterministic_metadata_without_changing_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "station-id.wav"
    _write_wave(source)
    original_bytes = source.read_bytes()

    analysis = analyze_audio(source)

    assert analysis.source_path == source.resolve()
    assert analysis.duration_seconds == pytest.approx(0.1)
    assert analysis.sample_rate_hz == 8_000
    assert analysis.channels == 1
    assert analysis.codec == "pcm_s16le"
    assert analysis.checksum_sha256 == hashlib.sha256(original_bytes).hexdigest()
    assert analysis.validation_status is AudioValidationStatus.VALID
    assert source.read_bytes() == original_bytes


@pytest.mark.parametrize("duration", ["inf", "-inf", "nan"])
def test_analyze_audio_rejects_non_finite_ffprobe_duration(
    tmp_path: Path, duration: str
) -> None:
    source = tmp_path / "station-id.wav"
    fixture = tmp_path / "ffprobe_fixture.py"
    _write_wave(source)
    command = _write_ffprobe_fixture(fixture, duration)

    with pytest.raises(UnreadableAudioError, match="positive duration"):
        analyze_audio(source, ffprobe_binary=command)


def test_analyze_audio_rejects_unsupported_ffprobe_codec(tmp_path: Path) -> None:
    source = tmp_path / "station-id.wav"
    fixture = tmp_path / "ffprobe_fixture.py"
    _write_wave(source)
    command = _write_ffprobe_fixture(fixture, "0.1", codec="garbage")

    with pytest.raises(UnreadableAudioError, match="unsupported audio codec"):
        analyze_audio(source, ffprobe_binary=command)


def test_analyze_audio_rejects_missing_source(tmp_path: Path) -> None:
    with pytest.raises(AudioAssetMissingError):
        analyze_audio(tmp_path / "missing.wav")


def test_analyze_audio_rejects_malformed_audio(tmp_path: Path) -> None:
    source = tmp_path / "malformed.wav"
    source.write_bytes(b"not a wave file")

    with pytest.raises(UnreadableAudioError):
        analyze_audio(source)


def test_analyze_audio_rejects_unsupported_file_type(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not audio", encoding="utf-8")

    with pytest.raises(UnsupportedAudioFormatError):
        analyze_audio(source)
