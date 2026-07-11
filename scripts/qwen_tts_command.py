"""Submit one trusted, policy-selected request to the local Qwen service."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import Settings
from backend.stations.context import coerce_station_context
from backend.tts.contracts import SynthesisRequest
from backend.tts.factory import build_tts_provider
from backend.tts.voice_policy import VoicePolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one Qwen-only RadioTEDU WAV clip.")
    parser.add_argument("text")
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--program-id", default="manual")
    parser.add_argument("--daypart", choices=("morning", "daytime", "night", "weekend"), default="daytime")
    parser.add_argument(
        "--announcement-label",
        choices=(
            "station_id", "track_intro", "track_outro", "weather", "news",
            "listener_reply", "program_open", "program_close",
        ),
        default="station_id",
    )
    parser.add_argument("--voice-config-root", type=Path, default=Path("config/voices"))
    parser.add_argument("--service-url", default=os.environ.get("QWEN_TTS_SERVICE_URL", "http://127.0.0.1:8090"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    context = coerce_station_context(Settings.from_env())
    normalized, voice = VoicePolicy.from_context(context, args.voice_config_root).select(
        program_id=args.program_id,
        daypart=args.daypart,
        announcement_label=args.announcement_label,
        text=args.text,
    )
    request = SynthesisRequest(
        request_id=str(uuid4()),
        station_id=context.profile.station_id,
        language=context.profile.language,
        locale=context.profile.locale,
        normalized_text=normalized,
        announcement_label=args.announcement_label,
        voice=voice,
    )
    result = build_tts_provider(context, args.service_url).synthesize_request(request, str(args.output_path))
    print(result.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
