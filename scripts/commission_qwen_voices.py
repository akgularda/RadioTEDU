from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from scripts.qualify_qwen_voice_pack import (
        load_manifest,
        qualification_errors,
        validate_manifest,
    )
else:
    from qualify_qwen_voice_pack import (
        load_manifest,
        qualification_errors,
        validate_manifest,
    )


def evidence_status(pack: dict) -> dict:
    return {
        "station_id": pack.get("station_id"),
        "commissioning_state": pack.get("commissioning_state"),
        "voice_qualification": pack.get("voice_qualification"),
        "imaging_qualification": pack.get("imaging_qualification"),
        "validation_errors": validate_manifest(pack),
        "qualification_errors": qualification_errors(pack),
        "audio_generation_attempted": False,
        "external_assets_requested": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect T15 commissioning evidence without generating speech or sourcing assets."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "verify"):
        command = subcommands.add_parser(name)
        command.add_argument("--pack", required=True, type=Path)
    args = parser.parse_args()

    result = evidence_status(load_manifest(args.pack))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.command == "verify":
        raise SystemExit(0 if not result["validation_errors"] else 1)


if __name__ == "__main__":
    main()
