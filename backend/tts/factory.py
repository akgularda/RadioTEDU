"""Construct the single permitted speech provider."""

from __future__ import annotations

import os

from backend.stations.context import StationContext

from .qwen_tts import QwenTTSProvider


def build_tts_provider(context: StationContext, service_url: str | None = None) -> QwenTTSProvider:
    """Return the local Qwen client; provider selection and fallback are forbidden."""
    if service_url is None:
        service_url = os.environ.get("QWEN_TTS_SERVICE_URL", "http://127.0.0.1:8090")
    return QwenTTSProvider(context, service_url)
