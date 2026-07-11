"""Typed synthesis provider boundary for the Qwen-only broadcast path."""

from __future__ import annotations

from typing import Protocol

from .contracts import SynthesisRequest, SynthesisResult


class TTSProvider(Protocol):
    provider_name: str

    def synthesize_request(self, request: SynthesisRequest, output_path: str) -> SynthesisResult: ...

    def health(self) -> dict[str, object]: ...
