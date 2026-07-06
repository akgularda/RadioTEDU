from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RadioTEDU Qwen TTS command wrapper.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--out", "--output_path", dest="output_path", required=True)
    parser.add_argument("--voice", default="")
    return parser.parse_args(argv)


def synthesize_via_http(text: str, output_path: Path, voice: str, url: str) -> None:
    payload = json.dumps({"text": text, "voice": voice, "output_format": "wav"}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if not data.startswith(b"RIFF"):
        raise RuntimeError("Qwen TTS endpoint did not return WAV bytes")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = Path(args.output_path)
    endpoint = os.environ.get("QWEN_TTS_HTTP_URL", "").strip()
    if not endpoint:
        print("QWEN_TTS_HTTP_URL is not configured; falling back to local provider.", file=sys.stderr)
        return 2
    try:
        synthesize_via_http(args.text, output_path, args.voice, endpoint)
    except Exception as exc:
        print(f"Qwen TTS failed: {exc}", file=sys.stderr)
        return 1
    output_path.with_suffix(".txt").write_text(args.text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
