from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from backend.stations.context import StationContext

from .contracts import SynthesisRequest, SynthesisResult, cache_identity_payload


class StationTTSCache:
    def __init__(self, context: StationContext) -> None:
        self.context = context
        self.root = Path(context.profile.runtime.cache_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate(self, request: SynthesisRequest) -> None:
        profile = self.context.profile
        if request.station_id != profile.station_id or request.language != profile.language:
            raise ValueError("cache request station/language mismatch")

    def key_for(self, request: SynthesisRequest) -> str:
        self._validate(request)
        identity = cache_identity_payload(request)
        identity.update(
            {
                "daypart": request.announcement_label,
                "approved_voice_reference": request.voice.reference_audio_path,
            }
        )
        encoded = json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _paths(self, key: str) -> tuple[Path, Path]:
        directory = (self.root / self.context.profile.station_id / key[:2]).resolve()
        try:
            directory.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("cache path escaped station root") from exc
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.wav", directory / f"{key}.json"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _partial_path(directory: Path, suffix: str) -> Path:
        descriptor, name = tempfile.mkstemp(
            dir=directory, prefix=".qwen-cache-", suffix=suffix
        )
        os.close(descriptor)
        return Path(name)

    @staticmethod
    def _discard(wav_path: Path, metadata_path: Path) -> None:
        wav_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    def get(self, request: SynthesisRequest, output_path: str) -> SynthesisResult | None:
        key = self.key_for(request)
        wav_path, metadata_path = self._paths(key)
        if not wav_path.is_file() or not metadata_path.is_file():
            return None

        try:
            stored = SynthesisResult.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
            if stored.station_id != request.station_id or stored.cache_key != key:
                raise ValueError("cache metadata identity mismatch")
            if self._sha256(wav_path) != stored.audio_sha256:
                raise ValueError("cache audio checksum mismatch")
        except (OSError, ValueError):
            self._discard(wav_path, metadata_path)
            return None

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wav_path, target)
        return stored.model_copy(
            update={"output_path": str(target), "source": "qwen-cache"}
        )

    def put(
        self, request: SynthesisRequest, finished_wav: Path, result: SynthesisResult
    ) -> SynthesisResult:
        key = self.key_for(request)
        if result.station_id != request.station_id or result.cache_key != key:
            raise ValueError("result identity does not match cache request")
        if not finished_wav.is_file():
            raise ValueError("finished Qwen WAV is missing")

        wav_path, metadata_path = self._paths(key)
        wav_partial = self._partial_path(wav_path.parent, ".wav.partial")
        metadata_partial = self._partial_path(metadata_path.parent, ".json.partial")
        try:
            shutil.copyfile(finished_wav, wav_partial)
            stored = result.model_copy(
                update={
                    "output_path": str(wav_path),
                    "audio_sha256": self._sha256(wav_partial),
                    "source": "qwen",
                }
            )
            metadata_partial.write_text(
                stored.model_dump_json(indent=2), encoding="utf-8"
            )
            os.replace(wav_partial, wav_path)
            os.replace(metadata_partial, metadata_path)
            return stored
        except Exception:
            wav_partial.unlink(missing_ok=True)
            metadata_partial.unlink(missing_ok=True)
            raise
