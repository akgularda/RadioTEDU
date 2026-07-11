from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ..config import Settings, ensure_runtime_dirs
from .models import AudioProfile, PublicProfile, RuntimeProfile, StationProfile


@dataclass(frozen=True, slots=True)
class StationContext:
    settings: Settings
    profile: StationProfile

    @property
    def data_root(self) -> Path:
        return self.settings.path(self.profile.runtime.data_root).resolve()

    @property
    def database_file(self) -> Path:
        return self.settings.database_file.resolve()

    @property
    def music_root(self) -> Path:
        return self.settings.music_path.resolve()

    @property
    def announcement_root(self) -> Path:
        return self.settings.path(self.profile.runtime.announcement_root).resolve()

    @property
    def cache_root(self) -> Path:
        return self.settings.path(self.profile.runtime.cache_root).resolve()

    @property
    def log_root(self) -> Path:
        return self.settings.path(self.profile.runtime.log_root).resolve()


def build_station_context(settings: Settings, profile: StationProfile) -> StationContext:
    data_root = Path(profile.runtime.data_root)
    scoped = replace(
        settings,
        database_path=profile.runtime.database,
        music_dir=profile.runtime.music_root,
        static_dir=str(data_root / "public"),
        rss_feeds_path=str(data_root / "rss-feeds.json"),
        liquidsoap_queue_path=str(data_root / "liquidsoap" / "queue.m3u"),
        liquidsoap_script_path=str(data_root / "liquidsoap" / f"{profile.station_id}.liq"),
        liquidsoap_mount=profile.audio.stream_mount,
        public_dashboard_route=profile.public.route,
        public_stream_url=profile.public.stream_url,
        min_ready_announcements=profile.audio.minimum_qwen_buffer,
        max_ready_announcements=max(
            settings.max_ready_announcements,
            profile.audio.minimum_qwen_buffer,
        ),
        station_id=profile.station_id,
    )
    return StationContext(scoped, profile)


def english_compatibility_context(settings: Settings) -> StationContext:
    profile = StationProfile(
        1,
        "radiotedu-en",
        "RadioTEDU",
        "en",
        "en-US",
        "Europe/Istanbul",
        PublicProfile(
            "/ai/en",
            ("/ai",),
            "/api/public/stations/radiotedu-en/snapshot",
            "/api/public/stations/radiotedu-en/status",
            settings.public_stream_url,
        ),
        AudioProfile(
            "/radiotedu-en",
            -16,
            -1,
            max(5, settings.min_ready_announcements),
        ),
        RuntimeProfile(
            str(settings.database_file.parent),
            settings.database_path,
            settings.music_dir,
            str(settings.tts_path),
            str(settings.tts_path / "qwen-cache"),
            str(settings.database_file.parent / "logs"),
        ),
        "radiotedu-en-voices-v1",
        "RADIOTEDU_EN_SNAPSHOT_SECRET",
    )
    return StationContext(settings, profile)


def coerce_station_context(value: Settings | StationContext) -> StationContext:
    return value if isinstance(value, StationContext) else english_compatibility_context(value)


def ensure_station_runtime_dirs(context: StationContext) -> None:
    ensure_runtime_dirs(context.settings)
    for path in (
        context.data_root,
        context.announcement_root,
        context.cache_root,
        context.log_root,
    ):
        path.mkdir(parents=True, exist_ok=True)
