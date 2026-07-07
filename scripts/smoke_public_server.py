from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid


def request_json(base_url: str, path: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "RadioTEDU-Public-Smoke/1.0"}
    if token:
        headers["X-RadioTEDU-Sync-Token"] = token
    request = urllib.request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = response.read().decode("utf-8")
            parsed = json.loads(data) if data else {}
            return {"ok": True, "status": response.status, "json": parsed}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "error": text[:300]}
    except OSError as exc:
        return {"ok": False, "status": None, "error": str(exc)}


def request_text(base_url: str, path: str) -> dict:
    request = urllib.request.Request(base_url.rstrip("/") + path, headers={"User-Agent": "RadioTEDU-Public-Smoke/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            text = response.read(500).decode("utf-8", errors="replace")
            return {"ok": response.status < 500, "status": response.status, "text": text}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": exc.read().decode("utf-8", errors="replace")[:300]}
    except OSError as exc:
        return {"ok": False, "status": None, "error": str(exc)}


def minimal_snapshot() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-07-07T00:00:00+00:00",
        "expires_at": "2026-07-07T00:00:30+00:00",
        "channel": {"id": "radiotedu", "name": "RadioTEDU", "status": "idle"},
        "now_playing": None,
        "current_program": None,
        "current_minutes_left": None,
        "next_program": None,
        "next_programs": [],
        "programs": [],
        "top_songs": [],
        "top_genres": [],
        "content_breakdown": [],
        "activity": [],
        "metrics": {},
        "stream": {"url": "", "status": "unknown"},
    }


def run_smoke(base_url: str, token: str | None) -> dict:
    session_id = f"smoke-{uuid.uuid4()}"
    results = {
        "status": request_json(base_url, "/api/public/status"),
        "ai_route": request_text(base_url, "/ai"),
        "session_start": request_json(
            base_url,
            "/api/public/session/start",
            method="POST",
            payload={"session_id": session_id},
        ),
        "session_heartbeat": request_json(
            base_url,
            "/api/public/session/heartbeat",
            method="POST",
            payload={"session_id": session_id},
        ),
        "session_end": request_json(
            base_url,
            "/api/public/session/end",
            method="POST",
            payload={"session_id": session_id},
        ),
    }
    if token:
        results["snapshot"] = request_json(
            base_url,
            "/api/public/snapshot",
            method="POST",
            payload=minimal_snapshot(),
            token=token,
        )
        results["wrong token"] = request_json(
            base_url,
            "/api/public/snapshot",
            method="POST",
            payload=minimal_snapshot(),
            token="wrong-token",
        )
    status_json = results["status"].get("json") or {}
    results["expired_or_offline"] = {
        "ok": bool(status_json.get("online") is False or status_json.get("message")),
        "status": results["status"].get("status"),
        "online": status_json.get("online"),
        "message": status_json.get("message"),
    }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check the public RadioTEDU website server.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Public server base URL.")
    parser.add_argument("--token", default="", help="Snapshot sync token for POST /api/public/snapshot.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero for failed checks.")
    args = parser.parse_args()

    results = run_smoke(args.base_url, args.token or None)
    failed = [name for name, result in results.items() if not result.get("ok")]
    if args.json:
        print(json.dumps({"base_url": args.base_url, "results": results, "failed": failed}, indent=2, ensure_ascii=True))
    else:
        print(f"RadioTEDU public smoke: {args.base_url}")
        for name, result in results.items():
            state = "ok" if result.get("ok") else "fail"
            print(f"- {name}: {state} ({result.get('status')})")
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
