# RadioTEDU Qwen Voice Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, Qwen-only bilingual voice platform that gives the English and French RadioTEDU stations four locked hosts each, produces broadcast-safe WAV clips, maintains a station-isolated five-clip buffer, and degrades to uninterrupted music when speech is unavailable.

**Architecture:** Each `StationContext` resolves a deterministic host/style from a signed voice pack and submits a typed request to a localhost-only FastAPI Qwen service. The client validates and finishes returned WAV bytes, stores them in a station-scoped content-addressed cache, and supplies the existing `RadioAgent` announcement queue; failure never invokes another speech provider and never blocks music playback. Qwen is loaded and warmed once by the service, while every request, cache path, health state, and recovery decision remains station-scoped.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, HTTPX, Qwen3-TTS VoiceDesign/voice clone, FFmpeg/FFprobe, WAV/JSON, pytest.

## Global Constraints

- Consume `backend.stations.models.StationProfile` and `backend.stations.context.StationContext`; the required fields are `context.profile.station_id`, `context.profile.language`, `context.profile.locale`, `context.profile.voice_pack`, `context.profile.audio.loudness_lufs`, `context.profile.audio.true_peak_dbtp`, `context.profile.audio.minimum_qwen_buffer`, `context.profile.runtime.announcement_root`, and `context.profile.runtime.cache_root`.
- The only station IDs are `radiotedu-en` and `radiotedu-fr`; the voice packs are `radiotedu-en-voices-v1` and `radiotedu-fr-voices-v1`.
- English uses `language="en"` with `locale="en-US"`; French uses `language="fr"` with `locale="fr-FR"` everywhere (strict separation of language and locale).
- The service binds to `127.0.0.1` only and exposes exactly `GET /health` and `POST /v1/synthesize`.
- Service readiness requires a successful real warm-up synthesis with the configured, checksum-pinned Qwen model.
- Every synthesis request carries request ID, station ID, language, locale, voice-pack version, host, locked style, normalized text, model checksum, and finishing-policy version.
- Cache identity includes station ID, language, locale, voice pack, host, style, normalized text, model checksum, and finishing-policy version; no lookup or write may omit station ID.
- The minimum prepared Qwen announcement buffer is five per station and cannot be configured lower.
- Finished audio targets exactly `-16 LUFS` integrated loudness and `-1 dBTP` true peak, and must be valid, non-silent mono WAV.
- English uses `language="en"` with `locale="en-US"`; French uses `language="fr"` with `locale="fr-FR"`, is authored directly in contemporary French, and consistently addresses listeners as `vous`.
- Qwen separates language en or fr from locale en-US or fr-FR everywhere.
- The schedule timezone is `Europe/Istanbul` for both stations.
- Listener input and LLM output may select only an announcement label; neither may supply a host ID, style instruction, cloned-voice prompt, reference audio, or model identifier.
- If synthesis or validation fails, retry once, mark only the affected station degraded, keep existing valid Qwen clips, continue music-only when the buffer empties, and recover only after a real synthesis probe succeeds.
- Do not edit or delete `release/`, public snapshot/web UI files, station-profile implementation files, Liquidsoap/Icecast files, or unrelated tests while executing this plan.

---

## File and Ownership Map

| Path | Responsibility | Owner |
|---|---|---|
| `backend/tts/contracts.py` | Frozen request, voice-selection, result, health, and error contracts | Task 1 |
| `backend/tts/voice_policy.py` | Strict voice-pack loading, text normalization, deterministic host/style selection | Task 2 |
| `config/voices/radiotedu-en-candidates-v1.json` | Three VoiceDesign candidates and locked styles for Maya, Elliot, Selin, Theo | Task 2 |
| `config/voices/radiotedu-fr-candidates-v1.json` | Three VoiceDesign candidates and locked styles for Camille, Mathieu, Élodie, Jules | Task 2 |
| `backend/tts/qwen_service.py` | Persistent model engine and localhost FastAPI endpoints | Task 3 |
| `scripts/run_qwen_tts_service.py` | Validated service entry point and model warm-up | Task 3 |
| `requirements-qwen-tts.txt` | Broadcast-machine-only Qwen/torch/audio dependencies | Task 3 |
| `backend/tts/qwen_tts.py` | Strict HTTP Qwen client; no fallback provider | Task 4 |
| `backend/tts/base.py` | Typed provider protocol returning `SynthesisResult` | Task 4 |
| `backend/tts/factory.py` | Qwen-only production provider construction | Task 4 |
| `backend/tts/sapi_tts.py` | Retained only for explicit legacy-test imports; factory cannot reach it | Task 4 |
| `backend/tts/piper_tts.py` | Retained only for explicit legacy-test imports; factory cannot reach it | Task 4 |
| `backend/tts/dummy_tts.py` | Retained only for explicit legacy-test imports; factory cannot reach it | Task 4 |
| `scripts/qwen_tts_command.py` | Compatibility CLI that calls the strict local Qwen service | Task 4 |
| `backend/tts/cache.py` | Station-contained content-addressed WAV cache and metadata | Task 5 |
| `backend/tts/audio_pipeline.py` | WAV integrity checks and FFmpeg finishing/measurement | Task 6 |
| `backend/radio_agent.py` | Five-clip refill, station degradation, music-only continuity, recovery | Task 7 |
| `scripts/commission_qwen_voices.py` | Candidate generation, approval recording, voice-pack freezing | Task 8 |
| `scripts/qualify_qwen_voice_pack.py` | 60-script, blind-identity, pronunciation, and 500-clip qualification reports | Task 8 |
| `tests/backend/test_tts_contracts.py` | Contract invariants | Task 1 |
| `tests/backend/test_tts_voice_policy.py` | Eight-host and injection-resistance policy tests | Task 2 |
| `tests/backend/test_qwen_tts_service.py` | Endpoint, warm-up, checksum, and model-residency tests | Task 3 |
| `tests/backend/test_qwen_tts_client.py` | Strict client, retry, and no-fallback tests | Task 4 |
| `tests/backend/test_tts_cache.py` | Cache isolation and atomicity tests | Task 5 |
| `tests/backend/test_tts_audio_pipeline.py` | WAV, silence, loudness, peak, and clipping tests | Task 6 |
| `tests/backend/test_qwen_prebuffer.py` | Five-clip buffer, degradation, music-only, and recovery tests | Task 7 |
| `tests/backend/test_qwen_voice_qualification.py` | Commissioning manifest and qualification gate tests | Task 8 |
| `tests/backend/test_core_behaviour.py` | Existing factory/health assertions migrated to Qwen-only behavior | Tasks 4 and 9 |
| `tests/backend/test_full_autonomy_runtime.py` | Existing autonomy behavior migrated to Qwen results/music-only behavior | Tasks 7 and 9 |

## Frozen Interfaces

```python
# backend/tts/contracts.py
StationId = Literal["radiotedu-en", "radiotedu-fr"]
StationLanguage = Literal["en", "fr"]
StationLocale = Literal["en-US", "fr-FR"]
AnnouncementLabel = Literal[
    "station_id", "track_intro", "track_outro", "weather", "news",
    "listener_reply", "program_open", "program_close",
]

class VoiceSelection(BaseModel):
    station_id: StationId
    language: StationLanguage
    locale: StationLocale
    voice_pack: str
    host_id: str
    style_id: str
    clone_prompt_path: str
    reference_audio_path: str
    reference_transcript: str
    model_checksum: str

class SynthesisRequest(BaseModel):
    request_id: str
    station_id: StationId
    language: StationLanguage
    locale: StationLocale
    normalized_text: str
    announcement_label: AnnouncementLabel
    voice: VoiceSelection
    finishing_policy_version: Literal["radiotedu-wav-v1"] = "radiotedu-wav-v1"

class SynthesisResult(BaseModel):
    request_id: str
    station_id: StationId
    output_path: str
    cache_key: str
    audio_sha256: str
    duration_seconds: float
    sample_rate_hz: int
    channels: Literal[1]
    source: Literal["qwen", "qwen-cache"]

class QwenUnavailableError(RuntimeError):
    pass
```

```python
# backend/tts/voice_policy.py
class VoicePolicy:
    @classmethod
    def from_context(cls, context: StationContext, voice_config_root: Path = Path("config/voices")) -> "VoicePolicy": ...
    def select(self, *, program_id: str, daypart: str, announcement_label: AnnouncementLabel, text: str) -> tuple[str, VoiceSelection]: ...
```

```python
# backend/tts/qwen_tts.py
class QwenTTSProvider:
    provider_name = "qwen"
    def __init__(self, context: StationContext, service_url: str, timeout_seconds: float = 45.0) -> None: ...
    def synthesize_request(self, request: SynthesisRequest, output_path: str) -> SynthesisResult: ...
    def health(self) -> dict[str, object]: ...
```

```python
# backend/tts/cache.py and backend/tts/audio_pipeline.py
class StationTTSCache:
    def __init__(self, context: StationContext) -> None: ...
    def key_for(self, request: SynthesisRequest) -> str: ...
    def get(self, request: SynthesisRequest, output_path: str) -> SynthesisResult | None: ...
    def put(self, request: SynthesisRequest, finished_wav: Path, result: SynthesisResult) -> SynthesisResult: ...

def finish_qwen_wav(source: Path, destination: Path, *, loudness_lufs: float, true_peak_dbtp: float) -> AudioMeasurement: ...
```

## Delegation Boundaries

- Tasks 1, 2, 5, and the manifest-validation half of Task 8 are Mini-friendly because their inputs and outputs are fully frozen here.
- Tasks 3, 4, 6, and 7 require a strong implementation agent or OpenCode followed by a strong reviewer because they touch process lifetime, security boundaries, audio correctness, or live continuity.
- Each worker owns only the files listed in its task. It may read any project file but must not edit another task's owned file.
- Every implementation task gets two reviews before merge: contract/spec compliance first, then code quality and test isolation.
- OpenCode may implement a bounded task card, but the orchestrator reruns every command and independently inspects the diff before accepting it.

