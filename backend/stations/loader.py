from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import AudioProfile, PublicProfile, RuntimeProfile, StationProfile

STATION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,31}$")
LANGUAGE_LOCALES = {"en": "en-US", "fr": "fr-FR"}


class StationProfileError(ValueError):
    pass


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StationProfileError(f"{label} must be an object")
    return value


def _keys(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise StationProfileError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise StationProfileError(f"{label} unknown keys: {', '.join(unknown)}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise StationProfileError(f"{label} must be a string")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise StationProfileError(f"{label} must be an integer")
    return value


def _descendant(child: str, parent: str) -> bool:
    child_path = Path(child).expanduser().resolve()
    parent_path = Path(parent).expanduser().resolve()
    return child_path == parent_path or parent_path in child_path.parents


def _validate(profile: StationProfile) -> None:
    if profile.profile_version != 1:
        raise StationProfileError("profile_version must equal 1")
    if not STATION_ID.fullmatch(profile.station_id):
        raise StationProfileError("invalid station_id")
    if LANGUAGE_LOCALES.get(profile.language) != profile.locale:
        raise StationProfileError("language and locale do not agree")
    if profile.timezone != "Europe/Istanbul":
        raise StationProfileError("timezone must be Europe/Istanbul")
    if profile.audio.minimum_qwen_buffer < 5:
        raise StationProfileError("minimum_qwen_buffer must be at least 5")
    if (profile.audio.loudness_lufs, profile.audio.true_peak_dbtp) != (-16, -1):
        raise StationProfileError("audio targets must be -16 LUFS and -1 dBTP")
    if not profile.public.route.startswith("/") or not profile.audio.stream_mount.startswith("/"):
        raise StationProfileError("public route and stream mount must be absolute URL paths")
    for name in ("database", "announcement_root", "cache_root", "log_root"):
        if not _descendant(getattr(profile.runtime, name), profile.runtime.data_root):
            raise StationProfileError(f"runtime.{name} must stay beneath runtime.data_root")


def load_station_profile(path: str | Path) -> StationProfile:
    source = Path(path)
    try:
        raw = _mapping(json.loads(source.read_text(encoding="utf-8")), "profile")
    except (OSError, json.JSONDecodeError) as exc:
        raise StationProfileError(f"cannot load {source}: {exc}") from exc
    root_keys = {
        "profile_version",
        "station_id",
        "display_name",
        "language",
        "locale",
        "timezone",
        "public",
        "audio",
        "runtime",
        "voice_pack",
        "snapshot_secret_ref",
    }
    public_keys = {"route", "compatibility_routes", "snapshot_endpoint", "status_endpoint", "stream_url"}
    audio_keys = {"stream_mount", "loudness_lufs", "true_peak_dbtp", "minimum_qwen_buffer"}
    runtime_keys = {"data_root", "database", "music_root", "announcement_root", "cache_root", "log_root"}
    _keys(raw, root_keys, "profile")
    public = _mapping(raw["public"], "public")
    audio = _mapping(raw["audio"], "audio")
    runtime = _mapping(raw["runtime"], "runtime")
    _keys(public, public_keys, "public")
    _keys(audio, audio_keys, "audio")
    _keys(runtime, runtime_keys, "runtime")
    if not isinstance(public["compatibility_routes"], list) or not all(
        isinstance(item, str) for item in public["compatibility_routes"]
    ):
        raise StationProfileError("public.compatibility_routes must be a string array")
    try:
        profile = StationProfile(
            profile_version=_integer(raw["profile_version"], "profile.profile_version"),
            station_id=_string(raw["station_id"], "profile.station_id"),
            display_name=_string(raw["display_name"], "profile.display_name"),
            language=_string(raw["language"], "profile.language"),
            locale=_string(raw["locale"], "profile.locale"),
            timezone=_string(raw["timezone"], "profile.timezone"),
            public=PublicProfile(
                _string(public["route"], "public.route"),
                tuple(public["compatibility_routes"]),
                _string(public["snapshot_endpoint"], "public.snapshot_endpoint"),
                _string(public["status_endpoint"], "public.status_endpoint"),
                _string(public["stream_url"], "public.stream_url"),
            ),
            audio=AudioProfile(
                _string(audio["stream_mount"], "audio.stream_mount"),
                _integer(audio["loudness_lufs"], "audio.loudness_lufs"),
                _integer(audio["true_peak_dbtp"], "audio.true_peak_dbtp"),
                _integer(audio["minimum_qwen_buffer"], "audio.minimum_qwen_buffer"),
            ),
            runtime=RuntimeProfile(
                *(_string(runtime[name], f"runtime.{name}") for name in (
                    "data_root",
                    "database",
                    "music_root",
                    "announcement_root",
                    "cache_root",
                    "log_root",
                ))
            ),
            voice_pack=_string(raw["voice_pack"], "profile.voice_pack"),
            snapshot_secret_ref=_string(raw["snapshot_secret_ref"], "profile.snapshot_secret_ref"),
        )
    except (TypeError, ValueError) as exc:
        raise StationProfileError(f"invalid profile value: {exc}") from exc
    _validate(profile)
    return profile


def load_station_profiles(directory: str | Path) -> dict[str, StationProfile]:
    profiles = [load_station_profile(path) for path in sorted(Path(directory).glob("*.json"))]
    result = {profile.station_id: profile for profile in profiles}
    if len(result) != len(profiles):
        raise StationProfileError("duplicate station_id")
    unique_groups = {
        "route": [route for profile in profiles for route in (profile.public.route, *profile.public.compatibility_routes)],
        "snapshot_endpoint": [profile.public.snapshot_endpoint for profile in profiles],
        "status_endpoint": [profile.public.status_endpoint for profile in profiles],
        "stream_mount": [profile.audio.stream_mount for profile in profiles],
        "database": [str(Path(profile.runtime.database).resolve()) for profile in profiles],
        "data_root": [str(Path(profile.runtime.data_root).resolve()) for profile in profiles],
        "music_root": [str(Path(profile.runtime.music_root).resolve()) for profile in profiles],
        "announcement_root": [str(Path(profile.runtime.announcement_root).resolve()) for profile in profiles],
        "cache_root": [str(Path(profile.runtime.cache_root).resolve()) for profile in profiles],
        "log_root": [str(Path(profile.runtime.log_root).resolve()) for profile in profiles],
        "secret_ref": [profile.snapshot_secret_ref for profile in profiles],
    }
    for label, values in unique_groups.items():
        if len(values) != len(set(values)):
            raise StationProfileError(f"duplicate {label}")
    for profile in profiles:
        inspected = " ".join(
            (
                profile.public.snapshot_endpoint,
                profile.public.status_endpoint,
                profile.audio.stream_mount,
                profile.runtime.data_root,
                profile.runtime.database,
                profile.runtime.music_root,
                profile.runtime.announcement_root,
                profile.runtime.cache_root,
                profile.runtime.log_root,
                profile.snapshot_secret_ref,
            )
        )
        for other_id in result:
            if other_id != profile.station_id and other_id in inspected:
                raise StationProfileError(f"{profile.station_id} references {other_id}")
    return result
