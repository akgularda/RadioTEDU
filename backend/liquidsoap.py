from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

from .config import Settings


def liquidsoap_pid_path(settings: Settings) -> Path:
    return Path(settings.liquidsoap_script_path).with_suffix(".pid")


def render_liquidsoap_config(settings: Settings) -> dict:
    queue_path = Path(settings.liquidsoap_queue_path)
    script_path = Path(settings.liquidsoap_script_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if not queue_path.exists():
        queue_path.write_text("", encoding="utf-8")
    mount = settings.liquidsoap_mount if settings.liquidsoap_mount.startswith("/") else f"/{settings.liquidsoap_mount}"
    script = f"""# RadioTEDU Liquidsoap configuration
set("log.stdout", true)
set("server.telnet", false)

radio = playlist(id="RadioTEDU", mode="normal", reload=1, reload_mode="watch", "{queue_path.as_posix()}")
radio = mksafe(radio)

output.icecast(
  %mp3,
  host="{settings.liquidsoap_host}",
  port={settings.liquidsoap_port},
  password="{settings.liquidsoap_icecast_password}",
  mount="{mount}",
  name="RadioTEDU",
  description="RadioTEDU AI radio",
  genre="AI Radio",
  radio
)
"""
    script_path.write_text(script, encoding="utf-8")
    return {
        "queue_path": str(queue_path),
        "script_path": str(script_path),
        "mount": mount,
        "icecast_url": f"http://{settings.liquidsoap_host}:{settings.liquidsoap_port}{mount}",
    }


def liquidsoap_status(settings: Settings) -> dict:
    pid_path = liquidsoap_pid_path(settings)
    command_path = shutil.which(settings.liquidsoap_command)
    pid = _read_pid(pid_path)
    running = _pid_running(pid) if pid else False
    if pid and not running:
        pid_path.unlink(missing_ok=True)
    rendered = Path(settings.liquidsoap_script_path).exists()
    queue_path = Path(settings.liquidsoap_queue_path)
    queue_exists = queue_path.exists()
    queue_length = _queue_length(queue_path) if queue_exists else 0
    if not settings.liquidsoap_enabled:
        health = "disabled"
    elif running:
        health = "running"
    elif command_path:
        health = "ready"
    else:
        health = "missing"
    return {
        "enabled": settings.liquidsoap_enabled,
        "health": health,
        "command": settings.liquidsoap_command,
        "command_found": bool(command_path),
        "command_path": command_path,
        "running": running,
        "pid": pid if running else None,
        "rendered": rendered,
        "script_path": settings.liquidsoap_script_path,
        "queue_path": settings.liquidsoap_queue_path,
        "queue_exists": queue_exists,
        "queue_length": queue_length,
        "mount": settings.liquidsoap_mount if settings.liquidsoap_mount.startswith("/") else f"/{settings.liquidsoap_mount}",
        "icecast_url": f"http://{settings.liquidsoap_host}:{settings.liquidsoap_port}{settings.liquidsoap_mount if settings.liquidsoap_mount.startswith('/') else '/' + settings.liquidsoap_mount}",
    }


def start_liquidsoap(settings: Settings) -> dict:
    rendered = render_liquidsoap_config(settings)
    status = liquidsoap_status(settings)
    if status["running"]:
        return {"started": True, "already_running": True, **status}
    command_path = status["command_path"]
    if not command_path:
        return {"started": False, "reason": "liquidsoap_missing", **status, **rendered}
    script_path = str(Path(settings.liquidsoap_script_path).resolve())
    out_path = Path(settings.liquidsoap_script_path).with_suffix(".out.log")
    err_path = Path(settings.liquidsoap_script_path).with_suffix(".err.log")
    with out_path.open("a", encoding="utf-8") as stdout, err_path.open("a", encoding="utf-8") as stderr:
        process = subprocess.Popen([command_path, script_path], stdout=stdout, stderr=stderr)
    liquidsoap_pid_path(settings).write_text(str(process.pid), encoding="utf-8")
    return {"started": True, "already_running": False, **liquidsoap_status(settings), **rendered}


def stop_liquidsoap(settings: Settings) -> dict:
    pid_path = liquidsoap_pid_path(settings)
    pid = _read_pid(pid_path)
    if not pid or not _pid_running(pid):
        pid_path.unlink(missing_ok=True)
        return {"stopped": True, "already_stopped": True, **liquidsoap_status(settings)}
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    pid_path.unlink(missing_ok=True)
    return {"stopped": True, "already_stopped": False, **liquidsoap_status(settings)}


def append_liquidsoap_item(settings: Settings, file_path: str) -> None:
    queue_path = Path(settings.liquidsoap_queue_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as handle:
        handle.write(str(Path(file_path).resolve()) + "\n")


def _queue_length(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
