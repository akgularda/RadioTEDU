from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from scripts.qualify_qwen_voice_pack import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[2]

PACKS = (
    (
        "radiotedu-en-voices-v1.json",
        ("maya", "elliot", "selin", "theo"),
        {"maya": "morning", "selin": "night"},
    ),
    (
        "radiotedu-fr-voices-v1.json",
        ("camille", "mathieu", "elodie", "jules"),
        {"camille": "morning", "elodie": "night"},
    ),
)


def _pack(filename: str) -> dict:
    return load_manifest(ROOT / "config" / "voices" / filename)


def test_commissioning_manifests_keep_fixed_bilingual_casts_and_women_dayparts() -> None:
    for filename, host_ids, women_dayparts in PACKS:
        pack = _pack(filename)

        assert tuple(host["host_id"] for host in pack["hosts"]) == host_ids
        assert len(pack["hosts"]) == 4
        assert {
            host["host_id"]: host["dayparts"][0]
            for host in pack["hosts"]
            if host["gender"] == "woman"
        } == women_dayparts
        assert all(host["styles"] for host in pack["hosts"])
        assert validate_manifest(pack) == []


def test_voice_qualification_blocks_generation_without_approved_local_qwen_references() -> None:
    for filename, _, _ in PACKS:
        pack = _pack(filename)
        qualification = pack["voice_qualification"]

        assert qualification["state"] == "blocked_missing_approved_local_qwen_references"
        assert qualification["generation_permitted"] is False
        assert qualification["approved_local_references"] == []
        assert qualification["candidate_model_checksum"].endswith("0" * 64)


def test_jingle_only_imaging_evidence_marks_promos_missing_and_not_queued_by_t15() -> None:
    for filename, _, _ in PACKS:
        pack = _pack(filename)
        imaging = pack["imaging_qualification"]

        assert imaging["state"] == "blocked_missing_promo_assets"
        assert imaging["available_categories"] == ["jingle"]
        assert imaging["missing_categories"] == ["promo"]
        assert imaging["commissioning_queue"] == {
            "state": "not_authorized_by_t15",
            "next_work_order": None,
        }
        assert imaging["approved_references"]
        assert all(reference["category"] == "jingle" for reference in imaging["approved_references"])


def test_commissioning_status_command_reports_evidence_without_generating_audio() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "commission_qwen_voices.py"),
            "status",
            "--pack",
            "config/voices/radiotedu-en-voices-v1.json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"audio_generation_attempted": false' in result.stdout
    assert '"external_assets_requested": false' in result.stdout
