from __future__ import annotations

import argparse
import json
import time

from backend.config import Settings
from backend.public_dashboard import PublicSnapshotPusher
from backend.radio_agent import RadioAgent


SYNC_TOKEN_HEADER = "X-RadioTEDU-Sync-Token"


def main() -> int:
    parser = argparse.ArgumentParser(description="manual/debug tool for pushing sanitized RadioTEDU public snapshots to the website server.")
    parser.add_argument("--once", action="store_true", help="Push one snapshot and exit.")
    parser.add_argument("--interval", type=int, default=0, help="Override PUBLIC_SYNC_INTERVAL_SECONDS.")
    parser.epilog = f"Requires PUBLIC_SYNC_URL, PUBLIC_SYNC_TOKEN, and sends {SYNC_TOKEN_HEADER}."
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.interval > 0:
        settings.public_sync_interval_seconds = args.interval
    pusher = PublicSnapshotPusher(settings, RadioAgent(settings))

    while True:
        result = pusher.maybe_push()
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if args.once:
            return 0 if result.get("pushed") or result.get("reason") == "waiting" else 1
        time.sleep(max(5, int(settings.public_sync_interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
