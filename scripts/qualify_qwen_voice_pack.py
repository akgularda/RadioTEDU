from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STYLE_KEYS = {
    "station_id",
    "track_intro",
    "track_outro",
    "weather",
    "news",
    "listener_reply",
    "program_open",
    "program_close",
}

EXPECTED_PACKS = {
    "radiotedu-en": {
        "language": "en",
        "hosts": ("maya", "elliot", "selin", "theo"),
        "women_dayparts": {"maya": "morning", "selin": "night"},
    },
    "radiotedu-fr": {
        "language": "fr",
        "hosts": ("camille", "mathieu", "elodie", "jules"),
        "women_dayparts": {"camille": "morning", "elodie": "night"},
    },
}


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    station_id = pack.get("station_id")
    expected = EXPECTED_PACKS.get(station_id)
    if expected is None:
        return ["station_id must be a RadioTEDU bilingual station"]

    if pack.get("language") != expected["language"]:
        errors.append("language must match the station")
    if pack.get("pack_id") != f"{station_id}-voices-v1":
        errors.append("pack_id must match the station")
    if pack.get("commissioning_state") != "blocked":
        errors.append("commissioning_state must remain blocked without approved local Qwen references")

    hosts = pack.get("hosts")
    if not isinstance(hosts, list):
        return errors + ["hosts must be a list"]
    if tuple(host.get("host_id") for host in hosts) != expected["hosts"]:
        errors.append("hosts must be the fixed four-host station cast")
    if len(hosts) != 4:
        errors.append("exactly four hosts are required")

    women_dayparts: dict[str, str] = {}
    for host in hosts:
        host_id = host.get("host_id")
        dayparts = host.get("dayparts")
        styles = host.get("styles")
        if not isinstance(dayparts, list) or len(dayparts) != 1:
            errors.append(f"{host_id}: exactly one daypart is required")
        if not isinstance(styles, dict) or set(styles) != REQUIRED_STYLE_KEYS:
            errors.append(f"{host_id}: required broadcast styles are missing")
        if host.get("approved") is not False:
            errors.append(f"{host_id}: no host can be approved before local Qwen reference review")
        if host.get("gender") == "woman" and isinstance(dayparts, list) and dayparts:
            women_dayparts[host_id] = dayparts[0]
    if women_dayparts != expected["women_dayparts"]:
        errors.append("morning and night women host assignments must remain fixed")

    voice = pack.get("voice_qualification")
    if not isinstance(voice, dict):
        return errors + ["voice_qualification is required"]
    if voice.get("state") != "blocked_missing_approved_local_qwen_references":
        errors.append("voice qualification must record the missing approved local references")
    if voice.get("generation_permitted") is not False:
        errors.append("voice generation must be disabled without approved local Qwen references")
    if voice.get("approved_local_references") != []:
        errors.append("approved_local_references must be empty until operator approval")
    checksum = voice.get("candidate_model_checksum")
    if not isinstance(checksum, str) or not checksum.startswith("sha256:"):
        errors.append("candidate model checksum must be recorded")

    imaging = pack.get("imaging_qualification")
    if not isinstance(imaging, dict):
        return errors + ["imaging_qualification is required"]
    if imaging.get("state") != "blocked_missing_promo_assets":
        errors.append("imaging qualification must record missing promos")
    if imaging.get("available_categories") != ["jingle"]:
        errors.append("only packaged jingles may be claimed as available imaging")
    if imaging.get("missing_categories") != ["promo"]:
        errors.append("promo must remain explicitly missing")
    if imaging.get("commissioning_queue") != {
        "state": "not_authorized_by_t15",
        "next_work_order": None,
    }:
        errors.append("T15 must not queue or create promo audio")
    references = imaging.get("approved_references")
    if not isinstance(references, list) or not references:
        errors.append("packaged jingle references are required")
    elif any(reference.get("category") != "jingle" for reference in references):
        errors.append("non-jingle imaging references are not approved by T15")

    return errors


def qualification_errors(pack: dict[str, Any]) -> list[str]:
    errors = validate_manifest(pack)
    if pack.get("voice_qualification", {}).get("state") != "qualified":
        errors.append("voice qualification is blocked pending approved local Qwen references")
    if pack.get("imaging_qualification", {}).get("state") != "qualified":
        errors.append("imaging qualification is blocked pending promo assets")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate RadioTEDU T15 qualification evidence.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--qualification-gate",
        action="store_true",
        help="Fail when valid evidence is not yet fully qualified.",
    )
    args = parser.parse_args()

    pack = load_manifest(args.manifest)
    errors = qualification_errors(pack) if args.qualification_gate else validate_manifest(pack)
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2, ensure_ascii=False))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
