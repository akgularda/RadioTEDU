from __future__ import annotations

from pathlib import Path

from .config import Settings


def render_liquidsoap_config(settings: Settings) -> dict:
    queue_path = Path(settings.liquidsoap_queue_path)
    script_path = Path(settings.liquidsoap_script_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if not queue_path.exists():
        queue_path.write_text("", encoding="utf-8")
    script = f"""# RadioTEDU Liquidsoap configuration
set("log.stdout", true)
set("server.telnet", false)

radio = playlist(id="RadioTEDU", mode="normal", reload=1, "{queue_path.as_posix()}")
radio = mksafe(radio)

output.icecast(
  %mp3,
  host="{settings.liquidsoap_host}",
  port={settings.liquidsoap_port},
  password="hackme",
  mount="radiotedu.mp3",
  name="RadioTEDU",
  radio
)
"""
    script_path.write_text(script, encoding="utf-8")
    return {"queue_path": str(queue_path), "script_path": str(script_path)}


def append_liquidsoap_item(settings: Settings, file_path: str) -> None:
    queue_path = Path(settings.liquidsoap_queue_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as handle:
        handle.write(str(Path(file_path).resolve()) + "\n")
