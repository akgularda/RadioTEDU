from __future__ import annotations

import subprocess
from pathlib import Path

from .dummy_tts import DummyTTSProvider


class QwenTTSProvider:
    def __init__(self, command_template: str = "", fallback=None) -> None:
        self.command_template = command_template.strip()
        self.fallback = fallback or DummyTTSProvider()
        self.provider_name = "qwen" if self.command_template else self.fallback.provider_name

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
        except Exception:
            self.provider_name = f"qwen->{self.fallback.provider_name}"
            return self.fallback.synthesize(text, output_path, voice)
        if not path.exists():
            self.provider_name = f"qwen->{self.fallback.provider_name}"
            return self.fallback.synthesize(text, output_path, voice)
        self.provider_name = "qwen"
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
        return str(path)


def _shell_arg(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
