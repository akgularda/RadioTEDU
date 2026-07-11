"""Curate validated imaging into station-scoped release media paths."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Final

from backend.audio.catalog_analyzer import FfprobeBinary, analyze_audio
from backend.audio.models import AudioAnalysis, AudioAnalysisError, AudioValidationStatus


MANIFEST_FILENAME: Final = "manifest.json"
MANIFEST_SCHEMA_VERSION: Final = 1
ASSET_DIRECTORY: Final = "assets"
SUPPORTED_CATEGORIES: Final = frozenset({"jingle", "program-promo"})
STATION_LANGUAGES: Final = {"radiotedu-en": "en", "radiotedu-fr": "fr"}
_CHECKSUM_PATTERN: Final = re.compile(r"[0-9a-f]{64}")


class ImagingError(RuntimeError):
    """Base error for station imaging import and access."""


class ImagingImportError(ImagingError):
    """A source asset cannot be safely added to the packaged library."""


class ImagingManifestError(ImagingError):
    """A packaged station manifest is invalid or unsafe to consume."""


@dataclass(frozen=True, slots=True)
class ImagingAsset:
    """One validated, release-relative imaging asset."""

    station_id: str
    language: str
    category: str
    duration_seconds: float
    checksum_sha256: str
    relative_path: PurePosixPath


@dataclass(frozen=True, slots=True)
class ImagingImportResult:
    """Stable result of an explicit imaging import invocation."""

    library: "ImagingLibrary"
    imported_count: int
    deduplicated_count: int


@dataclass(frozen=True, slots=True)
class ImagingLibrary:
    """Read-only runtime view of one station's packaged imaging library."""

    release_root: Path
    station_id: str
    assets: tuple[ImagingAsset, ...]

    @classmethod
    def open(cls, release_root: str | Path, station_id: str) -> "ImagingLibrary":
        """Load only validated assets beneath this station's release media root."""

        language = _station_language(station_id)
        root = _station_root(release_root, station_id)
        manifest_path = root / MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise ImagingManifestError("station imaging manifest is missing")
        assets = _read_manifest(manifest_path, root, station_id, language)
        return cls(
            release_root=Path(release_root).resolve(),
            station_id=station_id,
            assets=assets,
        )

    def asset_paths(self) -> tuple[Path, ...]:
        """Return paths already proven to reside in this station's package."""

        root = _station_root(self.release_root, self.station_id)
        return tuple((root / Path(asset.relative_path)).resolve() for asset in self.assets)


def import_imaging(
    source_path: str | Path,
    release_root: str | Path,
    *,
    station_id: str,
    category: str,
    ffprobe_binary: FfprobeBinary = "ffprobe",
) -> ImagingImportResult:
    """Validate and package a supplied source directory without altering it.

    The source must be supplied explicitly.  This function deliberately has no
    Downloads-folder default, while still accepting such a folder when a user
    invokes the importer with that path.
    """

    language = _station_language(station_id)
    if category not in SUPPORTED_CATEGORIES:
        raise ImagingImportError("unsupported imaging category")

    candidates = _analyze_sources(source_path, ffprobe_binary)
    root = _station_root(release_root, station_id)
    manifest_path = root / MANIFEST_FILENAME
    existing_assets = (
        _read_manifest(manifest_path, root, station_id, language)
        if manifest_path.exists()
        else ()
    )
    assets_by_checksum = {asset.checksum_sha256: asset for asset in existing_assets}
    assets = list(existing_assets)
    imported_count = 0
    deduplicated_count = 0

    for analysis, suffix in candidates:
        if analysis.checksum_sha256 in assets_by_checksum:
            deduplicated_count += 1
            continue

        relative_path = PurePosixPath(
            ASSET_DIRECTORY, f"{analysis.checksum_sha256}{suffix.lower()}"
        )
        asset = ImagingAsset(
            station_id=station_id,
            language=language,
            category=category,
            duration_seconds=analysis.duration_seconds,
            checksum_sha256=analysis.checksum_sha256,
            relative_path=relative_path,
        )
        _copy_packaged_asset(analysis.source_path, root / Path(relative_path), asset)
        assets.append(asset)
        assets_by_checksum[asset.checksum_sha256] = asset
        imported_count += 1

    if imported_count:
        _write_manifest(manifest_path, station_id, assets)

    return ImagingImportResult(
        library=ImagingLibrary.open(release_root, station_id),
        imported_count=imported_count,
        deduplicated_count=deduplicated_count,
    )


def _station_language(station_id: str) -> str:
    try:
        return STATION_LANGUAGES[station_id]
    except KeyError as error:
        raise ImagingImportError("unsupported station") from error


def _station_root(release_root: str | Path, station_id: str) -> Path:
    _station_language(station_id)
    return Path(release_root).resolve() / "media" / "imaging" / station_id


