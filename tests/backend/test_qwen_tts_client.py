import hashlib
import io
import wave
from types import SimpleNamespace

import httpx
import pytest

from backend.tts.contracts import QwenUnavailableError, SynthesisRequest, VoiceSelection
from backend.tts.factory import build_tts_provider
from backend.tts.qwen_tts import QwenTTSProvider


def context():
    return SimpleNamespace(
        profile=SimpleNamespace(station_id="radiotedu-en", language="en", locale="en-US")
    )


def request() -> SynthesisRequest:
    return SynthesisRequest(
        request_id="req-client-1",
        station_id="radiotedu-en",
        language="en",
        locale="en-US",
        normalized_text="Good morning.",
        announcement_label="station_id",
        voice=VoiceSelection(
            station_id="radiotedu-en",
            language="en",
            locale="en-US",
            voice_pack="radiotedu-en-voices-v1",
            host_id="maya",
            style_id="energetic_clear",
            clone_prompt_path="maya.pt",
            reference_audio_path="maya.wav",
            reference_transcript="Good morning.",
            model_checksum="sha256:" + "a" * 64,
        ),
    )


def wav_bytes() -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x01\x00" * 2400)
    return target.getvalue()


def test_client_retries_once_then_raises_without_fallback(tmp_path) -> None:
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"detail": "Qwen synthesis failed"})

    provider = QwenTTSProvider(
        context(), "http://127.0.0.1:8090", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(QwenUnavailableError, match="failed after 2 attempts"):
        provider.synthesize_request(request(), str(tmp_path / "clip.wav"))
    assert calls == 2
    assert not (tmp_path / "clip.wav").exists()
    assert provider.provider_name == "qwen"


def test_client_writes_only_valid_qwen_wav(tmp_path) -> None:
    payload = wav_bytes()

    def handler(http_request):
        assert http_request.url.path == "/v1/synthesize"
        return httpx.Response(
            200,
            content=payload,
            headers={
                "content-type": "audio/wav",
                "x-audio-sha256": hashlib.sha256(payload).hexdigest(),
                "x-sample-rate-hz": "24000",
                "x-model-checksum": "sha256:" + "a" * 64,
            },
        )

    provider = QwenTTSProvider(
        context(), "http://127.0.0.1:8090", transport=httpx.MockTransport(handler)
    )
    result = provider.synthesize_request(request(), str(tmp_path / "clip.wav"))
    assert result.source == "qwen"
    assert (tmp_path / "clip.wav").read_bytes() == payload


def test_client_refuses_cross_station_request_before_network_access(tmp_path) -> None:
    provider = QwenTTSProvider(
        context(),
        "http://127.0.0.1:8090",
        transport=httpx.MockTransport(lambda request: pytest.fail("request must not reach service")),
    )
    cross_station = request().model_copy(update={"station_id": "radiotedu-fr", "language": "fr", "locale": "fr-FR"})
    with pytest.raises(ValueError, match="does not belong to provider station"):
        provider.synthesize_request(cross_station, str(tmp_path / "clip.wav"))


def test_client_timeout_retries_once_then_reports_qwen_unavailable(tmp_path) -> None:
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("Qwen service timed out", request=http_request)

    provider = QwenTTSProvider(
        context(), "http://127.0.0.1:8090", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(QwenUnavailableError, match="failed after 2 attempts"):
        provider.synthesize_request(request(), str(tmp_path / "clip.wav"))
    assert calls == 2
    assert provider.last_error is not None


def test_client_health_reports_local_qwen_service_state() -> None:
    provider = QwenTTSProvider(
        context(),
        "http://127.0.0.1:8090",
        transport=httpx.MockTransport(
            lambda http_request: httpx.Response(
                200,
                json={
                    "status": "ready",
                    "warmed": True,
                    "model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                    "model_checksum": "sha256:" + "a" * 64,
                    "last_error": None,
                },
            )
        ),
    )
    health = provider.health()
    assert health["provider"] == "qwen"
    assert health["status"] == "ready"
    assert health["warmed"] is True


def test_factory_has_no_provider_or_fallback_choice() -> None:
    provider = build_tts_provider(context(), "http://127.0.0.1:8090")
    assert isinstance(provider, QwenTTSProvider)
    assert not hasattr(provider, "fallback")
