from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

from .config import Settings
from .llm import ollama_runtime_status


def check_ollama_setup(
    settings: Settings,
    *,
    which: Callable[[str], str | None] = shutil.which,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = settings.llm_provider.lower()
    base_url = settings.ollama_url.rstrip("/")
    model = settings.ollama_model
    cli_path = which("ollama")
    cli_found = bool(cli_path)
    runtime = runtime or ollama_runtime_status(settings, fetch_json=fetch_json)

    suggested_commands: list[str] = []
    if provider != "ollama":
        return {
            "provider": settings.llm_provider,
            "configured_model": model,
            "base_url": base_url,
            "cli_found": cli_found,
            "cli_path": cli_path,
            "server_reachable": False,
            "reachable": False,
            "model_available": False,
            "installed_models": [],
            "status": "disabled",
            "summary": f"LLM provider is {settings.llm_provider}; Ollama setup check is disabled.",
            "suggested_commands": suggested_commands,
            "error": None,
            "runtime": runtime,
        }

    server_reachable = bool(runtime["reachable"])
    model_available = bool(runtime["model_available"])
    installed_models = list(runtime["installed_models"])

    if not cli_found:
        suggested_commands.append("winget install Ollama.Ollama")
    if not server_reachable:
        suggested_commands.append("ollama serve")
    if not model_available:
        suggested_commands.append(f"ollama pull {model}")

    if server_reachable and model_available:
        status = "ready"
        summary = f"Ollama is reachable and {model} is available for RadioTEDU."
    elif not cli_found:
        status = "cli_missing"
        summary = f"Ollama CLI was not found. Install Ollama, start the server, then pull {model}."
    elif not server_reachable:
        status = "server_unreachable"
        summary = f"Ollama server is not reachable at {base_url}."
    else:
        status = "model_missing"
        summary = f"Ollama is reachable, but {model} is not available."

    return {
        "provider": "ollama",
        "configured_model": model,
        "base_url": base_url,
        "cli_found": cli_found,
        "cli_path": cli_path,
        "server_reachable": server_reachable,
        "reachable": server_reachable,
        "model_available": model_available,
        "installed_models": installed_models,
        "status": status,
        "summary": summary,
        "suggested_commands": suggested_commands,
        "error": runtime["error"],
        "runtime": runtime,
    }