def _analyze_sources(
    source_path: str | Path, ffprobe_binary: FfprobeBinary
) -> tuple[tuple[AudioAnalysis, str], ...]:
    source = Path(source_path).resolve()
    if source.is_file():
        source_files: Iterable[Path] = (source,)
    elif source.is_dir():
        source_files = sorted(
            (path for path in source.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(source).as_posix(),
        )
    else:
        raise ImagingImportError("imaging source is missing")

    candidates: list[tuple[AudioAnalysis, str]] = []
    for candidate in source_files:
        if candidate.is_symlink():
            raise ImagingImportError("imaging source symlinks are not allowed")
        try:
            analysis = analyze_audio(candidate, ffprobe_binary=ffprobe_binary)
        except AudioAnalysisError as error:
            if "unsupported" in str(error).lower():
                raise ImagingImportError("unsupported imaging source format") from error
            raise ImagingImportError("imaging source could not be analyzed") from error
        if analysis.validation_status is not AudioValidationStatus.VALID:
            raise ImagingImportError("imaging source is not valid")
        candidates.append((analysis, candidate.suffix))

    if not candidates:
        raise ImagingImportError("imaging source contains no files")
    return tuple(candidates)


def _copy_packaged_asset(source: Path, destination: Path, asset: ImagingAsset) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _checksum_sha256(destination) != asset.checksum_sha256:
            raise ImagingImportError("packaged asset checksum collision")
        return

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=".imaging-", suffix=".tmp", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        shutil.copyfile(source, temporary_path)
        if _checksum_sha256(temporary_path) != asset.checksum_sha256:
            raise ImagingImportError("copied imaging asset checksum mismatch")
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_manifest(
    manifest_path: Path, root: Path, station_id: str, language: str
) -> tuple[ImagingAsset, ...]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImagingManifestError("station imaging manifest is unreadable") from error
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "station_id",
        "assets",
    }:
        raise ImagingManifestError("station imaging manifest has unsafe fields")
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ImagingManifestError("station imaging manifest has an unsupported schema")
    if manifest["station_id"] != station_id:
        raise ImagingManifestError("station imaging manifest belongs to another station")
    raw_assets = manifest["assets"]
    if not isinstance(raw_assets, list):
        raise ImagingManifestError("station imaging manifest assets are invalid")

    assets = tuple(
        _manifest_asset(raw_asset, root, station_id, language) for raw_asset in raw_assets
    )
    checksums = [asset.checksum_sha256 for asset in assets]
    if len(checksums) != len(set(checksums)):
        raise ImagingManifestError("station imaging manifest duplicates an asset checksum")
    return assets


def _manifest_asset(
    raw_asset: object, root: Path, station_id: str, language: str
) -> ImagingAsset:
    expected_fields = {
        "station_id",
        "language",
        "category",
        "duration_seconds",
        "checksum_sha256",
        "relative_path",
    }
    if not isinstance(raw_asset, dict) or set(raw_asset) != expected_fields:
        raise ImagingManifestError("station imaging manifest asset has unsafe fields")
    checksum = raw_asset["checksum_sha256"]
    relative_path = _safe_relative_path(raw_asset["relative_path"])
    duration_seconds = raw_asset["duration_seconds"]
    if (
        raw_asset["station_id"] != station_id
        or raw_asset["language"] != language
        or raw_asset["category"] not in SUPPORTED_CATEGORIES
        or not isinstance(checksum, str)
        or _CHECKSUM_PATTERN.fullmatch(checksum) is None
        or isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise ImagingManifestError("station imaging manifest asset is invalid")

    asset_path = (root / Path(relative_path)).resolve()
    asset_root = (root / ASSET_DIRECTORY).resolve()
    if asset_root not in asset_path.parents or not asset_path.is_file():
        raise ImagingManifestError("station imaging packaged asset is missing")
    if _checksum_sha256(asset_path) != checksum:
        raise ImagingManifestError("station imaging packaged asset checksum mismatch")
    return ImagingAsset(
        station_id=station_id,
        language=language,
        category=raw_asset["category"],
        duration_seconds=float(duration_seconds),
        checksum_sha256=checksum,
        relative_path=relative_path,
    )


def _safe_relative_path(raw_path: object) -> PurePosixPath:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path or ":" in raw_path:
        raise ImagingManifestError("unsafe asset path")
    relative_path = PurePosixPath(raw_path)
    if (
        relative_path.is_absolute()
        or relative_path.as_posix() != raw_path
        or len(relative_path.parts) != 2
        or relative_path.parts[0] != ASSET_DIRECTORY
        or relative_path.parts[1] in {"", ".", ".."}
    ):
        raise ImagingManifestError("unsafe asset path")
    return relative_path


def _write_manifest(
    manifest_path: Path, station_id: str, assets: Iterable[ImagingAsset]
) -> None:
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "station_id": station_id,
        "assets": [
            {
                "station_id": asset.station_id,
                "language": asset.language,
                "category": asset.category,
                "duration_seconds": asset.duration_seconds,
                "checksum_sha256": asset.checksum_sha256,
                "relative_path": asset.relative_path.as_posix(),
            }
            for asset in sorted(assets, key=lambda asset: asset.checksum_sha256)
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=".manifest-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(payload, temporary_file, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, manifest_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _checksum_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
