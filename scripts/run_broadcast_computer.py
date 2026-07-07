from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

from backend.app import create_app
from backend.config import Settings, ensure_runtime_dirs
from backend.database import init_db
from backend.liquidsoap import liquidsoap_status, render_liquidsoap_config
from backend.music_library import scan_music
from backend.ollama_setup import check_ollama_setup
from backend.public_dashboard import PublicSnapshotPusher


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local RadioTEDU broadcast computer stack.")
    parser.add_argument("--check-only", action="store_true", help="Run readiness checks and exit.")
    parser.add_argument("--scan", action="store_true", help="Scan MUSIC_DIR before starting.")
    parser.add_argument("--json", action="store_true", help="Print readiness as JSON.")
    args = parser.parse_args()

    settings = Settings.from_env()
    ensure_runtime_dirs(settings)
    init_db(settings)
    readiness = broadcast_readiness(settings, scan=args.scan)
    if args.json:
        print(json.dumps(readiness, indent=2, ensure_ascii=True))
    else:
        print_readiness(readiness)
    if args.check_only:
        return 0 if readiness["can_start_backend"] else 1
    app = create_app(settings)
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, reload=False)
    return 0


def broadcast_readiness(settings: Settings, scan: bool = False) -> dict:
    scan_result = scan_music(settings).__dict__ if scan else None
    ollama = check_ollama_setup(settings)
    liquidsoap = liquidsoap_status(settings)
    rendered_liquidsoap = render_liquidsoap_config(settings) if settings.liquidsoap_enabled else {"rendered": False, "reason": "disabled"}
    public_sync_configured = bool(settings.public_sync_url and settings.public_sync_token)
    pusher_contract = PublicSnapshotPusher(settings, agent=None).status()
    return {
        "can_start_backend": True,
        "music_dir": settings.music_dir,
        "scan": scan_result,
        "ollama": ollama,
        "liquidsoap": liquidsoap,
        "rendered_liquidsoap": rendered_liquidsoap,
        "public_sync": {
            "configured": public_sync_configured,
            "url": settings.public_sync_url,
            "stream_url": settings.public_stream_url,
            "pusher_contract": pusher_contract,
        },
        "api": {"host": settings.api_host, "port": settings.api_port},
    }


def print_readiness(readiness: dict) -> None:
    print("RadioTEDU broadcast computer")
    print(f"- API: {readiness['api']['host']}:{readiness['api']['port']}")
    print(f"- Music: {readiness['music_dir']}")
    print(f"- Ollama: {readiness['ollama'].get('status')}")
    print(f"- Liquidsoap: {readiness['liquidsoap'].get('health')}")
    print(f"- Public sync: {'configured' if readiness['public_sync']['configured'] else 'not configured'}")
    if readiness["scan"]:
        print(f"- Scan indexed: {readiness['scan'].get('tracks_indexed', 0)}")


if __name__ == "__main__":
    raise SystemExit(main())
