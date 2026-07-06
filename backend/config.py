from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path


def _env_file_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get(name: str, default: str, env_file: dict[str, str]) -> str:
    return os.environ.get(name, env_file.get(name, default))


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    database_path: str = "data/radiotedu.db"
    music_dir: str = "data/music"
    static_dir: str = "backend/static"
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:0.5b-instruct"
    ollama_timeout_seconds: int = 30
    tts_provider: str = "qwen"
    qwen_tts_command: str = ""
    piper_tts_command: str = ""
    fallback_tts_provider: str = "dummy"
    search_provider: str = "rss"
    searxng_url: str = "http://localhost:8080"
    rss_feeds_path: str = "data/rss_feeds.json"
    playback_backend: str = "simulate"
    mpv_path: str = "mpv"
    ffplay_path: str = "ffplay"
    web_search_interval_minutes: int = 30
    weather_enabled: bool = False
    weather_provider: str = "open_meteo"
    weather_location: str = "Ankara"
    weather_latitude: str = ""
    weather_longitude: str = ""
    weather_interval_minutes: int = 30
    song_repeat_hours: int = 6
    artist_repeat_minutes: int = 90
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_port: int = 5173
    autonomy_enabled: bool = False
    autonomy_tick_seconds: int = 30
    strategy_interval_minutes: int = 240
    min_ready_announcements: int = 0
    max_ready_announcements: int = 8
    liquidsoap_enabled: bool = False
    liquidsoap_queue_path: str = "data/liquidsoap/queue.m3u"
    liquidsoap_script_path: str = "data/liquidsoap/radiotedu.liq"
    liquidsoap_host: str = "127.0.0.1"
    liquidsoap_port: int = 8001
    public_dashboard_enabled: bool = False
    public_dashboard_route: str = "/ai"
    public_stream_url: str = ""
    public_sync_url: str = ""
    public_sync_token: str = ""
    public_sync_interval_seconds: int = 10
    snapshot_ttl_seconds: int = 30
    news_enabled: bool = False
    news_interval_minutes: int = 60

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "Settings":
        env_file = _env_file_values(Path(env_path))
        values: dict[str, object] = {}
        key_map = {
            "database_path": "DATABASE_PATH",
            "music_dir": "MUSIC_DIR",
            "static_dir": "STATIC_DIR",
            "llm_provider": "LLM_PROVIDER",
            "ollama_url": "OLLAMA_URL",
            "ollama_model": "OLLAMA_MODEL",
            "ollama_timeout_seconds": "OLLAMA_TIMEOUT_SECONDS",
            "tts_provider": "TTS_PROVIDER",
            "qwen_tts_command": "QWEN_TTS_COMMAND",
            "piper_tts_command": "PIPER_TTS_COMMAND",
            "fallback_tts_provider": "FALLBACK_TTS_PROVIDER",
            "search_provider": "SEARCH_PROVIDER",
            "searxng_url": "SEARXNG_URL",
            "rss_feeds_path": "RSS_FEEDS_PATH",
            "playback_backend": "PLAYBACK_BACKEND",
            "mpv_path": "MPV_PATH",
            "ffplay_path": "FFPLAY_PATH",
            "web_search_interval_minutes": "WEB_SEARCH_INTERVAL_MINUTES",
            "weather_enabled": "WEATHER_ENABLED",
            "weather_provider": "WEATHER_PROVIDER",
            "weather_location": "WEATHER_LOCATION",
            "weather_latitude": "WEATHER_LATITUDE",
            "weather_longitude": "WEATHER_LONGITUDE",
            "weather_interval_minutes": "WEATHER_INTERVAL_MINUTES",
            "song_repeat_hours": "SONG_REPEAT_HOURS",
            "artist_repeat_minutes": "ARTIST_REPEAT_MINUTES",
            "api_host": "API_HOST",
            "api_port": "API_PORT",
            "frontend_port": "FRONTEND_PORT",
            "autonomy_enabled": "AUTONOMY_ENABLED",
            "autonomy_tick_seconds": "AUTONOMY_TICK_SECONDS",
            "strategy_interval_minutes": "STRATEGY_INTERVAL_MINUTES",
            "min_ready_announcements": "MIN_READY_ANNOUNCEMENTS",
            "max_ready_announcements": "MAX_READY_ANNOUNCEMENTS",
            "liquidsoap_enabled": "LIQUIDSOAP_ENABLED",
            "liquidsoap_queue_path": "LIQUIDSOAP_QUEUE_PATH",
            "liquidsoap_script_path": "LIQUIDSOAP_SCRIPT_PATH",
            "liquidsoap_host": "LIQUIDSOAP_HOST",
            "liquidsoap_port": "LIQUIDSOAP_PORT",
            "public_dashboard_enabled": "PUBLIC_DASHBOARD_ENABLED",
            "public_dashboard_route": "PUBLIC_DASHBOARD_ROUTE",
            "public_stream_url": "PUBLIC_STREAM_URL",
            "public_sync_url": "PUBLIC_SYNC_URL",
            "public_sync_token": "PUBLIC_SYNC_TOKEN",
            "public_sync_interval_seconds": "PUBLIC_SYNC_INTERVAL_SECONDS",
            "snapshot_ttl_seconds": "SNAPSHOT_TTL_SECONDS",
            "news_enabled": "NEWS_ENABLED",
            "news_interval_minutes": "NEWS_INTERVAL_MINUTES",
        }
        for field in fields(cls):
            env_name = key_map[field.name]
            raw = _get(env_name, str(field.default), env_file)
            if field.type in (int, "int"):
                values[field.name] = int(raw)
            elif field.type in (bool, "bool"):
                values[field.name] = _as_bool(raw)
            else:
                values[field.name] = raw
        return cls(**values)

    def path(self, value: str) -> Path:
        return Path(value).expanduser()

    @property
    def database_file(self) -> Path:
        return self.path(self.database_path)

    @property
    def music_path(self) -> Path:
        return self.path(self.music_dir)

    @property
    def static_path(self) -> Path:
        return self.path(self.static_dir)

    @property
    def covers_path(self) -> Path:
        return self.static_path / "generated" / "covers"

    @property
    def tts_path(self) -> Path:
        return self.static_path / "generated" / "tts"

    @property
    def clips_path(self) -> Path:
        return self.static_path / "generated" / "clips"


def ensure_runtime_dirs(settings: Settings) -> None:
    for path in (
        settings.database_file.parent,
        settings.music_path,
        settings.covers_path,
        settings.tts_path,
        settings.clips_path,
        Path(settings.rss_feeds_path).parent,
        Path(settings.liquidsoap_queue_path).parent,
        Path(settings.liquidsoap_script_path).parent,
    ):
        path.mkdir(parents=True, exist_ok=True)
