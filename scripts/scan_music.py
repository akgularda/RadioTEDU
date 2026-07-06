from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import Settings
from backend.music_library import scan_music


def main() -> None:
    settings = Settings.from_env()
    result = scan_music(settings)
    print(f"Music scan complete: {result.tracks_found} tracks found in {result.music_dir}.")


if __name__ == "__main__":
    main()
