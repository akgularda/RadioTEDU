"""Strict HTTP client for the local persistent Qwen service."""

from __future__ import annotations

import hashlib
import json
import os
import wave
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.stations.context import StationContext

from .contracts import QwenUnavailableError, SynthesisRequest, SynthesisResult, cache_identity_payload


class QwenTTSProvider:
    provider_name = "qwen"

    def __init__(
        self,
        context: StationContext,
        service_url: str,
        timeout_seconds: float = 45.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(service_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Qwen service URL must use loopback HTTP")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Qwen service URL must be a plain loopback endpoint")
        self.context = context
        self.service_url = service_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds, transport=transport)
        self.last_error: str | None = None

    def synthesize_request(self, request: SynthesisRequest, output_path: str) -> SynthesisResult:
        profile = self.context.profile
        if (
            request.station_id != profile.station_id
            or request.language != profile.language
            or request.locale != profile.locale
        ):
            raise ValueError("synthesis request does not belong to provider station")

        response: httpx.Response | None = None
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
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "audio/wav":
            raise QwenUnavailableError("Qwen response must be audio/wav")
        if response.headers.get("x-audio-sha256") != digest:
            raise QwenUnavailableError("Qwen response checksum mismatch")
        if response.headers.get("x-model-checksum") != request.voice.model_checksum:
            raise QwenUnavailableError("Qwen response model checksum mismatch")

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.partial")
        temporary.write_bytes(payload)
        try:
            with wave.open(str(temporary), "rb") as wav:
                channels = wav.getnchannels()
                rate = wav.getframerate()
                frames = wav.getnframes()
            if channels != 1 or frames == 0 or not 16000 <= rate <= 48000:
                raise QwenUnavailableError("Qwen response must be non-empty mono broadcast WAV")
            if response.headers.get("x-sample-rate-hz") != str(rate):
                raise QwenUnavailableError("Qwen response sample-rate header mismatch")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        identity = json.dumps(
            cache_identity_payload(request), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        self.last_error = None
        return SynthesisResult(
            request_id=request.request_id,
            station_id=request.station_id,
            output_path=str(target),
            cache_key=hashlib.sha256(identity).hexdigest(),
            audio_sha256=digest,
            duration_seconds=frames / rate,
            sample_rate_hz=rate,
            channels=1,
            source="qwen",
        )

    def health(self) -> dict[str, object]:
        try:
            response = self.client.get(f"{self.service_url}/health")
            response.raise_for_status()
            payload = response.json()
            return {**payload, "provider": "qwen", "last_error": self.last_error or payload.get("last_error")}
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "provider": "qwen",
                "status": "unhealthy",
                "warmed": False,
                "last_error": f"{type(exc).__name__}: {exc}",
            }
