from __future__ import annotations

import wave
from pathlib import Path


class DummyTTSProvider:
    provider_name = "dummy"
    last_error = None

    def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 8000)
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
        return str(path)

    def health(self) -> dict:
        return {
            "provider": "dummy",
            "active_provider": self.provider_name,
            "status": "ready",
            "configured": True,
            "last_error": self.last_error,
        }
