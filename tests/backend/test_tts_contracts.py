import pytest
from pydantic import ValidationError

from backend.tts.contracts import (
    SynthesisRequest,
    SynthesisResult,
    VoiceSelection,
    cache_identity_payload,
)


def voice(**overrides):
    values = {
        "station_id": "radiotedu-en",
        "language": "en",
        "locale": "en-US",
        "voice_pack": "radiotedu-en-voices-v1",
        "host_id": "maya",
        "style_id": "energetic_clear",
        "clone_prompt_path": "voices/radiotedu-en/maya/clone.pt",
        "reference_audio_path": "voices/radiotedu-en/maya/reference.wav",
        "reference_transcript": "Good morning. You are listening to RadioTEDU.",
        "model_checksum": "sha256:" + "a" * 64,
    }
    values.update(overrides)
    return VoiceSelection.model_validate(values)


def request(**overrides):
    values = {
        "request_id": "req-001",
        "station_id": "radiotedu-en",
        "language": "en",
        "locale": "en-US",
        "normalized_text": "Good morning, Ankara.",
        "announcement_label": "station_id",
        "voice": voice(),
    }
    values.update(overrides)
    return SynthesisRequest.model_validate(values)


def test_request_rejects_cross_station_voice():
    with pytest.raises(ValidationError, match="voice station_id must match"):
        request(voice=voice(station_id="radiotedu-fr", language="fr", locale="fr-FR"))


def test_request_rejects_unknown_fields_and_blank_text():
    with pytest.raises(ValidationError):
        SynthesisRequest.model_validate(
            {**request().model_dump(), "normalized_text": "   ", "voice_instruction": "whisper"}
        )


def test_cache_identity_contains_every_isolation_field():
    identity = cache_identity_payload(request())
    assert identity == {
        "station_id": "radiotedu-en",
        "language": "en",
        "locale": "en-US",
        "voice_pack": "radiotedu-en-voices-v1",
        "host_id": "maya",
        "style_id": "energetic_clear",
        "normalized_text": "Good morning, Ankara.",
        "model_checksum": "sha256:" + "a" * 64,
        "finishing_policy_version": "radiotedu-wav-v1",
    }


def test_result_requires_mono_qwen_source():
    result = SynthesisResult(
        request_id="req-001",
        station_id="radiotedu-en",
        output_path="clip.wav",
        cache_key="b" * 64,
        audio_sha256="c" * 64,
        duration_seconds=2.4,
        sample_rate_hz=24000,
        channels=1,
        source="qwen",
    )
    assert result.channels == 1
    with pytest.raises(ValidationError):
        SynthesisResult.model_validate({**result.model_dump(), "source": "sapi"})
