from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def check_icecast(url: str, timeout: float = 5.0) -> dict:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "RadioTEDU-Icecast-Check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "reachable": True,
                "mount_active": response.status in {200, 206},
                "status": response.status,
                "url": url,
            }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": True,
            "mount_active": False,
            "status": exc.code,
            "url": url,
            "error": str(exc),
        }
    except OSError as exc:
        return {
            "reachable": False,
            "mount_active": False,
            "status": None,
            "url": url,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether an Icecast mount is reachable.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mount", default="/ai")
    parser.add_argument("--url", default="")
    args = parser.parse_args()

    mount = args.mount if args.mount.startswith("/") else f"/{args.mount}"
    url = args.url or f"http://{args.host}:{args.port}{mount}"
    result = check_icecast(url)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["reachable"] and result["mount_active"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
