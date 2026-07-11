from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StationId = Literal["radiotedu-en", "radiotedu-fr"]
StationLanguage = Literal["en", "fr"]
StationLocale = Literal["en-US", "fr-FR"]
AnnouncementLabel = Literal[
    "station_id",
    "track_intro",
    "track_outro",
    "weather",
    "news",
    "listener_reply",
    "program_open",
    "program_close",
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
