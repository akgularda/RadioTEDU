"""Explicitly curate supplied radio imaging into release-relative assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.imaging.library import (  # noqa: E402
    SUPPORTED_CATEGORIES,
    STATION_LANGUAGES,
    ImagingError,
    import_imaging,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and package station imaging from an explicit source path."
    )
    parser.add_argument("source", type=Path, help="source file or directory to curate")
    parser.add_argument("release_root", type=Path, help="root of the release artifact")
    parser.add_argument("--station", choices=sorted(STATION_LANGUAGES), required=True)
    parser.add_argument("--category", choices=sorted(SUPPORTED_CATEGORIES), required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        result = import_imaging(
            arguments.source,
            arguments.release_root,
            station_id=arguments.station,
            category=arguments.category,
        )
    except ImagingError as error:
        print(f"imaging import rejected: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "station_id": result.library.station_id,
                "asset_count": len(result.library.assets),
                "imported_count": result.imported_count,
                "deduplicated_count": result.deduplicated_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
