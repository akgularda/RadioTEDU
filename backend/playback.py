from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .liquidsoap import append_liquidsoap_item, render_liquidsoap_config


@dataclass
class QueueItem:
    item_type: str
    title: str
    file_path: str
    duration_seconds: float | None = None
    artist: str | None = None
    track_id: int | None = None


class PlaybackController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.queue: list[QueueItem] = []
        self.now_playing: QueueItem | None = None
        self.running = False
        self.backend = self._backend()

    def _backend(self) -> str:
        requested = self.settings.playback_backend.lower()
        if requested == "mpv" and shutil.which(self.settings.mpv_path):
            return "mpv"
        if requested == "ffplay" and shutil.which(self.settings.ffplay_path):
            return "ffplay"
        if requested == "auto":
            if shutil.which(self.settings.mpv_path):
                return "mpv"
            if shutil.which(self.settings.ffplay_path):
                return "ffplay"
        if requested == "liquidsoap":
            render_liquidsoap_config(self.settings)
            return "liquidsoap"
        return "simulate"

    def add(self, item: QueueItem) -> None:
        self.queue.append(item)

    def skip(self) -> None:
        self.now_playing = None

    def play_next(self) -> QueueItem | None:
        if not self.queue:
            self.now_playing = None
            return None
        item = self.queue.pop(0)
        self.now_playing = item
        self.running = True
        if self.backend == "simulate":
            time.sleep(min(float(item.duration_seconds or 1), 1.0))
        elif self.backend == "mpv":
            subprocess.Popen([self.settings.mpv_path, "--really-quiet", item.file_path]).wait()
        elif self.backend == "ffplay":
            subprocess.Popen([self.settings.ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet", item.file_path]).wait()
        elif self.backend == "liquidsoap":
            append_liquidsoap_item(self.settings, item.file_path)
        return item

    def state(self) -> dict:
        if self.now_playing:
            current = self.now_playing
            return {
                "type": current.item_type,
                "title": current.title,
                "artist": current.artist,
                "file_path": current.file_path,
                "started_at": None,
            }
        return {
            "type": "idle",
            "title": "Idle — waiting for music library.",
            "artist": None,
            "started_at": None,
        }

    def health(self) -> str:
        return self.backend
