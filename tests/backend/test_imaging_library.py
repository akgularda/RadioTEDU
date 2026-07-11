from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from backend.imaging.library import (
    ImagingImportError,
    ImagingLibrary,
    ImagingManifestError,
    import_imaging,
)


def _write_wave(path: Path) -> bytes:
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(8_000)
        audio_file.writeframes(b"\x00\x00" * 800)
    return path.read_bytes()


def test_import_curates_deduplicated_assets_and_runtime_reads_only_packaged_paths(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "Downloads" / "jingle" / "generated_jingles"
    source_root.mkdir(parents=True)
    first_source = source_root / "station-id.wav"
    source_bytes = _write_wave(first_source)
    (source_root / "station-id-copy.wav").write_bytes(source_bytes)
    release_root = tmp_path / "release"

    first_import = import_imaging(
        source_root, release_root, station_id="radiotedu-en", category="jingle"
    )
    library = ImagingLibrary.open(release_root, "radiotedu-en")

    assert first_import.imported_count == 1
    assert first_import.deduplicated_count == 1
    assert len(library.assets) == 1
    assert library.assets[0].station_id == "radiotedu-en"
    assert library.assets[0].language == "en"
    assert library.assets[0].relative_path.parts[0] == "assets"
    assert len(library.asset_paths()) == 1
    assert library.asset_paths()[0].read_bytes() == source_bytes
    assert release_root in library.asset_paths()[0].parents
    assert source_root not in library.asset_paths()[0].parents

    manifest_path = release_root / "media" / "imaging" / "radiotedu-en" / "manifest.json"
    manifest_before_repeat = manifest_path.read_text(encoding="utf-8")
    repeated_import = import_imaging(
        source_root, release_root, station_id="radiotedu-en", category="jingle"
    )

    assert repeated_import.imported_count == 0
    assert repeated_import.deduplicated_count == 2
    assert manifest_path.read_text(encoding="utf-8") == manifest_before_repeat
    assert str(source_root) not in manifest_before_repeat


def test_same_content_is_packaged_separately_for_each_station(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    _write_wave(source_root / "shared.wav")
    release_root = tmp_path / "release"

    import_imaging(source_root, release_root, station_id="radiotedu-en", category="jingle")
    import_imaging(source_root, release_root, station_id="radiotedu-fr", category="jingle")

    en_path = ImagingLibrary.open(release_root, "radiotedu-en").asset_paths()[0]
    fr_path = ImagingLibrary.open(release_root, "radiotedu-fr").asset_paths()[0]

    assert "radiotedu-en" in en_path.parts
    assert "radiotedu-fr" not in en_path.parts
    assert "radiotedu-fr" in fr_path.parts
    assert "radiotedu-en" not in fr_path.parts
    assert en_path != fr_path


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("notes.txt", b"not audio", "unsupported"),
        ("broken.wav", b"not a wave file", "could not be analyzed"),
    ],
)
def test_import_rejects_unsupported_or_malformed_assets_without_packaging(
    tmp_path: Path, filename: str, contents: bytes, message: str
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / filename).write_bytes(contents)
    release_root = tmp_path / "release"

    with pytest.raises(ImagingImportError, match=message):
        import_imaging(source_root, release_root, station_id="radiotedu-en", category="jingle")

    assert not (release_root / "media" / "imaging" / "radiotedu-en").exists()


def test_open_rejects_unsafe_manifest_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    _write_wave(source_root / "safe.wav")
    release_root = tmp_path / "release"
    import_imaging(source_root, release_root, station_id="radiotedu-en", category="jingle")
    manifest_path = release_root / "media" / "imaging" / "radiotedu-en" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"][0]["relative_path"] = "../radiotedu-fr/assets/escape.wav"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ImagingManifestError, match="unsafe asset path"):
        ImagingLibrary.open(release_root, "radiotedu-en")