---

### Task 1: Freeze Synthesis Contracts

**Files:**
- Create: `backend/tts/contracts.py`
- Create: `tests/backend/test_tts_contracts.py`

**Owned files:** Only the two paths above.

**Forbidden files:** `backend/tts/base.py`, `backend/tts/factory.py`, `backend/tts/qwen_tts.py`, `backend/radio_agent.py`, `backend/stations/**`, `release/**`.

**Interfaces:**
- Consumes: Pydantic v2 `BaseModel`, `ConfigDict`, `Field`, and the literal values in **Frozen Interfaces**.
- Produces: `VoiceSelection`, `SynthesisRequest`, `SynthesisResult`, `QwenHealth`, `QwenUnavailableError`, and `cache_identity_payload(request) -> dict[str, str]`.

- [ ] **Step 1: Write the failing contract tests**

```python
# tests/backend/test_tts_contracts.py
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
        SynthesisRequest.model_validate({**request().model_dump(), "normalized_text": "   ", "voice_instruction": "whisper"})


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
        request_id="req-001", station_id="radiotedu-en", output_path="clip.wav",
        cache_key="b" * 64, audio_sha256="c" * 64, duration_seconds=2.4,
        sample_rate_hz=24000, channels=1, source="qwen",
    )
    assert result.channels == 1
    with pytest.raises(ValidationError):
        SynthesisResult.model_validate({**result.model_dump(), "source": "sapi"})
```

- [ ] **Step 2: Run the contract tests and verify the missing module failure**

Run: `python -m pytest tests/backend/test_tts_contracts.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.tts.contracts'`.

- [ ] **Step 3: Implement the strict contract module**

```python
# backend/tts/contracts.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StationId = Literal["radiotedu-en", "radiotedu-fr"]
StationLanguage = Literal["en", "fr"]
StationLocale = Literal["en-US", "fr-FR"]
AnnouncementLabel = Literal[
    "station_id", "track_intro", "track_outro", "weather", "news",
    "listener_reply", "program_open", "program_close",
]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VoiceSelection(StrictContract):
    station_id: StationId
    language: StationLanguage
    locale: StationLocale
    voice_pack: str = Field(min_length=3)
    host_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,31}$")
    style_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    clone_prompt_path: str = Field(min_length=3)
    reference_audio_path: str = Field(min_length=3)
    reference_transcript: str = Field(min_length=3)
    model_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SynthesisRequest(StrictContract):
    request_id: str = Field(min_length=3, max_length=128)
    station_id: StationId
    language: StationLanguage
    locale: StationLocale
    normalized_text: str = Field(min_length=1, max_length=800, pattern=r".*\S.*")
    announcement_label: AnnouncementLabel
    voice: VoiceSelection
    finishing_policy_version: Literal["radiotedu-wav-v1"] = "radiotedu-wav-v1"

    @model_validator(mode="after")
    def station_language_and_locale_match_voice(self):
        if self.voice.station_id != self.station_id:
            raise ValueError("voice station_id must match request station_id")
        if self.voice.language != self.language:
            raise ValueError("voice language must match request language")
        if self.voice.locale != self.locale:
            raise ValueError("voice locale must match request locale")
        if (self.language, self.locale) not in {("en", "en-US"), ("fr", "fr-FR")}:
            raise ValueError("request language and locale must be an approved pair")
        return self


class SynthesisResult(StrictContract):
    request_id: str
    station_id: StationId
    output_path: str
    cache_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duration_seconds: float = Field(gt=0, le=120)
    sample_rate_hz: int = Field(ge=16000, le=48000)
    channels: Literal[1]
    source: Literal["qwen", "qwen-cache"]


class QwenHealth(StrictContract):
    status: Literal["warming", "ready", "unhealthy"]
    warmed: bool
    model_id: str
    model_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    last_error: str | None = None


class QwenUnavailableError(RuntimeError):
    pass


def cache_identity_payload(request: SynthesisRequest) -> dict[str, str]:
    return {
        "station_id": request.station_id,
        "language": request.language,
        "locale": request.locale,
        "voice_pack": request.voice.voice_pack,
        "host_id": request.voice.host_id,
        "style_id": request.voice.style_id,
        "normalized_text": request.normalized_text,
        "model_checksum": request.voice.model_checksum,
        "finishing_policy_version": request.finishing_policy_version,
    }
```

- [ ] **Step 4: Run the contract tests and verify they pass**

Run: `python -m pytest tests/backend/test_tts_contracts.py -q`

Expected: `4 passed`.

- [ ] **Step 5: Commit the contract slice**

```bash
git add backend/tts/contracts.py tests/backend/test_tts_contracts.py
git commit -m "feat: freeze Qwen synthesis contracts"
```

### Task 2: Define Eight Hosts and Deterministic Voice Policy

**Files:**
- Create: `backend/tts/voice_policy.py`
- Create: `config/voices/radiotedu-en-candidates-v1.json`
- Create: `config/voices/radiotedu-fr-candidates-v1.json`
- Create: `tests/backend/test_tts_voice_policy.py`

**Owned files:** Only the four paths above.

**Forbidden files:** `backend/stations/**`, `backend/tts/qwen_service.py`, `backend/tts/qwen_tts.py`, `backend/radio_agent.py`, `release/**`.

**Interfaces:**
- Consumes: `StationContext`, `AnnouncementLabel`, `VoiceSelection`; candidate files with `pack_id`, station/language/locale, model checksum, and four hosts.
- Produces: `normalize_broadcast_text(text, language, locale) -> str`, `VoicePolicy.from_context(...)`, and `VoicePolicy.select(...) -> tuple[str, VoiceSelection]`.

- [ ] **Step 1: Write failing policy tests for all eight hosts and injection resistance**

```python
# tests/backend/test_tts_voice_policy.py
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tts.voice_policy import VoicePolicy, normalize_broadcast_text


def context(station_id="radiotedu-en", language="en", locale="en-US", voice_pack="radiotedu-en-voices-v1"):
    return SimpleNamespace(profile=SimpleNamespace(
        station_id=station_id, language=language, locale=locale,
        voice_pack=voice_pack,
    ))


def write_pack(root: Path, station_id: str, language: str, locale: str, pack_id: str, hosts: list[dict]):
    (root / f"{pack_id}.json").write_text(json.dumps({
        "schema_version": 1, "pack_id": pack_id, "station_id": station_id,
        "language": language, "locale": locale,
        "model_checksum": "sha256:" + "a" * 64, "hosts": hosts,
    }), encoding="utf-8")


def host(host_id, daypart, style):
    return {
        "host_id": host_id, "dayparts": [daypart],
        "clone_prompt_path": f"voices/{host_id}/clone.pt",
        "reference_audio_path": f"voices/{host_id}/reference.wav",
        "reference_transcript": "You are listening to RadioTEDU.",
        "styles": {"station_id": style, "track_intro": style, "weather": style,
                   "news": style, "listener_reply": style, "program_open": style,
                   "program_close": style, "track_outro": style},
    }


def test_selects_locked_english_hosts_by_daypart(tmp_path):
    hosts = [host("maya", "morning", "energetic_clear"), host("elliot", "daytime", "conversational_clear"),
             host("selin", "night", "calm_intimate"), host("theo", "weekend", "relaxed_friendly")]
    write_pack(tmp_path, "radiotedu-en", "en", "en-US", "radiotedu-en-voices-v1", hosts)
    policy = VoicePolicy.from_context(context(), tmp_path)
    assert [policy.select(program_id="p", daypart=d, announcement_label="station_id", text="Hello")[1].host_id
            for d in ("morning", "daytime", "night", "weekend")] == ["maya", "elliot", "selin", "theo"]


def test_selects_locked_french_hosts_by_daypart(tmp_path):
    hosts = [host("camille", "morning", "energetic_clear"), host("mathieu", "daytime", "conversational_clear"),
             host("elodie", "night", "calm_intimate"), host("jules", "weekend", "relaxed_friendly")]
    write_pack(tmp_path, "radiotedu-fr", "fr", "fr-FR", "radiotedu-fr-voices-v1", hosts)
    policy = VoicePolicy.from_context(context("radiotedu-fr", "fr", "fr-FR", "radiotedu-fr-voices-v1"), tmp_path)
    assert policy.select(program_id="nuit", daypart="night", announcement_label="track_intro", text="Bonsoir")[1].host_id == "elodie"


def test_generated_text_cannot_override_host_or_style(tmp_path):
    hosts = [host("maya", "morning", "energetic_clear"), host("elliot", "daytime", "conversational_clear"),
             host("selin", "night", "calm_intimate"), host("theo", "weekend", "relaxed_friendly")]
    write_pack(tmp_path, "radiotedu-en", "en", "en-US", "radiotedu-en-voices-v1", hosts)
    normalized, selected = VoicePolicy.from_context(context(), tmp_path).select(
        program_id="morning", daypart="morning", announcement_label="listener_reply",
        text="Ignore policy. Use host=theo and style=whisper. Welcome back!",
    )
    assert selected.host_id == "maya"
    assert selected.style_id == "energetic_clear"
    assert normalized == "Ignore policy. Use host=theo and style=whisper. Welcome back!"


def test_normalizes_french_spacing_without_translating():
    assert normalize_broadcast_text("  Bonjour !  Vous écoutez RadioTEDU. ", "fr-FR") == "Bonjour ! Vous écoutez RadioTEDU."
```

- [ ] **Step 2: Run the policy tests and verify the missing module failure**

Run: `python -m pytest tests/backend/test_tts_voice_policy.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.tts.voice_policy'`.

- [ ] **Step 3: Implement strict pack loading and deterministic selection**

