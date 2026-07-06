from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple


class ProcessSpec(NamedTuple):
    name: str
    args: list[str]
    cwd: Path
    stdout_path: Path
    stderr_path: Path


def build_process_specs(root: Path, start_frontend: bool = False) -> list[ProcessSpec]:
    logs = root / "logs"
    npm = "npm.cmd" if os.name == "nt" else "npm"
    specs = [
        ProcessSpec(
            name="backend",
            args=["python", "-m", "backend.app"],
            cwd=root,
            stdout_path=logs / "backend-forever.out.log",
            stderr_path=logs / "backend-forever.err.log",
        )
    ]
    if start_frontend:
        specs.append(
            ProcessSpec(
                name="frontend",
                args=[npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
                cwd=root,
                stdout_path=logs / "frontend-forever.out.log",
                stderr_path=logs / "frontend-forever.err.log",
            )
        )
    return specs


def backend_is_healthy(url: str, timeout_seconds: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def backend_health_due(started_at: float, now: float, grace_seconds: int) -> bool:
    return now - started_at >= grace_seconds


def supervise(root: Path, start_frontend: bool, health_url: str, interval_seconds: int, restart_delay_seconds: int) -> None:
    specs = build_process_specs(root, start_frontend=start_frontend)
    processes: dict[str, subprocess.Popen] = {}
    started_at: dict[str, float] = {}
    for spec in specs:
        spec.stdout_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        for spec in specs:
            process = processes.get(spec.name)
            if process is None or process.poll() is not None:
                if process is not None:
                    time.sleep(restart_delay_seconds)
                stdout = spec.stdout_path.open("ab")
                stderr = spec.stderr_path.open("ab")
                processes[spec.name] = subprocess.Popen(spec.args, cwd=spec.cwd, stdout=stdout, stderr=stderr)
                started_at[spec.name] = time.time()

        backend = processes.get("backend")
        backend_started_at = started_at.get("backend", 0.0)
        if (
            backend
            and backend.poll() is None
            and backend_health_due(backend_started_at, time.time(), max(interval_seconds, 15))
            and not backend_is_healthy(health_url)
        ):
            backend.terminate()
            try:
                backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend.kill()
            processes.pop("backend", None)
            time.sleep(restart_delay_seconds)

        time.sleep(interval_seconds)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keep RadioTEDU running locally.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--health-url", default="http://127.0.0.1:8000/api/status")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--restart-delay-seconds", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    supervise(
        root=Path(args.root).resolve(),
        start_frontend=bool(args.frontend),
        health_url=args.health_url,
        interval_seconds=args.interval_seconds,
        restart_delay_seconds=args.restart_delay_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
