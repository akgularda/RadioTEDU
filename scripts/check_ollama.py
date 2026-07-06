from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import Settings
from backend.ollama_setup import check_ollama_setup


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "RadioTEDU Ollama check",
        f"Status: {result['status']}",
        f"Model: {result['configured_model']}",
        f"Server: {result['base_url']}",
        f"CLI: {result.get('cli_path') or 'not found'}",
        f"Reachable: {'yes' if result['server_reachable'] else 'no'}",
        f"Model available: {'yes' if result['model_available'] else 'no'}",
        f"Summary: {result['summary']}",
    ]
    installed = result.get("installed_models") or []
    if installed:
        lines.append("Installed models: " + ", ".join(installed))
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    commands = result.get("suggested_commands") or []
    if commands:
        lines.append("Suggested commands:")
        lines.extend(f"  {command}" for command in commands)
    return "\n".join(lines)


def pull_configured_model(model: str) -> int:
    return subprocess.run(["ollama", "pull", model], check=False).returncode


def install_ollama() -> int:
    return subprocess.run(
        [
            "winget",
            "install",
            "--id",
            "Ollama.Ollama",
            "--source",
            "winget",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent",
        ],
        check=False,
    ).returncode


def start_ollama_server() -> int:
    command = (
        "Start-Process -FilePath 'ollama' "
        "-ArgumentList @('serve') "
        "-WindowStyle Hidden"
    )
    return subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check RadioTEDU's configured Ollama runtime.")
    parser.add_argument("--env", default=".env", help="Path to the environment file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--install", action="store_true", help="Explicitly install Ollama with winget.")
    parser.add_argument("--start", action="store_true", help="Explicitly start `ollama serve` in the background.")
    parser.add_argument("--pull", action="store_true", help="Explicitly run `ollama pull` for the configured model.")
    args = parser.parse_args(argv)

    settings = Settings.from_env(args.env)
    result = check_ollama_setup(settings)

    if args.install and not result["cli_found"]:
        result["install_attempted"] = True
        result["install_returncode"] = install_ollama()
        result = {**check_ollama_setup(settings), **{k: result[k] for k in ("install_attempted", "install_returncode")}}
    else:
        result["install_attempted"] = False

    if args.start and not result["server_reachable"] and result["cli_found"]:
        result["start_attempted"] = True
        result["start_returncode"] = start_ollama_server()
        time.sleep(3)
        result = {**check_ollama_setup(settings), **{k: result[k] for k in ("install_attempted", "start_attempted", "start_returncode") if k in result}}
    else:
        result["start_attempted"] = False

    if args.pull:
        result["pull_attempted"] = True
        if not result["cli_found"]:
            result["pull_returncode"] = None
            result["pull_error"] = "Cannot pull because the Ollama CLI was not found."
        else:
            result["pull_returncode"] = pull_configured_model(settings.ollama_model)
            result = {**check_ollama_setup(settings), **{k: result[k] for k in ("pull_attempted", "pull_returncode")}}
    else:
        result["pull_attempted"] = False

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_report(result))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