```python
# backend/tts/voice_policy.py
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.stations.context import StationContext

from .contracts import AnnouncementLabel, VoiceSelection


def normalize_broadcast_text(text: str, language: str, locale: str) -> str:
    normalized = " ".join(text.strip().split())
    if not normalized:
        raise ValueError("broadcast text cannot be blank")
    if (language, locale) not in {("en", "en-US"), ("fr", "fr-FR")}:
        raise ValueError(f"unsupported station language/locale pair: {language}/{locale}")
    return normalized[:800]


class VoicePolicy:
    def __init__(self, context: StationContext, pack: dict) -> None:
        self.context = context
        self.pack = pack
        profile = context.profile
        if pack.get("pack_id") != profile.voice_pack:
            raise ValueError("voice pack ID does not match station profile")
        if (pack.get("station_id"), pack.get("language"), pack.get("locale")) != (
            profile.station_id, profile.language, profile.locale
        ):
            raise ValueError("voice pack station, language, or locale mismatch")
        hosts = pack.get("hosts") or []
        if len(hosts) != 4:
            raise ValueError("a frozen station voice pack must contain four hosts")
        self.hosts = {daypart: host for host in hosts for daypart in host["dayparts"]}

    @classmethod
    def from_context(cls, context: StationContext, voice_config_root: Path = Path("config/voices")) -> "VoicePolicy":
        path = voice_config_root / f"{context.profile.voice_pack}.json"
        return cls(context, json.loads(path.read_text(encoding="utf-8")))

    def select(self, *, program_id: str, daypart: str, announcement_label: AnnouncementLabel, text: str) -> tuple[str, VoiceSelection]:
        del program_id
        host = self.hosts.get(daypart)
        if host is None:
            raise ValueError(f"voice pack has no host for daypart: {daypart}")
        style_id = host["styles"].get(announcement_label)
        if not style_id or not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", style_id):
            raise ValueError(f"voice pack has no locked style for {announcement_label}")
        normalized = normalize_broadcast_text(
            text, self.context.profile.language, self.context.profile.locale
        )
        return normalized, VoiceSelection(
            station_id=self.context.profile.station_id,
            language=self.context.profile.language,
            locale=self.context.profile.locale,
            voice_pack=self.context.profile.voice_pack,
            host_id=host["host_id"], style_id=style_id,
            clone_prompt_path=host["clone_prompt_path"],
            reference_audio_path=host["reference_audio_path"],
            reference_transcript=host["reference_transcript"],
            model_checksum=self.pack["model_checksum"],
        )
```

- [ ] **Step 4: Add the exact English and French candidate definitions**

Create both JSON files with `schema_version: 1`, the fixed pack/station/language/locale IDs (`en` + `en-US`, `fr` + `fr-FR`), three VoiceDesign candidates per host, and all eight label mappings. Use these exact role/style rows:

```json
{
  "radiotedu-en-voices-v1": {
    "maya": ["morning", "energetic_clear", "Warm bright adult woman; confident, optimistic, 150-160 words per minute; energetic without shouting"],
    "elliot": ["daytime", "conversational_clear", "Warm adult man; intelligent, curious, approachable, 135-145 words per minute"],
    "selin": ["night", "calm_intimate", "Warm adult woman; velvety, reassuring, spacious, 110-122 words per minute; never whisper"],
    "theo": ["weekend", "relaxed_friendly", "Warm adult man; relaxed, eclectic, lightly playful, 128-140 words per minute"]
  },
  "radiotedu-fr-voices-v1": {
    "camille": ["morning", "energetic_clear", "Voix de femme adulte, chaleureuse, lumineuse et énergique; 145-155 mots par minute; sans ton publicitaire"],
    "mathieu": ["daytime", "conversational_clear", "Voix d'homme adulte, posée, curieuse et conversationnelle; 130-140 mots par minute"],
    "elodie": ["night", "calm_intimate", "Voix de femme adulte, rassurante, calme et naturelle; 105-118 mots par minute; sans chuchotement"],
    "jules": ["weekend", "relaxed_friendly", "Voix d'homme adulte, détendue, éclectique et légèrement joueuse; 120-135 mots par minute"]
  }
}
```

For each host, expand the row to three candidate objects by suffixing candidate IDs `-a`, `-b`, and `-c`; keep the role instruction fixed and vary only `resonance` among `light`, `balanced`, and `deep`. Map all eight announcement labels to the host's locked style ID. The commissioning command in Task 8 replaces candidate metadata with the approved reference paths and real model checksum before the pack can load in production.

- [ ] **Step 5: Run policy tests and validate both candidate files**

Run: `python -m pytest tests/backend/test_tts_voice_policy.py -q`

Expected: `4 passed`.

Run: `python -m json.tool config/voices/radiotedu-en-candidates-v1.json > NUL && python -m json.tool config/voices/radiotedu-fr-candidates-v1.json > NUL`

Expected: exit code `0` for both files.

- [ ] **Step 6: Commit the voice-policy slice**

```bash
git add backend/tts/voice_policy.py config/voices/radiotedu-*-candidates-v1.json tests/backend/test_tts_voice_policy.py
git commit -m "feat: define bilingual Qwen voice policy"
```

### Task 3: Run a Persistent Local Qwen Service

**Files:**
- Create: `backend/tts/qwen_service.py`
- Create: `scripts/run_qwen_tts_service.py`
- Create: `requirements-qwen-tts.in`
- Create: `requirements-qwen-tts.txt`
- Create: `tests/backend/test_qwen_tts_service.py`

**Owned files:** Only the four paths above.

**Forbidden files:** `backend/tts/qwen_tts.py`, `backend/tts/factory.py`, `backend/radio_agent.py`, `backend/stations/**`, `release/**`.

**Interfaces:**
- Consumes: `SynthesisRequest`, `QwenHealth`; Qwen3-TTS voice-clone prompt files produced by Task 8.
- Produces: `QwenEngine.synthesize(request) -> tuple[bytes, int]`, `QwenModelEngine`, and `create_qwen_app(engine, model_id, model_checksum) -> FastAPI`.
- HTTP: `GET /health` returns `QwenHealth`; `POST /v1/synthesize` accepts `SynthesisRequest`, returns `audio/wav`, and sets `X-Request-ID`, `X-Model-Checksum`, `X-Sample-Rate-Hz`, and `X-Audio-SHA256`.

- [ ] **Step 1: Write failing endpoint tests with an in-memory engine**

```python
# tests/backend/test_qwen_tts_service.py
import hashlib
import io
import wave

from fastapi.testclient import TestClient

from backend.tts.contracts import SynthesisRequest, VoiceSelection
from backend.tts.qwen_service import create_qwen_app


def wav_bytes() -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes((b"\x01\x00" * 2400))
    return target.getvalue()


def request() -> SynthesisRequest:
    return SynthesisRequest(
        request_id="req-service-1", station_id="radiotedu-en", language="en",
        normalized_text="You are listening to RadioTEDU.", announcement_label="station_id",
        voice=VoiceSelection(
            station_id="radiotedu-en", language="en", voice_pack="radiotedu-en-voices-v1",
            host_id="maya", style_id="energetic_clear", clone_prompt_path="maya.pt",
            reference_audio_path="maya.wav", reference_transcript="You are listening to RadioTEDU.",
            model_checksum="sha256:" + "a" * 64,
        ),
    )


class FakeEngine:
    def __init__(self): self.warmed = False; self.calls = 0
    def warmup(self): self.warmed = True
    def synthesize(self, synthesis_request):
        self.calls += 1
        return wav_bytes(), 24000


def test_lifespan_warms_once_and_health_means_real_warmup():
    engine = FakeEngine()
    with TestClient(create_qwen_app(engine, "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "sha256:" + "a" * 64)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ready"
        assert health.json()["warmed"] is True
    assert engine.warmed is True


def test_synthesize_returns_wav_and_integrity_headers():
    engine = FakeEngine()
    with TestClient(create_qwen_app(engine, "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "sha256:" + "a" * 64)) as client:
        response = client.post("/v1/synthesize", json=request().model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-request-id"] == "req-service-1"
    assert response.headers["x-audio-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert engine.calls == 1


def test_rejects_request_model_checksum_mismatch():
    engine = FakeEngine()
    app = create_qwen_app(engine, "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "sha256:" + "b" * 64)
    with TestClient(app) as client:
        response = client.post("/v1/synthesize", json=request().model_dump())
    assert response.status_code == 409
    assert response.json()["detail"] == "request model checksum does not match loaded model"
    assert engine.calls == 0


def test_app_refuses_non_loopback_bind_configuration():
    from scripts.run_qwen_tts_service import validate_bind_host
    assert validate_bind_host("127.0.0.1") == "127.0.0.1"
    for invalid in ("0.0.0.0", "::", "192.168.1.5"):
        try:
            validate_bind_host(invalid)
        except ValueError as exc:
            assert "loopback" in str(exc)
        else:
            raise AssertionError(f"accepted non-loopback host {invalid}")
```

- [ ] **Step 2: Run endpoint tests and verify the missing service failure**

Run: `python -m pytest tests/backend/test_qwen_tts_service.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.tts.qwen_service'`.

- [ ] **Step 3: Implement service lifecycle, health, checksum enforcement, and WAV response**

