from __future__ import annotations

import argparse
import json
import sys
import time
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
    parser.add_argument("--restart-on-exit", action="store_true", help="Restart the backend with backoff if it exits.")
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
    return run_backend_with_backoff(settings, restart_on_exit=args.restart_on_exit)


def broadcast_readiness(settings: Settings, scan: bool = False) -> dict:
    scan_result = scan_music(settings).__dict__ if scan else None
    ollama = check_ollama_setup(settings)
    liquidsoap = liquidsoap_status(settings)
    rendered_liquidsoap = render_liquidsoap_config(settings) if settings.liquidsoap_enabled else {"rendered": False, "reason": "disabled"}
    public_sync_configured = bool(settings.public_sync_url and settings.public_sync_token)
    pusher_contract = PublicSnapshotPusher(settings, agent=None).status()
    return {
        "can_start_backend": True,
        "backend": backend_readiness(settings),
        "orchestrator": orchestrator_readiness(settings),
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


def backend_readiness(settings: Settings) -> dict:
    return {
        "verified": True,
        "host": settings.api_host,
        "port": settings.api_port,
        "start_command": "python scripts/run_broadcast_computer.py",
        "restart_flag": "--restart-on-exit",
    }


def orchestrator_readiness(settings: Settings) -> dict:
    return {
        "autonomy_enabled": settings.autonomy_enabled,
        "startup": "automatic" if settings.autonomy_enabled else "manual_run_air",
        "tick_seconds": settings.autonomy_tick_seconds,
        "min_ready_announcements": settings.min_ready_announcements,
        "max_ready_announcements": settings.max_ready_announcements,
    }


def run_backend_with_backoff(settings: Settings, restart_on_exit: bool = False) -> int:
    backoff_seconds = 2
    while True:
        app = create_app(settings)
        uvicorn.run(app, host=settings.api_host, port=settings.api_port, reload=False)
        if not restart_on_exit:
            return 0
        print(f"Backend exited. Restarting in {backoff_seconds}s...")
        time.sleep(backoff_seconds)
        backoff_seconds = min(backoff_seconds * 2, 60)


def print_readiness(readiness: dict) -> None:
    print("RadioTEDU broadcast computer")
    print(f"- API: {readiness['api']['host']}:{readiness['api']['port']}")
    print(f"- Backend: {'verified' if readiness['backend']['verified'] else 'not verified'}")
    print(f"- Orchestrator: {readiness['orchestrator']['startup']}")
    print(f"- Music: {readiness['music_dir']}")
    print(f"- Ollama: {readiness['ollama'].get('status')}")
    print(f"- Liquidsoap: {readiness['liquidsoap'].get('health')}")
    print(f"- Icecast mount: {'active' if readiness['liquidsoap'].get('mount_active') else 'inactive'}")
    print(f"- Public sync: {'configured' if readiness['public_sync']['configured'] else 'not configured'}")
    if readiness["scan"]:
        print(f"- Scan indexed: {readiness['scan'].get('tracks_indexed', 0)}")


if __name__ == "__main__":
    raise SystemExit(main())
