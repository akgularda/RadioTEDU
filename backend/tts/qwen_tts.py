from __future__ import annotations

import subprocess
from pathlib import Path

from .dummy_tts import DummyTTSProvider


class QwenTTSProvider:
    def __init__(self, command_template: str = "", fallback=None) -> None:
        self.command_template = command_template.strip()
        self.fallback = fallback or DummyTTSProvider()
        self.provider_name = "qwen" if self.command_template else self.fallback.provider_name
        self.last_error: str | None = None

    def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        if not self.command_template:
            return self.fallback.synthesize(text, output_path, voice)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        command = self.command_template.format(
            text=_shell_arg(text),
            output_path=_shell_arg(str(path)),
            voice=_shell_arg(voice or ""),
        )
        try:
            subprocess.run(command, shell=True, check=True, timeout=45)
        except Exception as exc:
            self.last_error = str(exc)
            self.provider_name = f"qwen->{self.fallback.provider_name}"
            return self.fallback.synthesize(text, output_path, voice)
        if not path.exists():
            self.last_error = "command_completed_without_output"
            self.provider_name = f"qwen->{self.fallback.provider_name}"
            return self.fallback.synthesize(text, output_path, voice)
        self.provider_name = "qwen"
        self.last_error = None
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
        return str(path)

    def health(self) -> dict:
        configured = bool(self.command_template)
        return {
            "provider": "qwen",
            "active_provider": self.provider_name,
            "status": "ready" if configured and self.provider_name == "qwen" else ("fallback" if not configured or "->" in self.provider_name else "ready"),
            "configured": configured,
            "command_configured": configured,
            "last_error": self.last_error,
        }


def _shell_arg(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