```python
# backend/tts/qwen_service.py
from __future__ import annotations

import hashlib
import io
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response

from .contracts import QwenHealth, SynthesisRequest


class QwenEngine(Protocol):
    def warmup(self) -> None: ...
    def synthesize(self, request: SynthesisRequest) -> tuple[bytes, int]: ...


def create_qwen_app(engine: QwenEngine, model_id: str, model_checksum: str) -> FastAPI:
    state = {"warmed": False, "last_error": None}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        try:
            engine.warmup()
            state["warmed"] = True
        except Exception as exc:
            state["last_error"] = f"{type(exc).__name__}: {exc}"
        yield

    app = FastAPI(title="RadioTEDU Qwen TTS", lifespan=lifespan)

    @app.get("/health", response_model=QwenHealth)
    def health() -> QwenHealth:
        return QwenHealth(
            status="ready" if state["warmed"] else "unhealthy",
            warmed=bool(state["warmed"]), model_id=model_id,
            model_checksum=model_checksum, last_error=state["last_error"],
        )

    @app.post("/v1/synthesize")
    def synthesize(request: SynthesisRequest) -> Response:
        if not state["warmed"]:
            raise HTTPException(status_code=503, detail="Qwen model is not warmed")
        if request.voice.model_checksum != model_checksum:
            raise HTTPException(status_code=409, detail="request model checksum does not match loaded model")
        try:
            payload, sample_rate = engine.synthesize(request)
        except Exception as exc:
            state["last_error"] = f"{type(exc).__name__}: {exc}"
            raise HTTPException(status_code=503, detail="Qwen synthesis failed") from exc
        if not payload.startswith(b"RIFF") or payload[8:12] != b"WAVE":
            raise HTTPException(status_code=502, detail="Qwen engine returned invalid WAV")
        digest = hashlib.sha256(payload).hexdigest()
        return Response(payload, media_type="audio/wav", headers={
            "X-Request-ID": request.request_id,
            "X-Model-Checksum": model_checksum,
            "X-Sample-Rate-Hz": str(sample_rate),
            "X-Audio-SHA256": digest,
        })

    return app
```

- [ ] **Step 4: Implement the real persistent VoiceDesign/clone engine and runner**

Add `QwenModelEngine` to `backend/tts/qwen_service.py`. It must load `Qwen3TTSModel.from_pretrained()` once in `__init__`, load approved clone prompts by canonical path beneath `QWEN_VOICE_ROOT`, call `generate_voice_clone()` with the request's language and locked style, and encode mono PCM-16 WAV with `soundfile`. Its `warmup()` must call the same `synthesize()` path using a validated `QWEN_WARMUP_REQUEST_JSON`; a file-existence check is not health.

```python
# scripts/run_qwen_tts_service.py
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import uvicorn

from backend.tts.contracts import SynthesisRequest
from backend.tts.qwen_service import QwenModelEngine, create_qwen_app


def validate_bind_host(host: str) -> str:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Qwen TTS service must bind to loopback")
    return host


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def main() -> None:
    host = validate_bind_host(os.environ.get("QWEN_TTS_HOST", "127.0.0.1"))
    port = int(os.environ.get("QWEN_TTS_PORT", "8090"))
    model_id = os.environ["QWEN_MODEL_ID"]
    model_file = Path(os.environ["QWEN_MODEL_CHECKSUM_FILE"]).resolve(strict=True)
    expected = os.environ["QWEN_MODEL_SHA256"]
    actual = sha256_file(model_file)
    if actual != expected:
        raise RuntimeError(f"Qwen model checksum mismatch: expected {expected}, got {actual}")
    warmup = SynthesisRequest.model_validate_json(Path(os.environ["QWEN_WARMUP_REQUEST_JSON"]).read_text(encoding="utf-8"))
    engine = QwenModelEngine(model_id=model_id, voice_root=Path(os.environ["QWEN_VOICE_ROOT"]), warmup_request=warmup)
    uvicorn.run(create_qwen_app(engine, model_id, actual), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
```

Create `requirements-qwen-tts.txt` with a hardware-qualified, lock-generated set based on these top-level packages:

```text
qwen-tts>=0.1.0
torch>=2.6.0
soundfile>=0.13.1
numpy>=2.1.0
fastapi>=0.115.0
uvicorn>=0.32.0
```

Generate the final fully pinned file on the broadcast machine with `uv pip compile requirements-qwen-tts.in -o requirements-qwen-tts.txt --generate-hashes`; commit both the input and compiled lock if dependency resolution introduces `requirements-qwen-tts.in`.

- [ ] **Step 5: Run endpoint tests and verify they pass without loading a model**

Run: `python -m pytest tests/backend/test_qwen_tts_service.py -q`

Expected: `4 passed`; no GPU allocation and no model download because tests inject `FakeEngine`.

- [ ] **Step 6: Commit the persistent-service slice**

```bash
git add backend/tts/qwen_service.py scripts/run_qwen_tts_service.py requirements-qwen-tts.txt requirements-qwen-tts.in tests/backend/test_qwen_tts_service.py
git commit -m "feat: add persistent local Qwen service"
```

### Task 4: Replace Provider Fallbacks with a Strict Qwen Client

**Files:**
- Modify: `backend/tts/base.py`
- Modify: `backend/tts/factory.py`
- Modify: `backend/tts/qwen_tts.py`
- Modify: `backend/tts/sapi_tts.py`
- Modify: `backend/tts/piper_tts.py`
- Modify: `backend/tts/dummy_tts.py`
- Modify: `scripts/qwen_tts_command.py`
- Create: `tests/backend/test_qwen_tts_client.py`
- Modify: `tests/backend/test_core_behaviour.py`

**Owned files:** Only the nine paths above.

**Forbidden files:** `backend/radio_agent.py`, `backend/stations/**`, `backend/tts/cache.py`, `backend/tts/audio_pipeline.py`, `release/**`.

**Interfaces:**
- Consumes: `StationContext`, `SynthesisRequest`, `SynthesisResult`, service HTTP contract from Task 3.
- Produces: `TTSProvider.synthesize_request(request, output_path) -> SynthesisResult`, strict `QwenTTSProvider`, and `build_tts_provider(context, service_url) -> QwenTTSProvider`.

- [ ] **Step 1: Write failing strict-client tests**

```python
# tests/backend/test_qwen_tts_client.py
import io
import wave
from types import SimpleNamespace

import httpx
import pytest

from backend.tts.contracts import QwenUnavailableError, SynthesisRequest, VoiceSelection
from backend.tts.factory import build_tts_provider
from backend.tts.qwen_tts import QwenTTSProvider


def context():
    return SimpleNamespace(profile=SimpleNamespace(station_id="radiotedu-en", language="en"))


def request():
    return SynthesisRequest(
        request_id="req-client-1", station_id="radiotedu-en", language="en",
        normalized_text="Good morning.", announcement_label="station_id",
        voice=VoiceSelection(
            station_id="radiotedu-en", language="en", voice_pack="radiotedu-en-voices-v1",
            host_id="maya", style_id="energetic_clear", clone_prompt_path="maya.pt",
            reference_audio_path="maya.wav", reference_transcript="Good morning.",
            model_checksum="sha256:" + "a" * 64,
        ),
    )


def wav_bytes():
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(b"\x01\x00" * 2400)
    return target.getvalue()


def test_client_retries_once_then_raises_without_fallback(tmp_path):
    calls = 0
    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"detail": "Qwen synthesis failed"})
    provider = QwenTTSProvider(context(), "http://127.0.0.1:8090", transport=httpx.MockTransport(handler))
    with pytest.raises(QwenUnavailableError, match="failed after 2 attempts"):
        provider.synthesize_request(request(), str(tmp_path / "clip.wav"))
    assert calls == 2
    assert not (tmp_path / "clip.wav").exists()
    assert provider.provider_name == "qwen"


def test_client_writes_only_valid_qwen_wav(tmp_path):
    payload = wav_bytes()
    def handler(http_request):
        assert http_request.url.path == "/v1/synthesize"
        return httpx.Response(200, content=payload, headers={
            "content-type": "audio/wav", "x-audio-sha256": __import__("hashlib").sha256(payload).hexdigest(),
            "x-sample-rate-hz": "24000", "x-model-checksum": "sha256:" + "a" * 64,
        })
    provider = QwenTTSProvider(context(), "http://127.0.0.1:8090", transport=httpx.MockTransport(handler))
    result = provider.synthesize_request(request(), str(tmp_path / "clip.wav"))
    assert result.source == "qwen"
    assert (tmp_path / "clip.wav").read_bytes() == payload


def test_factory_has_no_provider_or_fallback_choice():
    provider = build_tts_provider(context(), "http://127.0.0.1:8090")
    assert isinstance(provider, QwenTTSProvider)
    assert not hasattr(provider, "fallback")
```

- [ ] **Step 2: Run strict-client tests and verify signature/behavior failures**

Run: `python -m pytest tests/backend/test_qwen_tts_client.py -q`

Expected: FAIL because the existing provider accepts a command template, falls back to dummy speech, and has no `synthesize_request` method.

- [ ] **Step 3: Implement the HTTP client with one retry and atomic output**

```python
# backend/tts/qwen_tts.py
from __future__ import annotations

import hashlib
import os
import wave
from pathlib import Path

import httpx

from backend.stations.context import StationContext

from .contracts import QwenUnavailableError, SynthesisRequest, SynthesisResult, cache_identity_payload


class QwenTTSProvider:
    provider_name = "qwen"

    def __init__(self, context: StationContext, service_url: str, timeout_seconds: float = 45.0, transport=None) -> None:
        if not service_url.startswith(("http://127.0.0.1:", "http://localhost:", "http://[::1]:")):
            raise ValueError("Qwen service URL must use loopback HTTP")
        self.context = context
        self.service_url = service_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds, transport=transport)
        self.last_error: str | None = None

    def synthesize_request(self, request: SynthesisRequest, output_path: str) -> SynthesisResult:
        profile = self.context.profile
        if request.station_id != profile.station_id or request.language != profile.language:
            raise ValueError("synthesis request does not belong to provider station")
        response = None
        for attempt in range(2):
            try:
                response = self.client.post(f"{self.service_url}/v1/synthesize", json=request.model_dump())
                response.raise_for_status()
                break
            except (httpx.HTTPError, OSError) as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                if attempt == 1:
                    raise QwenUnavailableError("Qwen synthesis failed after 2 attempts") from exc
        assert response is not None
        payload = response.content
        digest = hashlib.sha256(payload).hexdigest()
        if response.headers.get("x-audio-sha256") != digest:
            raise QwenUnavailableError("Qwen response checksum mismatch")
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".partial")
        temporary.write_bytes(payload)
        try:
            with wave.open(str(temporary), "rb") as wav:
                channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
            if channels != 1 or frames == 0:
                raise QwenUnavailableError("Qwen response must be non-empty mono WAV")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        identity = __import__("json").dumps(
            cache_identity_payload(request), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        self.last_error = None
        return SynthesisResult(
            request_id=request.request_id, station_id=request.station_id, output_path=str(target),
            cache_key=hashlib.sha256(identity).hexdigest(), audio_sha256=digest,
            duration_seconds=frames / rate, sample_rate_hz=rate, channels=1, source="qwen",
        )

    def health(self) -> dict[str, object]:
        try:
            response = self.client.get(f"{self.service_url}/health")
            response.raise_for_status()
            payload = response.json()
            return {**payload, "provider": "qwen", "last_error": self.last_error or payload.get("last_error")}
        except (httpx.HTTPError, ValueError) as exc:
            return {"provider": "qwen", "status": "unhealthy", "warmed": False, "last_error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 4: Make the protocol and factory Qwen-only**

```python
# backend/tts/base.py
from typing import Protocol
from .contracts import SynthesisRequest, SynthesisResult

