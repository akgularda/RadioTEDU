from pathlib import Path
from types import SimpleNamespace

from backend.tts.cache import StationTTSCache
from backend.tts.contracts import SynthesisRequest, SynthesisResult, VoiceSelection


def context(tmp_path, station_id, language):
    locale = "en-US" if language == "en" else "fr-FR"
    profile = SimpleNamespace(
        station_id=station_id,
        language=language,
        runtime=SimpleNamespace(cache_root=tmp_path / station_id / "qwen-cache"),
    )
    return SimpleNamespace(profile=profile, locale=locale)


def request(station_id, language, host, *, daypart="station_id", text="RadioTEDU", reference=None):
    locale = "en-US" if language == "en" else "fr-FR"
    pack = "radiotedu-en-voices-v1" if language == "en" else "radiotedu-fr-voices-v1"
    return SynthesisRequest(
        request_id=f"req-{station_id}",
        station_id=station_id,
        language=language,
        locale=locale,
        normalized_text=text,
        announcement_label=daypart,
        voice=VoiceSelection(
            station_id=station_id,
            language=language,
            locale=locale,
            voice_pack=pack,
            host_id=host,
            style_id="energetic_clear",
            clone_prompt_path=f"{host}.pt",
            reference_audio_path=reference or f"{host}.wav",
            reference_transcript="RadioTEDU",
            model_checksum="sha256:" + "a" * 64,
        ),
    )


def result(req, path, key):
    return SynthesisResult(
        request_id=req.request_id,
        station_id=req.station_id,
        output_path=str(path),
        cache_key=key,
        audio_sha256="b" * 64,
        duration_seconds=1.0,
        sample_rate_hz=24000,
        channels=1,
        source="qwen",
    )


def test_cache_key_binds_station_language_host_daypart_text_and_voice_reference(tmp_path):
    cache = StationTTSCache(context(tmp_path, "radiotedu-en", "en"))
    base = request("radiotedu-en", "en", "maya")

    assert cache.key_for(base) != cache.key_for(
        request("radiotedu-en", "en", "maya", daypart="program_open")
    )
    assert cache.key_for(base) != cache.key_for(
        request("radiotedu-en", "en", "maya", text="RadioTEDU news")
    )
    assert cache.key_for(base) != cache.key_for(
        request("radiotedu-en", "en", "maya", reference="maya-approved-v2.wav")
    )
    assert cache.key_for(base) != StationTTSCache(
        context(tmp_path, "radiotedu-fr", "fr")
    ).key_for(request("radiotedu-fr", "fr", "camille"))


def test_put_is_atomic_and_get_copies_valid_entry(tmp_path):
    ctx = context(tmp_path, "radiotedu-en", "en")
    cache, req = StationTTSCache(ctx), request("radiotedu-en", "en", "maya")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFFxxxxWAVEqwen")

    stored = cache.put(req, source, result(req, source, cache.key_for(req)))
    output = tmp_path / "restored.wav"
    hit = cache.get(req, str(output))

    assert hit is not None and hit.source == "qwen-cache"
    assert output.read_bytes() == source.read_bytes()
    assert stored.output_path.endswith(f"{cache.key_for(req)}.wav")
    assert not list(Path(ctx.profile.runtime.cache_root).rglob("*.partial"))


def test_cache_rejects_request_for_another_station(tmp_path):
    cache = StationTTSCache(context(tmp_path, "radiotedu-en", "en"))

    try:
        cache.key_for(request("radiotedu-fr", "fr", "camille"))
    except ValueError as exc:
        assert "station" in str(exc)
    else:
        raise AssertionError("cross-station request reached cache")
