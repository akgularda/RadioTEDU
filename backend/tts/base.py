from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        ...