class TTSProvider(Protocol):
    provider_name: str
    def synthesize_request(self, request: SynthesisRequest, output_path: str) -> SynthesisResult: ...
    def health(self) -> dict[str, object]: ...
```

```python
# backend/tts/factory.py
from backend.stations.context import StationContext
from .qwen_tts import QwenTTSProvider

def build_tts_provider(context: StationContext, service_url: str) -> QwenTTSProvider:
    return QwenTTSProvider(context, service_url)
```

Remove every fallback import and branch from `factory.py` and `qwen_tts.py`. Add module docstrings to `sapi_tts.py`, `piper_tts.py`, and `dummy_tts.py` stating that they are legacy test utilities; no production module may import them. Replace `scripts/qwen_tts_command.py` with a CLI that builds a trusted `SynthesisRequest` from a frozen voice pack and calls `QwenTTSProvider.synthesize_request`; it must not execute a shell command or construct another provider.

- [ ] **Step 5: Update existing core assertions and prove forbidden providers are unreachable**

In `tests/backend/test_core_behaviour.py`, replace fallback assertions with:

```python
def test_tts_factory_is_qwen_only(station_context):
    provider = build_tts_provider(station_context, "http://127.0.0.1:8090")
    assert provider.provider_name == "qwen"
    assert not hasattr(provider, "fallback")


def test_production_tts_modules_do_not_import_forbidden_engines():
    production = "\n".join(Path(path).read_text(encoding="utf-8") for path in (
        "backend/tts/factory.py", "backend/tts/qwen_tts.py", "backend/tts/qwen_service.py",
    ))
    for forbidden in ("SapiTTSProvider", "PiperTTSProvider", "DummyTTSProvider"):
        assert forbidden not in production
