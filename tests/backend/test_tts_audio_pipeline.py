import math
import struct
import wave

import pytest

from backend.tts.audio_pipeline import AudioValidationError, finish_qwen_wav, inspect_wav


def write_tone(path, amplitude=9000, seconds=1.0, rate=24000, channels=1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = [
            int(amplitude * math.sin(2 * math.pi * 440 * index / rate))
            for index in range(int(rate * seconds))
        ]
        wav.writeframes(
            b"".join(
                struct.pack("<h", frame) * channels
                for frame in frames
            )
        )


def test_inspect_rejects_silent_stereo_clipped_and_empty_wav(tmp_path):
    silent = tmp_path / "silent.wav"
    write_tone(silent, amplitude=0)
    with pytest.raises(AudioValidationError, match="silent"):
        inspect_wav(silent)

    stereo = tmp_path / "stereo.wav"
    write_tone(stereo, channels=2)
    with pytest.raises(AudioValidationError, match="mono"):
        inspect_wav(stereo)

    clipped = tmp_path / "clipped.wav"
    with wave.open(str(clipped), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(struct.pack("<h", 32767) * 24000)
    with pytest.raises(AudioValidationError, match="clipped"):
        inspect_wav(clipped)

    empty = tmp_path / "empty.wav"
    with wave.open(str(empty), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"")
    with pytest.raises(AudioValidationError, match="frames"):
        inspect_wav(empty)


def test_finish_targets_minus_16_lufs_and_minus_1_dbtp_without_mutating_source(
    tmp_path, monkeypatch
):
    source, destination = tmp_path / "raw.wav", tmp_path / "finished.wav"
    write_tone(source)
    source_before = source.read_bytes()
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "pipe:1":
            return type(
                "Run",
                (),
                {
                    "returncode": 0,
                    "stdout": (
                        '{"input_i":"-24.00","input_tp":"-6.00",'
                        '"input_lra":"2.00","input_thresh":"-34.00",'
                        '"target_offset":"0.00"}'
                    ),
                    "stderr": "",
                },
            )()
        temporary = command[-1]
        with open(temporary, "wb") as output:
            output.write(source_before)
        return type("Run", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("backend.tts.audio_pipeline.subprocess.run", fake_run)
    monkeypatch.setattr(
        "backend.tts.audio_pipeline.measure_loudness", lambda path: (-16.0, -1.0)
    )

    measurement = finish_qwen_wav(
        source, destination, loudness_lufs=-16, true_peak_dbtp=-1
    )

    assert measurement.integrated_lufs == -16.0
    assert measurement.true_peak_dbtp == -1.0
    assert source.read_bytes() == source_before
    assert destination.read_bytes() == source_before
    assert any(
        "I=-16.0:TP=-1.0" in part for command in calls for part in command
    )


def test_finish_rejects_output_outside_qualification_tolerance(tmp_path, monkeypatch):
    source, destination = tmp_path / "raw.wav", tmp_path / "finished.wav"
    write_tone(source)
    source_before = source.read_bytes()
    monkeypatch.setattr(
        "backend.tts.audio_pipeline._run_loudnorm",
        lambda raw, temporary, *_: temporary.write_bytes(raw.read_bytes()),
    )
    monkeypatch.setattr(
        "backend.tts.audio_pipeline.measure_loudness", lambda path: (-14.8, -0.4)
    )

    with pytest.raises(AudioValidationError, match="loudness"):
        finish_qwen_wav(source, destination, loudness_lufs=-16, true_peak_dbtp=-1)

    assert source.read_bytes() == source_before
    assert not destination.exists()
