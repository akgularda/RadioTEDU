"""Legacy test utility; production speech must never import this module."""

from __future__ import annotations

from .qwen_tts import QwenTTSProvider


class PiperTTSProvider(QwenTTSProvider):
    """Command-template provider for optional Piper installations."""

    def __init__(self, command_template: str = "", fallback=None) -> None:
        super().__init__(command_template, fallback=fallback)
        if self.command_template:
            self.provider_name = "piper"