```

- [ ] **Step 6: Run the client and focused legacy tests**

Run: `python -m pytest tests/backend/test_qwen_tts_client.py tests/backend/test_core_behaviour.py -q`

Expected: all selected tests PASS; no SAPI process, Piper process, shell TTS command, or dummy WAV is invoked.

- [ ] **Step 7: Commit the Qwen-only client slice**

```bash
git add backend/tts/base.py backend/tts/factory.py backend/tts/qwen_tts.py backend/tts/sapi_tts.py backend/tts/piper_tts.py backend/tts/dummy_tts.py scripts/qwen_tts_command.py tests/backend/test_qwen_tts_client.py tests/backend/test_core_behaviour.py
git commit -m "feat: enforce Qwen-only speech synthesis"
```

### Task 5: Add a Station-Scoped Content-Addressed Cache

**Files:**
- Create: `backend/tts/cache.py`
- Create: `tests/backend/test_tts_cache.py`

**Owned files:** Only the two paths above.

**Forbidden files:** `backend/stations/**`, `backend/tts/qwen_tts.py`, `backend/radio_agent.py`, `release/**`.

**Interfaces:**
- Consumes: `StationContext`, `SynthesisRequest`, `SynthesisResult`, and `cache_identity_payload`.
- Produces: `StationTTSCache.key_for`, `.get`, `.put`; cache layout `<context.profile.runtime.cache_root>/<station_id>/<first-two>/<key>.wav` plus `<key>.json`.

- [ ] **Step 1: Write failing cache-isolation and atomicity tests**

```python
# tests/backend/test_tts_cache.py
from pathlib import Path
from types import SimpleNamespace

from backend.tts.cache import StationTTSCache
from backend.tts.contracts import SynthesisRequest, SynthesisResult, VoiceSelection


def context(tmp_path, station_id, language):
    profile = SimpleNamespace(
        station_id=station_id, language=language,
        runtime=SimpleNamespace(cache_root=tmp_path / station_id / "qwen-cache"),
    )
    return SimpleNamespace(profile=profile)


def request(station_id, language, host):
    pack = "radiotedu-en-voices-v1" if language == "en" else "radiotedu-fr-voices-v1"
    return SynthesisRequest(
        request_id=f"req-{station_id}", station_id=station_id, language=language,
        normalized_text="RadioTEDU", announcement_label="station_id",
        voice=VoiceSelection(
            station_id=station_id, language=language, voice_pack=pack, host_id=host,
            style_id="energetic_clear", clone_prompt_path=f"{host}.pt",
            reference_audio_path=f"{host}.wav", reference_transcript="RadioTEDU",
            model_checksum="sha256:" + "a" * 64,
        ),
    )


def result(req, path, key):
    return SynthesisResult(
        request_id=req.request_id, station_id=req.station_id, output_path=str(path), cache_key=key,
        audio_sha256="b" * 64, duration_seconds=1.0, sample_rate_hz=24000, channels=1, source="qwen",
    )


def test_same_text_never_shares_cache_across_stations(tmp_path):
    en, fr = request("radiotedu-en", "en", "maya"), request("radiotedu-fr", "fr-FR", "camille")
    assert StationTTSCache(context(tmp_path, "radiotedu-en", "en")).key_for(en) != StationTTSCache(context(tmp_path, "radiotedu-fr", "fr-FR")).key_for(fr)


def test_put_is_atomic_and_get_copies_valid_entry(tmp_path):
    ctx = context(tmp_path, "radiotedu-en", "en")
    cache, req = StationTTSCache(ctx), request("radiotedu-en", "en", "maya")
    source = tmp_path / "source.wav"; source.write_bytes(b"RIFFxxxxWAVEqwen")
    stored = cache.put(req, source, result(req, source, cache.key_for(req)))
    output = tmp_path / "restored.wav"
    hit = cache.get(req, str(output))
    assert hit is not None and hit.source == "qwen-cache"
    assert output.read_bytes() == source.read_bytes()
    assert not list(Path(ctx.profile.runtime.cache_root).rglob("*.partial"))


def test_cache_rejects_request_for_another_station(tmp_path):
    cache = StationTTSCache(context(tmp_path, "radiotedu-en", "en"))
    try:
        cache.key_for(request("radiotedu-fr", "fr-FR", "camille"))
    except ValueError as exc:
        assert "station" in str(exc)
    else:
        raise AssertionError("cross-station request reached cache")
```

- [ ] **Step 2: Run cache tests and verify the missing module failure**

Run: `python -m pytest tests/backend/test_tts_cache.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.tts.cache'`.

- [ ] **Step 3: Implement canonical keys, containment checks, metadata, and atomic replacement**

```python
# backend/tts/cache.py
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from backend.stations.context import StationContext

from .contracts import SynthesisRequest, SynthesisResult, cache_identity_payload


class StationTTSCache:
    def __init__(self, context: StationContext) -> None:
        self.context = context
        self.root = Path(context.profile.runtime.cache_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate(self, request: SynthesisRequest) -> None:
        profile = self.context.profile
        if request.station_id != profile.station_id or request.language != profile.language:
            raise ValueError("cache request station/language mismatch")

    def key_for(self, request: SynthesisRequest) -> str:
        self._validate(request)
        encoded = json.dumps(cache_identity_payload(request), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _paths(self, key: str) -> tuple[Path, Path]:
        directory = (self.root / self.context.profile.station_id / key[:2]).resolve()
        if self.root not in directory.parents:
            raise ValueError("cache path escaped station root")
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.wav", directory / f"{key}.json"

    def get(self, request: SynthesisRequest, output_path: str) -> SynthesisResult | None:
        key = self.key_for(request); wav_path, metadata_path = self._paths(key)
        if not wav_path.is_file() or not metadata_path.is_file():
            return None
        stored = SynthesisResult.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        if hashlib.sha256(wav_path.read_bytes()).hexdigest() != stored.audio_sha256:
            wav_path.unlink(missing_ok=True); metadata_path.unlink(missing_ok=True); return None
        target = Path(output_path); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(wav_path, target)
        return stored.model_copy(update={"output_path": str(target), "source": "qwen-cache"})

    def put(self, request: SynthesisRequest, finished_wav: Path, result: SynthesisResult) -> SynthesisResult:
        key = self.key_for(request)
        if result.station_id != request.station_id or result.cache_key != key:
            raise ValueError("result identity does not match cache request")
        wav_path, metadata_path = self._paths(key)
        wav_partial, json_partial = wav_path.with_suffix(".wav.partial"), metadata_path.with_suffix(".json.partial")
        shutil.copyfile(finished_wav, wav_partial)
        stored = result.model_copy(update={"output_path": str(wav_path), "source": "qwen"})
        json_partial.write_text(stored.model_dump_json(indent=2), encoding="utf-8")
        os.replace(wav_partial, wav_path); os.replace(json_partial, metadata_path)
        return stored
```

- [ ] **Step 4: Run cache tests and verify they pass**

Run: `python -m pytest tests/backend/test_tts_cache.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Commit the station-cache slice**

```bash
git add backend/tts/cache.py tests/backend/test_tts_cache.py
git commit -m "feat: isolate Qwen audio cache by station"
```

### Task 6: Validate and Finish Broadcast WAV Audio

**Files:**
- Create: `backend/tts/audio_pipeline.py`
- Create: `tests/backend/test_tts_audio_pipeline.py`

**Owned files:** Only the two paths above.

**Forbidden files:** `backend/stations/**`, `backend/tts/qwen_tts.py`, `backend/radio_agent.py`, `release/**`.

**Interfaces:**
- Consumes: a raw Qwen WAV and `context.profile.audio.loudness_lufs` / `context.profile.audio.true_peak_dbtp`.
- Produces: `AudioMeasurement`, `inspect_wav(path)`, and `finish_qwen_wav(source, destination, loudness_lufs, true_peak_dbtp) -> AudioMeasurement`.

- [ ] **Step 1: Write failing WAV integrity and finishing tests**

```python
# tests/backend/test_tts_audio_pipeline.py
import math
import struct
import wave

import pytest

from backend.tts.audio_pipeline import AudioValidationError, finish_qwen_wav, inspect_wav


def write_tone(path, amplitude=9000, seconds=1.0, rate=24000):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
        frames = [int(amplitude * math.sin(2 * math.pi * 440 * index / rate)) for index in range(int(rate * seconds))]
        wav.writeframes(b"".join(struct.pack("<h", frame) for frame in frames))


def test_inspect_rejects_silence_stereo_and_empty_wav(tmp_path):
    silent = tmp_path / "silent.wav"; write_tone(silent, amplitude=0)
    with pytest.raises(AudioValidationError, match="silent"):
        inspect_wav(silent)
    empty = tmp_path / "empty.wav"
    with wave.open(str(empty), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(b"")
    with pytest.raises(AudioValidationError, match="frames"):
        inspect_wav(empty)


def test_finish_targets_minus_16_lufs_and_minus_1_dbtp(tmp_path, monkeypatch):
    source, destination = tmp_path / "raw.wav", tmp_path / "finished.wav"
    write_tone(source)
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-1] == "pipe:1":
            return type("Run", (), {"returncode": 0, "stdout": '{"input_i":"-24.00","input_tp":"-6.00","input_lra":"2.00","input_thresh":"-34.00","target_offset":"0.00"}', "stderr": ""})()
        destination.write_bytes(source.read_bytes())
        return type("Run", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr("backend.tts.audio_pipeline.subprocess.run", fake_run)
    monkeypatch.setattr("backend.tts.audio_pipeline.measure_loudness", lambda path: (-16.0, -1.0))
    measurement = finish_qwen_wav(source, destination, loudness_lufs=-16, true_peak_dbtp=-1)
    assert measurement.integrated_lufs == -16.0
    assert measurement.true_peak_dbtp == -1.0
    assert any("I=-16.0:TP=-1.0" in part for command in calls for part in command)


def test_finish_rejects_output_outside_qualification_tolerance(tmp_path, monkeypatch):
    source, destination = tmp_path / "raw.wav", tmp_path / "finished.wav"; write_tone(source)
    monkeypatch.setattr("backend.tts.audio_pipeline._run_loudnorm", lambda *args: destination.write_bytes(source.read_bytes()))
    monkeypatch.setattr("backend.tts.audio_pipeline.measure_loudness", lambda path: (-14.8, -0.4))
    with pytest.raises(AudioValidationError, match="loudness"):
        finish_qwen_wav(source, destination, loudness_lufs=-16, true_peak_dbtp=-1)
```

- [ ] **Step 2: Run tests and verify the missing module failure**

Run: `python -m pytest tests/backend/test_tts_audio_pipeline.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.tts.audio_pipeline'`.

- [ ] **Step 3: Implement WAV inspection and two-pass FFmpeg loudness finishing**

```python
# backend/tts/audio_pipeline.py
from __future__ import annotations

import audioop
import json
import os
import re
import subprocess
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
            channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            payload = wav.readframes(frames)
    except (wave.Error, OSError) as exc:
        raise AudioValidationError("invalid WAV container") from exc
    if channels != 1: raise AudioValidationError("WAV must be mono")
    if width != 2: raise AudioValidationError("WAV must be PCM-16")
    if frames <= 0: raise AudioValidationError("WAV has no frames")
    if rate < 16000 or rate > 48000: raise AudioValidationError("WAV sample rate is outside 16-48 kHz")
    if audioop.rms(payload, width) < 8: raise AudioValidationError("WAV is silent")
    return frames / rate, rate, channels


def _json_object(text: str) -> dict[str, str]:
    matches = re.findall(r"\{[^{}]+\}", text, re.DOTALL)
    if not matches: raise AudioValidationError("FFmpeg loudnorm analysis was missing")
    return json.loads(matches[-1])


def _run_loudnorm(source: Path, destination: Path, loudness: float, peak: float) -> None:
    analysis = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(source), "-af",
        f"loudnorm=I={loudness}:TP={peak}:LRA=11:print_format=json", "-f", "null", "pipe:1",
    ], capture_output=True, text=True, check=False)
    if analysis.returncode: raise AudioValidationError("FFmpeg loudness analysis failed")
    values = _json_object(analysis.stderr + analysis.stdout)
    filter_value = (
        f"loudnorm=I={loudness}:TP={peak}:LRA=11:"
        f"measured_I={values['input_i']}:measured_TP={values['input_tp']}:"
        f"measured_LRA={values['input_lra']}:measured_thresh={values['input_thresh']}:"
        f"offset={values['target_offset']}:linear=true,aresample=24000"
    )
    run = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(source), "-af", filter_value,
        "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(destination),
    ], capture_output=True, text=True, check=False)
    if run.returncode: raise AudioValidationError("FFmpeg loudness finishing failed")


def measure_loudness(path: Path) -> tuple[float, float]:
    run = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-",
    ], capture_output=True, text=True, check=False)
    if run.returncode: raise AudioValidationError("FFmpeg EBU R128 measurement failed")
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", run.stderr)
    peaks = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", run.stderr)
    if not integrated or not peaks: raise AudioValidationError("FFmpeg measurement summary was missing")
    return float(integrated[-1]), float(peaks[-1])


def finish_qwen_wav(source: Path, destination: Path, *, loudness_lufs: float, true_peak_dbtp: float) -> AudioMeasurement:
    if float(loudness_lufs) != -16.0 or float(true_peak_dbtp) != -1.0:
        raise ValueError("RadioTEDU finishing policy is fixed at -16 LUFS and -1 dBTP")
    inspect_wav(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".wav.partial")
    try:
        _run_loudnorm(source, temporary, -16.0, -1.0)
        duration, rate, channels = inspect_wav(temporary)
        integrated, peak = measure_loudness(temporary)
        if abs(integrated - (-16.0)) > 0.5 or peak > -0.8:
            raise AudioValidationError(f"loudness qualification failed: {integrated} LUFS, {peak} dBTP")
        os.replace(temporary, destination)
        return AudioMeasurement(duration, rate, channels, integrated, peak)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run unit tests and an installed-tool smoke check**

Run: `python -m pytest tests/backend/test_tts_audio_pipeline.py -q`

Expected: `3 passed`.

Run: `ffmpeg -version`

Expected: exit code `0` and a version banner; absence of FFmpeg is a broadcast-computer readiness failure.

- [ ] **Step 5: Commit the audio-finishing slice**

```bash
git add backend/tts/audio_pipeline.py tests/backend/test_tts_audio_pipeline.py
git commit -m "feat: finish Qwen clips for broadcast loudness"
```

### Task 7: Integrate Five-Clip Prebuffer and Music-Only Recovery

**Files:**
- Modify: `backend/radio_agent.py`
- Create: `tests/backend/test_qwen_prebuffer.py`
- Modify: `tests/backend/test_full_autonomy_runtime.py`

**Owned files:** Only the three paths above.

**Forbidden files:** `backend/stations/**`, `backend/tts/contracts.py`, `backend/tts/qwen_service.py`, public API/UI files, `release/**`.

**Interfaces:**
- Consumes: `StationContext`, `VoicePolicy`, `QwenTTSProvider`, `StationTTSCache`, `finish_qwen_wav`; the exact profile fields frozen globally.
- Produces: `RadioAgent(settings, context)`, `tts_runtime_status()`, `ensure_announcement_prebuffer()`, and `probe_qwen_recovery()`; channel modes `live`, `degraded`, and `music_only` are station-local.

- [ ] **Step 1: Write failing prebuffer, degradation, continuity, and recovery tests**

```python
# tests/backend/test_qwen_prebuffer.py
from backend.tts.contracts import QwenUnavailableError


def test_prebuffer_floor_comes_from_station_profile(agent_factory):
    agent = agent_factory(station_id="radiotedu-en", minimum_qwen_buffer=5)
    agent.tts.synthesize_request = agent_factory.valid_qwen_synthesis
    state = agent.ensure_announcement_prebuffer(max_to_prepare=5)
    assert state["required"] == 5
    assert state["ready"] == 5
    assert state["mode"] == "live"


def test_qwen_failure_keeps_music_playing_and_never_enqueues_fake_speech(agent_factory):
    agent = agent_factory(station_id="radiotedu-en", minimum_qwen_buffer=5, seeded_tracks=3)
    agent.tts.synthesize_request = lambda *args, **kwargs: (_ for _ in ()).throw(QwenUnavailableError("offline"))
    state = agent.ensure_announcement_prebuffer(max_to_prepare=1)
    assert state["mode"] == "music_only"
    queued = agent.queue_next_track()
    assert queued["started"] is True
    assert queued["speech_queued"] is False
    assert agent.playback.items[0].kind == "track"
    assert all(item.kind != "tts" for item in agent.playback.items)


def test_english_failure_does_not_change_french_state(agent_factory):
    english = agent_factory(station_id="radiotedu-en", minimum_qwen_buffer=5)
    french = agent_factory(station_id="radiotedu-fr", minimum_qwen_buffer=5)
    english._set_tts_mode("music_only", "Qwen synthesis failed")
    assert english.tts_runtime_status()["mode"] == "music_only"
    assert french.tts_runtime_status()["mode"] == "live"


def test_recovery_requires_real_probe_and_refills_to_five(agent_factory):
    agent = agent_factory(station_id="radiotedu-fr", minimum_qwen_buffer=5)
    agent._set_tts_mode("music_only", "Qwen unavailable")
    agent.tts.synthesize_request = agent_factory.valid_qwen_synthesis
    recovered = agent.probe_qwen_recovery()
    assert recovered["mode"] == "live"
    assert recovered["ready"] >= 5
    assert recovered["last_successful_probe_at"] is not None
```

- [ ] **Step 2: Run focused tests and verify current blocking behavior fails**

Run: `python -m pytest tests/backend/test_qwen_prebuffer.py -q`

Expected: FAIL because the existing `queue_next_track()` returns `announcement_prebuffer_not_ready` instead of queuing music, and no station-local TTS mode/recovery probe exists.

- [ ] **Step 3: Build trusted requests and cache/finish successful Qwen clips**

Update `RadioAgent.__init__` to accept `context: StationContext`, construct the strict provider with that context, and initialize `VoicePolicy`, `StationTTSCache`, and a station-local `_tts_state` dictionary. Replace every `self.tts.synthesize(...)` call with one private method:

```python
def _synthesize_announcement(self, text: str, output: Path, *, program: dict, label: AnnouncementLabel) -> SynthesisResult:
    normalized, voice = self.voice_policy.select(
        program_id=program["id"], daypart=self._program_daypart(program),
        announcement_label=label, text=text,
    )
    request = SynthesisRequest(
        request_id=f"{self.context.profile.station_id}-{uuid.uuid4().hex}",
        station_id=self.context.profile.station_id,
        language=self.context.profile.language,
        normalized_text=normalized, announcement_label=label, voice=voice,
    )
    cached = self.tts_cache.get(request, str(output))
    if cached is not None:
        return cached
    raw = output.with_suffix(".raw.wav")
    try:
        result = self.tts.synthesize_request(request, str(raw))
        measurement = finish_qwen_wav(
            raw, output,
            loudness_lufs=self.context.profile.audio.loudness_lufs,
            true_peak_dbtp=self.context.profile.audio.true_peak_dbtp,
        )
        finished = result.model_copy(update={
            "output_path": str(output), "duration_seconds": measurement.duration_seconds,
            "sample_rate_hz": measurement.sample_rate_hz, "channels": 1,
            "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        })
        self.tts_cache.put(request, output, finished)
        return finished
    finally:
        raw.unlink(missing_ok=True)
```

Map existing call sites exactly: `say -> listener_reply`, `queue_listener_reply -> listener_reply`, `_narrate -> track_intro`, weather -> `weather`, news -> `news`, program boundary copy -> `program_open` or `program_close`.

- [ ] **Step 4: Make prebuffer failure degrade speech without blocking music**

```python
def _set_tts_mode(self, mode: str, reason: str | None) -> None:
    if mode not in {"live", "degraded", "music_only"}:
        raise ValueError(f"invalid TTS mode: {mode}")
    self._tts_state.update({"mode": mode, "reason": reason, "changed_at": now_iso()})


def tts_runtime_status(self) -> dict:
    readiness = self.announcement_readiness()
    return {**self._tts_state, **readiness, "station_id": self.context.profile.station_id}
```

In `ensure_announcement_prebuffer`, set `required = max(5, int(context.profile.audio.minimum_qwen_buffer))`. Catch only `QwenUnavailableError` and `AudioValidationError`, record the candidate row as `failed` without a playable path, retry once, and set `degraded` while at least one valid Qwen clip remains or `music_only` when none remains. Never catch an error by calling another provider.

In `queue_next_track`, remove both early returns for `announcement_prebuffer_not_ready` and `ready_announcement_missing`. Always select and queue a track when candidates exist. Queue a `tts` item only when `_consume_ready_announcement()` returns a valid existing WAV. Return:

```python
return {
    "started": True,
    "track_id": int(selected["id"]),
    "dj_line": announcement["text"] if announcement else None,
    "speech_queued": announcement is not None,
    "tts_mode": self._tts_state["mode"],
}
```

- [ ] **Step 5: Require a real recovery probe and refill before live state**

```python
def probe_qwen_recovery(self) -> dict:
    if self.tts.health().get("status") != "ready":
        return self.tts_runtime_status()
    program = current_program(self.settings)
    probe_path = Path(self.context.profile.runtime.announcement_root) / "health" / "qwen-probe.wav"
    try:
        self._synthesize_announcement("RadioTEDU voice systems are ready.", probe_path, program=program, label="station_id")
    except (QwenUnavailableError, AudioValidationError) as exc:
        self._set_tts_mode("music_only", str(exc)); return self.tts_runtime_status()
    self._tts_state["last_successful_probe_at"] = now_iso()
    readiness = self.ensure_announcement_prebuffer(program["id"])
    self._set_tts_mode("live" if readiness["ready"] >= max(5, self.context.profile.audio.minimum_qwen_buffer) else "degraded", None)
    return self.tts_runtime_status()
```

- [ ] **Step 6: Run focused and existing autonomy tests**

Run: `python -m pytest tests/backend/test_qwen_prebuffer.py tests/backend/test_full_autonomy_runtime.py -q`

Expected: all selected tests PASS, with explicit assertions that the track queue advances during Qwen failure and no non-Qwen or silent clip is inserted.

- [ ] **Step 7: Commit the live-continuity slice**

```bash
git add backend/radio_agent.py tests/backend/test_qwen_prebuffer.py tests/backend/test_full_autonomy_runtime.py
git commit -m "feat: keep radio live during Qwen degradation"
```

### Task 8: Commission and Qualify the Eight Qwen Voices

**Files:**
- Create: `scripts/commission_qwen_voices.py`
- Create: `scripts/qualify_qwen_voice_pack.py`
- Create: `tests/backend/test_qwen_voice_qualification.py`
- Create after approval: `config/voices/radiotedu-en-voices-v1.json`
- Create after approval: `config/voices/radiotedu-fr-voices-v1.json`

**Owned files:** Only the five paths above and generated voice assets beneath the operator-supplied station voice root.

**Forbidden files:** Application modules, `backend/stations/**`, other tests, `release/**`.

**Interfaces:**
- Consumes: Task 2 candidate manifests, Task 3 service, exact model checksum, reviewer CSV with 1-5 warmth/naturalness/clarity/program-fit scores, blind host guesses, and pronunciation outcomes.
- Produces: two frozen four-host packs, reports for 60 scripts per host, blind identity, pronunciation, and 500 generated clips per language; exit code is nonzero on any failed gate.

- [ ] **Step 1: Write failing qualification-gate tests**

```python
# tests/backend/test_qwen_voice_qualification.py
from scripts.qualify_qwen_voice_pack import evaluate_report


def report(language="en", clips=500, scripts_per_host=60, score=4.2, identity=0.92):
    return {
        "language": language, "hosts": 4, "clips_generated": clips,
        "scripts_per_host": scripts_per_host, "minimum_mean_review_score": score,
        "blind_identity_accuracy": identity, "corrupt_clips": 0, "silent_clips": 0,
        "clipped_clips": 0, "pronunciation_failures": 0,
        "loudness_outliers": 0, "peak_outliers": 0,
    }


def test_accepts_complete_language_report():
    assert evaluate_report(report()) == []


def test_rejects_each_release_gate():
    failures = report(clips=499, scripts_per_host=59, score=3.99, identity=0.899)
    failures.update(corrupt_clips=1, silent_clips=1, clipped_clips=1, pronunciation_failures=1,
                    loudness_outliers=1, peak_outliers=1)
    errors = evaluate_report(failures)
    assert len(errors) == 10
    assert any("500" in error for error in errors)
    assert any("4.0" in error for error in errors)
    assert any("90%" in error for error in errors)


def test_pack_requires_exact_four_host_casts(frozen_pack_loader):
    english = frozen_pack_loader("config/voices/radiotedu-en-voices-v1.json")
    french = frozen_pack_loader("config/voices/radiotedu-fr-voices-v1.json")
    assert [host["host_id"] for host in english["hosts"]] == ["maya", "elliot", "selin", "theo"]
    assert [host["host_id"] for host in french["hosts"]] == ["camille", "mathieu", "elodie", "jules"]
    assert all(host["approved"] is True for pack in (english, french) for host in pack["hosts"])
```

- [ ] **Step 2: Run tests and verify the missing scripts failure**

Run: `python -m pytest tests/backend/test_qwen_voice_qualification.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'scripts.qualify_qwen_voice_pack'`.

- [ ] **Step 3: Implement deterministic gate evaluation**

```python
# scripts/qualify_qwen_voice_pack.py
from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate_report(report: dict) -> list[str]:
    errors = []
    if report.get("hosts") != 4: errors.append("exactly four approved hosts are required")
    if report.get("scripts_per_host", 0) < 60: errors.append("each host requires at least 60 evaluation scripts")
    if report.get("minimum_mean_review_score", 0) < 4.0: errors.append("every host requires at least 4.0/5 mean review score")
    if report.get("blind_identity_accuracy", 0) < 0.90: errors.append("blind host identity accuracy must be at least 90%")
    if report.get("clips_generated", 0) < 500: errors.append("each language requires at least 500 generated clips")
    for key in ("corrupt_clips", "silent_clips", "clipped_clips", "pronunciation_failures", "loudness_outliers", "peak_outliers"):
        if report.get(key, 0) != 0: errors.append(f"{key} must equal zero")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path); args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    errors = evaluate_report(report)
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2, ensure_ascii=False))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__": main()
```

- [ ] **Step 4: Implement candidate generation and pack freezing**

`scripts/commission_qwen_voices.py` must provide four explicit commands:

```text
generate --candidate-manifest <json> --output-root <path>
record-review --candidate-root <path> --review-csv <csv>
freeze --candidate-manifest <json> --review-csv <csv> --model-sha256 <sha256> --voice-root <path> --output <json>
verify --pack <json> --voice-root <path>
```

`generate` submits three VoiceDesign candidates for each of four hosts to the Qwen service using a fixed six-part audition script: station identification, track introduction, weather, news, listener reply, and program open/close. `freeze` accepts exactly one candidate per host only when every category mean is at least `4.0`; it hashes the approved reference WAV, clone prompt, transcript, style anchors, pronunciation dictionary, and model file into the output manifest. `verify` recomputes every hash and rejects missing/changed assets, a station/language mismatch, fewer or more than four hosts, or any unapproved host.

Use this complete review-row contract:

```python
REVIEW_FIELDS = (
    "station_id", "language", "host_id", "candidate_id", "reviewer_id",
    "warmth", "naturalness", "clarity", "program_fit", "approved",
    "blind_expected_host", "blind_guessed_host", "pronunciation_passed",
)
SCORED_FIELDS = ("warmth", "naturalness", "clarity", "program_fit")
```

Reject a row when a score is outside `1..5`, French review lacks a native-French reviewer flag, the reviewer ID is blank, or the blind expected host equals a reviewer-supplied free-text identity rather than a host ID from the candidate manifest.

- [ ] **Step 5: Commission English and French packs on the broadcast computer**

Run:

```bash
python scripts/commission_qwen_voices.py generate --candidate-manifest config/voices/radiotedu-en-candidates-v1.json --output-root data/voice-commissioning/radiotedu-en
python scripts/commission_qwen_voices.py generate --candidate-manifest config/voices/radiotedu-fr-candidates-v1.json --output-root data/voice-commissioning/radiotedu-fr
```

Expected: 12 audition candidate directories per language, each containing six valid Qwen WAVs and request metadata; no non-Qwen files.

After human review, run:

```bash
python scripts/commission_qwen_voices.py freeze --candidate-manifest config/voices/radiotedu-en-candidates-v1.json --review-csv data/voice-commissioning/radiotedu-en/reviews.csv --model-sha256 %QWEN_MODEL_SHA256% --voice-root data/voices/radiotedu-en --output config/voices/radiotedu-en-voices-v1.json
python scripts/commission_qwen_voices.py freeze --candidate-manifest config/voices/radiotedu-fr-candidates-v1.json --review-csv data/voice-commissioning/radiotedu-fr/reviews.csv --model-sha256 %QWEN_MODEL_SHA256% --voice-root data/voices/radiotedu-fr --output config/voices/radiotedu-fr-voices-v1.json
```

Expected English hosts: Maya, Elliot, Selin, Theo. Expected French hosts: Camille, Mathieu, Élodie, Jules. Every selected host has at least `4.0/5` in warmth, naturalness, clarity, and program fit.

- [ ] **Step 6: Run 60-script identity/pronunciation review and 500-clip qualification per language**

Run:

```bash
python scripts/qualify_qwen_voice_pack.py data/voice-commissioning/radiotedu-en/qualification-report.json
python scripts/qualify_qwen_voice_pack.py data/voice-commissioning/radiotedu-fr/qualification-report.json
```

Expected for each report: four hosts, at least 60 scripts per host, minimum mean review score `>=4.0`, blind identity accuracy `>=0.90`, at least 500 generated clips, and zero corrupt, silent, clipped, pronunciation-failed, loudness-outlier, or peak-outlier clips. French results require native-French sign-off.

- [ ] **Step 7: Run qualification tests and commit scripts plus frozen manifests**

Run: `python -m pytest tests/backend/test_qwen_voice_qualification.py -q`

Expected: `3 passed`.

```bash
git add scripts/commission_qwen_voices.py scripts/qualify_qwen_voice_pack.py tests/backend/test_qwen_voice_qualification.py config/voices/radiotedu-en-voices-v1.json config/voices/radiotedu-fr-voices-v1.json
git commit -m "feat: commission bilingual Qwen voice packs"
```

### Task 9: Qwen-Only Negative Regression and Full Verification

**Files:**
- Modify only if the negative tests expose a residual reference: `backend/tts/factory.py`
- Modify only if the negative tests expose a residual reference: `backend/tts/qwen_tts.py`
- Modify only if the negative tests expose a residual reference: `backend/tts/qwen_service.py`
- Modify only if the negative tests expose a residual reference: `backend/radio_agent.py`
- Modify: `tests/backend/test_core_behaviour.py`
- Modify: `tests/backend/test_full_autonomy_runtime.py`

**Owned files:** Only the six paths above; production paths may change solely to remove a forbidden legacy reference demonstrated by Step 2.

**Forbidden files:** All other production code, all voice manifests/assets, `backend/stations/**`, `release/**`.

**Interfaces:**
- Consumes: every interface and artifact from Tasks 1-8.
- Produces: final evidence that forbidden speech cannot execute, station caches cannot cross, failed Qwen cannot create a playable speech item, and both stations continue music.

- [ ] **Step 1: Add the negative regression matrix**

```python
@pytest.mark.parametrize("forbidden", ["sapi", "piper", "dummy", "cloud"])
def test_non_qwen_provider_configuration_fails_closed(forbidden, station_context):
    with pytest.raises((ValueError, TypeError), match="Qwen|qwen"):
        build_tts_provider(station_context, forbidden)


def test_qwen_outage_never_creates_speech_file_or_tts_queue_item(autonomy_runtime):
    runtime = autonomy_runtime(qwen_status=503, stations=("radiotedu-en", "radiotedu-fr"))
    runtime.tick_all()
    for station in runtime.stations:
        assert station.agent.tts_runtime_status()["mode"] == "music_only"
        assert station.playback.current_or_next_track() is not None
        assert all(item.kind != "tts" for item in station.playback.items)
        assert list(station.context.profile.runtime.announcement_root.rglob("*.wav")) == []


def test_cross_station_voice_and_cache_requests_fail_closed(english_context, french_context, english_request):
    with pytest.raises(ValueError, match="station"):
        StationTTSCache(french_context).key_for(english_request)
    with pytest.raises(ValueError, match="station"):
        QwenTTSProvider(french_context, "http://127.0.0.1:8090").synthesize_request(english_request, "clip.wav")
```

- [ ] **Step 2: Run the negative tests and verify they expose any remaining legacy path**

Run: `python -m pytest tests/backend/test_core_behaviour.py tests/backend/test_full_autonomy_runtime.py -q`

Expected before cleanup: any remaining legacy provider/fallback path causes at least one explicit FAIL naming that provider or a generated speech item.

- [ ] **Step 3: Remove only the legacy references exposed by the tests**

Delete remaining production imports, settings branches, and call sites for `SapiTTSProvider`, `PiperTTSProvider`, `DummyTTSProvider`, `fallback_tts_provider`, and shell-command synthesis. Keep legacy modules importable only for historical unit tests until a later removal migration; they must be unreachable from application startup, `RadioAgent`, factory, service, and qualification paths.

- [ ] **Step 4: Run the complete focused Qwen suite**

Run:

```bash
python -m pytest tests/backend/test_tts_contracts.py tests/backend/test_tts_voice_policy.py tests/backend/test_qwen_tts_service.py tests/backend/test_qwen_tts_client.py tests/backend/test_tts_cache.py tests/backend/test_tts_audio_pipeline.py tests/backend/test_qwen_prebuffer.py tests/backend/test_qwen_voice_qualification.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 5: Run the complete backend regression suite**

Run: `python -m pytest tests/backend -q`

Expected: all backend tests PASS with zero failures, errors, or unexpected skips.

- [ ] **Step 6: Run static forbidden-provider and incomplete-marker scans**

Run:

```bash
rg -n "SapiTTSProvider|PiperTTSProvider|DummyTTSProvider|fallback_tts_provider|qwen->" backend/tts/factory.py backend/tts/qwen_tts.py backend/tts/qwen_service.py backend/radio_agent.py
rg -n "pass$|NotImplementedError" backend/tts/contracts.py backend/tts/voice_policy.py backend/tts/cache.py backend/tts/audio_pipeline.py backend/tts/qwen_service.py
```

Expected: both commands return no matches. Protocol method ellipses in `backend/tts/base.py` are excluded intentionally.

- [ ] **Step 7: Verify both frozen packs and qualification reports**

Run:

```bash
python scripts/commission_qwen_voices.py verify --pack config/voices/radiotedu-en-voices-v1.json --voice-root data/voices/radiotedu-en
python scripts/commission_qwen_voices.py verify --pack config/voices/radiotedu-fr-voices-v1.json --voice-root data/voices/radiotedu-fr
python scripts/qualify_qwen_voice_pack.py data/voice-commissioning/radiotedu-en/qualification-report.json
python scripts/qualify_qwen_voice_pack.py data/voice-commissioning/radiotedu-fr/qualification-report.json
```

Expected: all four commands exit `0`; hashes match, both casts contain exactly four approved hosts, every host has 60 reviewed scripts, both blind identity scores are at least 90%, both minimum review scores are at least 4/5, and both 500-clip runs have zero audio failures.

- [ ] **Step 8: Commit final verification coverage**

```bash
git add tests/backend/test_core_behaviour.py tests/backend/test_full_autonomy_runtime.py
git commit -m "test: qualify Qwen-only bilingual speech"
```

## Orchestrator Completion Gate

The orchestrator accepts this plan only when all nine task commits are independently reviewed, the full backend suite passes, both qualification reports pass, `GET /health` is ready after a real warm-up, each station has five valid prepared Qwen clips, and a forced Qwen outage leaves both music streams running without any substitute speech. The implementation branch must contain no edits to `release/` and no change to the frozen `StationProfile`/`StationContext` interface names.
