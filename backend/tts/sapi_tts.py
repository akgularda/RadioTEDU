"""Legacy test utility; production speech must never import this module."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .dummy_tts import DummyTTSProvider


class SapiTTSProvider:
    """Windows SAPI voice provider for fully local spoken segments."""

    provider_name = "sapi"

    def __init__(self, command_path: str | None = None, fallback=None) -> None:
        self.command_path = command_path or self._detect_command()
        self.fallback = fallback or DummyTTSProvider()

    def synthesize(self, text: str, output_path: str, voice: str | None = None) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._invoke_sapi(text, path, voice)
        except Exception:
            return self.fallback.synthesize(text, output_path, voice)
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
        return str(path)

    def _invoke_sapi(self, text: str, output_path: Path, voice: str | None = None) -> None:
        escaped_text = text.replace("'", "''")
        escaped_path = str(output_path).replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        )
        if voice:
            escaped_voice = voice.replace("'", "''")
            script += f"$speaker.SelectVoice('{escaped_voice}'); "
        script += (
            f"$speaker.SetOutputToWaveFile('{escaped_path}'); "
            f"$speaker.Speak('{escaped_text}'); "
            "$speaker.Dispose();"
        )
        subprocess.run([self.command_path, "-NoProfile", "-Command", script], check=True, timeout=45)

    @staticmethod
    def _detect_command() -> str:
        return shutil.which("powershell") or shutil.which("pwsh") or "powershell"
