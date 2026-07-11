"""Construct the single permitted speech provider."""

from __future__ import annotations

from backend.stations.context import StationContext

from .qwen_tts import QwenTTSProvider


def build_tts_provider(context: StationContext, service_url: str) -> QwenTTSProvider:
    """Return the local Qwen client; provider selection and fallback are forbidden."""
    return QwenTTSProvider(context, service_url)
