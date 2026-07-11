"""Qwen-only typed text-to-speech interfaces."""

from .base import TTSProvider
from .factory import build_tts_provider
from .qwen_tts import QwenTTSProvider

__all__ = ["QwenTTSProvider", "TTSProvider", "build_tts_provider"]
