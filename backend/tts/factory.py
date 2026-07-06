from __future__ import annotations

from .dummy_tts import DummyTTSProvider
from .piper_tts import PiperTTSProvider
from .qwen_tts import QwenTTSProvider
from .sapi_tts import SapiTTSProvider


def build_tts_provider(settings):
    fallback = _base_provider(settings.fallback_tts_provider, settings)
    provider = settings.tts_provider.lower().strip()
    if provider == "qwen":
        return QwenTTSProvider(settings.qwen_tts_command, fallback=fallback)
    if provider == "piper":
        return PiperTTSProvider(settings.piper_tts_command, fallback=fallback)
    return _base_provider(provider, settings)


def _base_provider(name: str, settings):
    provider = name.lower().strip()
    if provider == "sapi":
        return SapiTTSProvider()
    if provider == "piper":
        return PiperTTSProvider(settings.piper_tts_command, fallback=DummyTTSProvider())
    return DummyTTSProvider()
