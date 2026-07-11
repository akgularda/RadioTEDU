# RadioTEDU Dual-Station Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce validated English and French station profiles, immutable station contexts, station-scoped runtime paths and databases, and compatibility-preserving context injection through scheduling, agents, orchestration, and FastAPI startup.

**Architecture:** `backend.stations` owns the frozen profile contract, strict JSON loading, and the conversion from shared operational `Settings` to a station-scoped `StationContext`. Existing runtime classes accept either a context or legacy `Settings`; legacy callers are adapted to the English station, while profile-started instances receive isolated databases and writable roots. The database-local channel key remains `radiotedu` in this foundation so existing English queries and history remain compatible; station identity is carried by `StationContext.profile.station_id`, and physical database separation prevents cross-station state access.

**Tech Stack:** Python 3.11+, frozen `dataclasses`, `pathlib`, JSON, SQLite, `zoneinfo`, FastAPI, pytest.

## Global Constraints

- The only station IDs are `radiotedu-en` and `radiotedu-fr`; IDs must match `^[a-z0-9][a-z0-9-]{2,31}$`.
- English is `en` / `en-US`; French is `fr` / `fr-FR`; both schedule in `Europe/Istanbul`.
- English public routes are `/ai/en` and compatibility alias `/ai`; French public route is `/ai/fr` with no compatibility alias.
- Stream mounts are `/radiotedu-en` and `/radiotedu-fr`.
- Qwen buffer floors are at least `5`; audio targets remain exactly `-16 LUFS` and `-1 dBTP`.
- Voice packs are `radiotedu-en-voices-v1` and `radiotedu-fr-voices-v1`.
- English and French databases, writable roots, queues, caches, logs, mounts, endpoints, and secret references must be unique.
- Profile validation must finish before directory creation, database creation, agent construction, thread startup, or any other side effect.
- Existing direct `Settings` callers remain English-compatible; existing `/ai`, program schedule, history, artwork behavior, and local database channel key remain intact.
- This plan does not implement Qwen synthesis, Snapshot v2, public `/ai/fr` rendering, Liquidsoap/Icecast services, voice commissioning, or production state-copy migration.
- At most three implementation workers may run concurrently, shared files have one owner, and OpenCode may review but may not change frozen interfaces.

---

## File Structure and Ownership

| Path | Responsibility | Owner task |
|---|---|---|
| `backend/stations/__init__.py` | Stable exports for station contracts | 1 |
| `backend/stations/models.py` | Frozen Station Profile v1 dataclasses | 1 |
| `backend/stations/loader.py` | Strict JSON and profile-set validation | 2 |
| `config/stations/radiotedu-en.json` | Canonical English profile | 2 |
| `config/stations/radiotedu-fr.json` | Canonical French profile | 2 |
| `backend/config.py` | Station selector settings only | 3 |
| `backend/stations/context.py` | Scoped settings, paths, compatibility adapter | 3 |
| `backend/database.py` | Context-aware connection and profile-driven seed | 4 |
| `backend/scheduler.py` | Context database and timezone-aware schedule reads | 4 |
| `backend/radio_agent.py` | Context injection into one agent instance | 5 |
| `backend/orchestrator.py` | Context injection and station-named worker | 5 |
| `backend/app.py` | Startup composition and English compatibility | 6 |
| `tests/backend/test_station_profiles.py` | Profile, loader, settings, and context contract tests | 1–3 |
| `tests/backend/test_station_isolation.py` | Database, runtime, and app isolation tests | 4–7 |

Forbidden throughout this plan: `release/**`, `frontend/**`, `backend/public_dashboard.py`, `backend/maintenance.py`, `backend/tts.py`, `backend/liquidsoap.py`, `backend/models.py`, `.env`, and every voice-pack, snapshot, installer, or deployment file. Any needed change there is a contract escalation to the lead agent, not an opportunistic edit.

### Task 1: Freeze Station Profile v1 Types

**Files:**
- Create: `backend/stations/__init__.py`
- Create: `backend/stations/models.py`
- Create/Test: `tests/backend/test_station_profiles.py`

**Owned files:** the three files above.
**Forbidden files:** every file outside the owned list.

**Interfaces:**
- Consumes: Python frozen dataclasses only.
- Produces: `PublicProfile`, `AudioProfile`, `RuntimeProfile`, and `StationProfile` from `backend.stations.models`, with the exact nested fields below.

- [ ] **Step 1: Write the failing immutable-contract test**

```python
# tests/backend/test_station_profiles.py
from dataclasses import FrozenInstanceError

import pytest

from backend.stations.models import AudioProfile, PublicProfile, RuntimeProfile, StationProfile


def make_profile(station_id: str = "radiotedu-en") -> StationProfile:
    return StationProfile(
        profile_version=1,
        station_id=station_id,
        display_name="RadioTEDU",
        language="en",
        locale="en-US",
        timezone="Europe/Istanbul",
        public=PublicProfile(
            route="/ai/en",
            compatibility_routes=("/ai",),
            snapshot_endpoint=f"/api/public/stations/{station_id}/snapshot",
            status_endpoint=f"/api/public/stations/{station_id}/status",
            stream_url=f"https://radiotedu.com:8001/{station_id}",
        ),
        audio=AudioProfile(f"/{station_id}", -16, -1, 5),
        runtime=RuntimeProfile(
            f"data/stations/{station_id}",
            f"data/stations/{station_id}/radio.db",
            f"media/stations/{station_id}/music",
            f"data/stations/{station_id}/announcements",
            f"data/stations/{station_id}/qwen-cache",
            f"data/stations/{station_id}/logs",
        ),
        voice_pack=f"{station_id}-voices-v1",
        snapshot_secret_ref="RADIOTEDU_EN_SNAPSHOT_SECRET",
    )


def test_station_profile_is_nested_and_immutable() -> None:
    profile = make_profile()
    assert profile.public.compatibility_routes == ("/ai",)
    assert profile.audio.minimum_qwen_buffer == 5
    with pytest.raises(FrozenInstanceError):
        profile.display_name = "changed"  # type: ignore[misc]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/backend/test_station_profiles.py::test_station_profile_is_nested_and_immutable -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.stations'`.

- [ ] **Step 3: Add the exact frozen dataclasses and exports**

```python
# backend/stations/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicProfile:
    route: str
    compatibility_routes: tuple[str, ...]
    snapshot_endpoint: str
    status_endpoint: str
    stream_url: str


@dataclass(frozen=True, slots=True)
class AudioProfile:
    stream_mount: str
    loudness_lufs: int
    true_peak_dbtp: int
    minimum_qwen_buffer: int


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    data_root: str
    database: str
    music_root: str
    announcement_root: str
    cache_root: str
    log_root: str


@dataclass(frozen=True, slots=True)
class StationProfile:
    profile_version: int
    station_id: str
    display_name: str
    language: str
    locale: str
    timezone: str
    public: PublicProfile
    audio: AudioProfile
    runtime: RuntimeProfile
    voice_pack: str
    snapshot_secret_ref: str
```

```python
# backend/stations/__init__.py
from .models import AudioProfile, PublicProfile, RuntimeProfile, StationProfile

__all__ = ["AudioProfile", "PublicProfile", "RuntimeProfile", "StationProfile"]
```

- [ ] **Step 4: Run the contract test to verify it passes**

Run: `python -m pytest tests/backend/test_station_profiles.py::test_station_profile_is_nested_and_immutable -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/stations/__init__.py backend/stations/models.py tests/backend/test_station_profiles.py
git commit -m "feat: freeze station profile contract"
```

### Task 2: Load and Validate the Two Canonical Profiles

**Files:**
- Create: `backend/stations/loader.py`
- Create: `config/stations/radiotedu-en.json`
- Create: `config/stations/radiotedu-fr.json`
- Modify/Test: `tests/backend/test_station_profiles.py`

**Owned files:** the four files above plus the named test file.
**Forbidden files:** all runtime and application modules.

**Interfaces:**
- Consumes: the exact dataclasses from Task 1.
- Produces: `StationProfileError`, `load_station_profile(path: str | Path) -> StationProfile`, and `load_station_profiles(directory: str | Path) -> dict[str, StationProfile]`.

- [ ] **Step 1: Add failing canonical and fail-before-side-effect tests**

```python
from pathlib import Path

from backend.stations.loader import StationProfileError, load_station_profile, load_station_profiles


def test_canonical_profiles_have_frozen_identity() -> None:
    profiles = load_station_profiles(Path("config/stations"))
    assert set(profiles) == {"radiotedu-en", "radiotedu-fr"}
    assert profiles["radiotedu-en"].public.compatibility_routes == ("/ai",)
    assert profiles["radiotedu-fr"].public.compatibility_routes == ()
    assert profiles["radiotedu-fr"].voice_pack == "radiotedu-fr-voices-v1"


def test_unknown_key_is_rejected_before_runtime_paths_are_created(tmp_path: Path) -> None:
    profile_path = tmp_path / "bad.json"
    data_root = tmp_path / "must-not-exist"
    raw = Path("config/stations/radiotedu-en.json").read_text(encoding="utf-8")
    profile_path.write_text(raw.replace('"profile_version": 1', '"profile_version": 1, "extra": true').replace("data/stations/radiotedu-en", str(data_root).replace("\\", "/")), encoding="utf-8")
    with pytest.raises(StationProfileError, match="unknown keys: extra"):
        load_station_profile(profile_path)
    assert not data_root.exists()
```

- [ ] **Step 2: Run the loader tests to verify they fail**

Run: `python -m pytest tests/backend/test_station_profiles.py -k "canonical or unknown_key" -q`

Expected: FAIL during collection because `backend.stations.loader` does not exist.

- [ ] **Step 3: Implement strict parsing and set-level uniqueness validation**

```python
# backend/stations/loader.py
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
    root_keys = {"profile_version", "station_id", "display_name", "language", "locale", "timezone", "public", "audio", "runtime", "voice_pack", "snapshot_secret_ref"}
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
    if not isinstance(public["compatibility_routes"], list) or not all(isinstance(item, str) for item in public["compatibility_routes"]):
        raise StationProfileError("public.compatibility_routes must be a string array")
    try:
        profile = StationProfile(
            profile_version=int(raw["profile_version"]), station_id=str(raw["station_id"]), display_name=str(raw["display_name"]),
            language=str(raw["language"]), locale=str(raw["locale"]), timezone=str(raw["timezone"]),
            public=PublicProfile(str(public["route"]), tuple(public["compatibility_routes"]), str(public["snapshot_endpoint"]), str(public["status_endpoint"]), str(public["stream_url"])),
            audio=AudioProfile(str(audio["stream_mount"]), int(audio["loudness_lufs"]), int(audio["true_peak_dbtp"]), int(audio["minimum_qwen_buffer"])),
            runtime=RuntimeProfile(*(str(runtime[name]) for name in ("data_root", "database", "music_root", "announcement_root", "cache_root", "log_root"))),
            voice_pack=str(raw["voice_pack"]), snapshot_secret_ref=str(raw["snapshot_secret_ref"]),
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
        "route": [route for p in profiles for route in (p.public.route, *p.public.compatibility_routes)],
        "snapshot_endpoint": [p.public.snapshot_endpoint for p in profiles],
        "status_endpoint": [p.public.status_endpoint for p in profiles],
        "stream_mount": [p.audio.stream_mount for p in profiles],
        "database": [str(Path(p.runtime.database).resolve()) for p in profiles],
        "data_root": [str(Path(p.runtime.data_root).resolve()) for p in profiles],
        "music_root": [str(Path(p.runtime.music_root).resolve()) for p in profiles],
        "announcement_root": [str(Path(p.runtime.announcement_root).resolve()) for p in profiles],
        "cache_root": [str(Path(p.runtime.cache_root).resolve()) for p in profiles],
        "log_root": [str(Path(p.runtime.log_root).resolve()) for p in profiles],
        "secret_ref": [p.snapshot_secret_ref for p in profiles],
    }
    for label, values in unique_groups.items():
        if len(values) != len(set(values)):
            raise StationProfileError(f"duplicate {label}")
    for profile in profiles:
        inspected = " ".join((
            profile.public.snapshot_endpoint, profile.public.status_endpoint, profile.audio.stream_mount,
            profile.runtime.data_root, profile.runtime.database, profile.runtime.music_root,
            profile.runtime.announcement_root, profile.runtime.cache_root, profile.runtime.log_root,
            profile.snapshot_secret_ref,
        ))
        for other_id in result:
            if other_id != profile.station_id and other_id in inspected:
                raise StationProfileError(f"{profile.station_id} references {other_id}")
    return result
```

`config/stations/radiotedu-en.json`:

```json
{
  "profile_version": 1,
  "station_id": "radiotedu-en",
  "display_name": "RadioTEDU",
  "language": "en",
  "locale": "en-US",
  "timezone": "Europe/Istanbul",
  "public": {
    "route": "/ai/en",
    "compatibility_routes": ["/ai"],
    "snapshot_endpoint": "/api/public/stations/radiotedu-en/snapshot",
    "status_endpoint": "/api/public/stations/radiotedu-en/status",
    "stream_url": "https://radiotedu.com:8001/radiotedu-en"
  },
  "audio": {"stream_mount": "/radiotedu-en", "loudness_lufs": -16, "true_peak_dbtp": -1, "minimum_qwen_buffer": 5},
  "runtime": {
    "data_root": "data/stations/radiotedu-en",
    "database": "data/stations/radiotedu-en/radio.db",
    "music_root": "media/stations/radiotedu-en/music",
    "announcement_root": "data/stations/radiotedu-en/announcements",
    "cache_root": "data/stations/radiotedu-en/qwen-cache",
    "log_root": "data/stations/radiotedu-en/logs"
  },
  "voice_pack": "radiotedu-en-voices-v1",
  "snapshot_secret_ref": "RADIOTEDU_EN_SNAPSHOT_SECRET"
}
```

`config/stations/radiotedu-fr.json`:

```json
{
  "profile_version": 1,
  "station_id": "radiotedu-fr",
  "display_name": "RadioTEDU Français",
  "language": "fr",
  "locale": "fr-FR",
  "timezone": "Europe/Istanbul",
  "public": {
    "route": "/ai/fr",
    "compatibility_routes": [],
    "snapshot_endpoint": "/api/public/stations/radiotedu-fr/snapshot",
    "status_endpoint": "/api/public/stations/radiotedu-fr/status",
    "stream_url": "https://radiotedu.com:8001/radiotedu-fr"
  },
  "audio": {"stream_mount": "/radiotedu-fr", "loudness_lufs": -16, "true_peak_dbtp": -1, "minimum_qwen_buffer": 5},
  "runtime": {
    "data_root": "data/stations/radiotedu-fr",
    "database": "data/stations/radiotedu-fr/radio.db",
    "music_root": "media/stations/radiotedu-fr/music",
    "announcement_root": "data/stations/radiotedu-fr/announcements",
    "cache_root": "data/stations/radiotedu-fr/qwen-cache",
    "log_root": "data/stations/radiotedu-fr/logs"
  },
  "voice_pack": "radiotedu-fr-voices-v1",
  "snapshot_secret_ref": "RADIOTEDU_FR_SNAPSHOT_SECRET"
}
```

- [ ] **Step 4: Run profile tests**

Run: `python -m pytest tests/backend/test_station_profiles.py -q`

Expected: all tests PASS, including deterministic rejection without created runtime directories.

- [ ] **Step 5: Commit**

```bash
git add backend/stations/loader.py config/stations/radiotedu-en.json config/stations/radiotedu-fr.json tests/backend/test_station_profiles.py
git commit -m "feat: validate canonical station profiles"
```

### Task 3: Derive an Immutable Station Context and Scoped Settings

**Files:**
- Create: `backend/stations/context.py`
- Modify: `backend/config.py`
- Modify/Test: `tests/backend/test_station_profiles.py`

**Owned files:** the three files above.
**Forbidden files:** database, scheduler, agent, orchestrator, app, and public modules.

**Interfaces:**
- Consumes: `StationProfile`, `Settings`.
- Produces: `StationContext`, `build_station_context(settings: Settings, profile: StationProfile) -> StationContext`, `english_compatibility_context(settings: Settings) -> StationContext`, `coerce_station_context(value: Settings | StationContext) -> StationContext`, and `ensure_station_runtime_dirs(context: StationContext) -> None`.

- [ ] **Step 1: Add a failing path-isolation test**

```python
from backend.config import Settings
from backend.stations.context import build_station_context


def test_context_derives_station_scoped_settings() -> None:
    profiles = load_station_profiles("config/stations")
    context = build_station_context(Settings(), profiles["radiotedu-fr"])
    assert context.profile.station_id == "radiotedu-fr"
    assert context.settings.database_path.endswith("data/stations/radiotedu-fr/radio.db")
    assert context.settings.liquidsoap_mount == "/radiotedu-fr"
    assert context.announcement_root != context.cache_root
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/backend/test_station_profiles.py::test_context_derives_station_scoped_settings -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.stations.context'`.

- [ ] **Step 3: Add selector settings and the exact context interface**

In `Settings`, add `station_id: str = "radiotedu-en"` and `station_profiles_dir: str = "config/stations"`; add mappings `"station_id": "STATION_ID"` and `"station_profiles_dir": "STATION_PROFILES_DIR"` to `from_env()`'s `key_map`, then add:

```python
@property
def station_profiles_path(self) -> Path:
    return self.path(self.station_profiles_dir)
```

```python
# backend/stations/context.py
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
        max_ready_announcements=max(settings.max_ready_announcements, profile.audio.minimum_qwen_buffer),
        station_id=profile.station_id,
    )
    return StationContext(scoped, profile)


def english_compatibility_context(settings: Settings) -> StationContext:
    profile = StationProfile(
        1, "radiotedu-en", "RadioTEDU", "en", "en-US", "Europe/Istanbul",
        PublicProfile("/ai/en", ("/ai",), "/api/public/stations/radiotedu-en/snapshot", "/api/public/stations/radiotedu-en/status", settings.public_stream_url),
        AudioProfile("/radiotedu-en", -16, -1, max(5, settings.min_ready_announcements)),
        RuntimeProfile(str(settings.database_file.parent), settings.database_path, settings.music_dir, str(settings.tts_path), str(settings.tts_path / "qwen-cache"), str(settings.database_file.parent / "logs")),
        "radiotedu-en-voices-v1", "RADIOTEDU_EN_SNAPSHOT_SECRET",
    )
    return StationContext(settings, profile)


def coerce_station_context(value: Settings | StationContext) -> StationContext:
    return value if isinstance(value, StationContext) else english_compatibility_context(value)


def ensure_station_runtime_dirs(context: StationContext) -> None:
    ensure_runtime_dirs(context.settings)
    for path in (context.data_root, context.announcement_root, context.cache_root, context.log_root):
        path.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run focused and configuration regression tests**

Run: `python -m pytest tests/backend/test_station_profiles.py tests/backend/test_core_behaviour.py -q`

Expected: all tests PASS; legacy `Settings` paths remain unchanged unless `build_station_context` is called.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/stations/context.py tests/backend/test_station_profiles.py
git commit -m "feat: derive isolated station contexts"
```

### Task 4: Make Database Seeding and Scheduling Context-Aware

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/scheduler.py`
- Create/Test: `tests/backend/test_station_isolation.py`

**Owned files:** the three files above.
**Forbidden files:** agent, orchestrator, app, maintenance, and public dashboard.

**Interfaces:**
- Consumes: `Settings | StationContext` through `coerce_station_context`.
- Produces: context-aware `connect`, `init_db`, `seed_channel`, `seed_programs`, `current_program`, and `next_programs`; direct legacy `Settings` calls retain current behavior.

- [ ] **Step 1: Write the failing database-isolation test**

```python
# tests/backend/test_station_isolation.py
from dataclasses import replace
from pathlib import Path

from backend.config import Settings
from backend.database import connect, init_db
from backend.stations.context import build_station_context
from backend.stations.loader import load_station_profiles


def contexts(tmp_path: Path):
    profiles = load_station_profiles("config/stations")
    result = {}
    for station_id, profile in profiles.items():
        root = tmp_path / station_id
        runtime = replace(profile.runtime, data_root=str(root), database=str(root / "radio.db"), music_root=str(root / "music"), announcement_root=str(root / "announcements"), cache_root=str(root / "cache"), log_root=str(root / "logs"))
        result[station_id] = build_station_context(Settings(static_dir=str(root / "public")), replace(profile, runtime=runtime))
    return result


def test_station_databases_do_not_share_program_state(tmp_path: Path) -> None:
    stations = contexts(tmp_path)
    for context in stations.values():
        init_db(context)
    with connect(stations["radiotedu-en"]) as conn:
        conn.execute("update programs set name='English-only edit' where id='morning_signal'")
        conn.commit()
    with connect(stations["radiotedu-fr"]) as conn:
        name = conn.execute("select name from programs where id='morning_signal'").fetchone()[0]
    assert name != "English-only edit"
    assert stations["radiotedu-en"].database_file != stations["radiotedu-fr"].database_file
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/backend/test_station_isolation.py::test_station_databases_do_not_share_program_state -q`

Expected: FAIL because `connect()` and `init_db()` expect `Settings`, not `StationContext`.

- [ ] **Step 3: Replace settings-only database boundaries with context coercion**

Use `Runtime = Settings | StationContext`. At the start of `connect()` and `init_db()`, coerce once and use `context.settings`; pass the context into both seed functions. Keep the database-local channel key `radiotedu`, but replace seed identity values with `context.profile.display_name` and a language-aware description. Change `seed_programs(conn)` to `seed_programs(conn, context)` and parameterize its `channel_id` value as `"radiotedu"`. Do not change table schemas or program IDs.

```python
Runtime = Settings | StationContext
DATABASE_CHANNEL_ID = "radiotedu"


@contextmanager
def connect(runtime: Runtime):
    context = coerce_station_context(runtime)
    conn = sqlite3.connect(context.database_file)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(runtime: Runtime) -> None:
    context = coerce_station_context(runtime)
    ensure_station_runtime_dirs(context)
    with connect(context) as conn:
        conn.executescript(SCHEMA)
        conn.execute("drop table if exists donations")
        migrate_program_columns(conn)
        seed_channel(conn, context)
        seed_programs(conn, context)
        conn.commit()
```

In `scheduler.py`, accept `Settings | StationContext`, coerce before database access, and calculate implicit current time with `ZoneInfo(context.profile.timezone)`:

```python
def _programs_from_db(runtime: Settings | StationContext) -> list[dict]:
    context = coerce_station_context(runtime)
    with connect(context) as conn:
        rows = conn.execute(
            "select id, name, description, vibe, start_time, end_time, days_of_week, cover_path, active "
            "from programs where channel_id=? and active=1 order by start_time",
            (DATABASE_CHANNEL_ID,),
        ).fetchall()
    return rows_to_dicts(rows)


def current_program(runtime: Settings | StationContext | None = None, now: datetime | None = None) -> dict:
    context = coerce_station_context(runtime) if runtime is not None else None
    now = now or datetime.now(ZoneInfo(context.profile.timezone) if context else None)
    day, minute = DAY_KEYS[now.weekday()], now.hour * 60 + now.minute
    programs = _programs_from_db(context) if context else [dict(program) for program in PROGRAMS]
    return next((dict(program) for program in programs if _matches(program, day, minute)), dict(programs[0] if programs else PROGRAMS[0]))


def next_programs(runtime: Settings | StationContext | None = None, limit: int = 4) -> list[dict]:
    programs = _programs_from_db(coerce_station_context(runtime)) if runtime is not None else [dict(program) for program in PROGRAMS]
    return [dict(program) for program in programs[:limit]]
```

- [ ] **Step 4: Run isolation and scheduler regressions**

Run: `python -m pytest tests/backend/test_station_isolation.py tests/backend/test_core_behaviour.py -k "station_databases or program or schedule" -q`

Expected: all selected tests PASS; the English-only mutation is absent from the French database.

- [ ] **Step 5: Commit**

```bash
git add backend/database.py backend/scheduler.py tests/backend/test_station_isolation.py
git commit -m "feat: isolate station databases and schedules"
```

### Task 5: Inject Station Context into the Agent and Orchestrator

**Files:**
- Modify: `backend/radio_agent.py`
- Modify: `backend/orchestrator.py`
- Modify/Test: `tests/backend/test_station_isolation.py`

**Owned files:** the three files above.
**Forbidden files:** app, public dashboard, maintenance, audio, and TTS modules.

**Interfaces:**
- Consumes: `coerce_station_context(Settings | StationContext)` and context-aware database/scheduler APIs.
- Produces: `RadioAgent(runtime: Settings | StationContext)` and `AutonomousOrchestrator(runtime: Settings | StationContext, agent: RadioAgent)`; both expose `.context` and retain `.settings` for unchanged collaborators.

- [ ] **Step 1: Add a failing constructor-isolation test**

```python
def test_agent_and_orchestrator_retain_their_station_contexts(tmp_path: Path, monkeypatch) -> None:
    from backend import radio_agent as radio_agent_module
    from backend.orchestrator import AutonomousOrchestrator

    class StubPlayback:
        def __init__(self, settings): self.settings = settings

    monkeypatch.setattr(radio_agent_module, "PlaybackController", StubPlayback)
    monkeypatch.setattr(radio_agent_module, "build_tts_provider", lambda settings: object())
    stations = contexts(tmp_path)
    agents = {station_id: radio_agent_module.RadioAgent(context) for station_id, context in stations.items()}
    orchestrators = {station_id: AutonomousOrchestrator(stations[station_id], agent) for station_id, agent in agents.items()}
    assert agents["radiotedu-en"].context.profile.station_id == "radiotedu-en"
    assert orchestrators["radiotedu-fr"].context.profile.station_id == "radiotedu-fr"
    assert orchestrators["radiotedu-en"]._thread_name != orchestrators["radiotedu-fr"]._thread_name
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/backend/test_station_isolation.py::test_agent_and_orchestrator_retain_their_station_contexts -q`

Expected: FAIL because the constructors do not expose `.context` and the orchestrator has no station-specific thread name.

- [ ] **Step 3: Migrate constructors without changing collaborators**

```python
# Replace RadioAgent.__init__ signature and first assignments.
def __init__(self, runtime: Settings | StationContext) -> None:
    self.context = coerce_station_context(runtime)
    self.settings = self.context.settings
    init_db(self.context)
    self.playback = PlaybackController(self.settings)
    self.tts = build_tts_provider(self.settings)
    # Keep the existing timestamp/provider state assignments exactly as they are.
```

```python
# Replace AutonomousOrchestrator.__init__ and the thread construction line.
def __init__(self, runtime: Settings | StationContext, agent: RadioAgent) -> None:
    self.context = coerce_station_context(runtime)
    self.settings = self.context.settings
    self.agent = agent
    self._stop = threading.Event()
    self._thread: threading.Thread | None = None
    self._thread_name = f"radiotedu-orchestrator-{self.context.profile.station_id}"
    self.last_tick_at: datetime | None = None
    self.last_strategy_at: datetime | None = None
    self.last_error: str | None = None
    self.public_pusher = PublicSnapshotPusher(self.settings, agent)

# In start_background():
self._thread = threading.Thread(target=self._run_forever, name=self._thread_name, daemon=True)
```

Pass `self.context` to `connect`, `init_db`, `current_program`, and `next_programs` inside these two classes. Continue passing `self.settings` to un-migrated playback, TTS, weather, LLM, search, and public-pusher collaborators.

- [ ] **Step 4: Run agent/orchestrator tests**

Run: `python -m pytest tests/backend/test_station_isolation.py::test_agent_and_orchestrator_retain_their_station_contexts tests/backend/test_autonomous_orchestrator.py -q`

Expected: all tests PASS; direct `Settings` construction remains English-compatible.

- [ ] **Step 5: Commit**

```bash
git add backend/radio_agent.py backend/orchestrator.py tests/backend/test_station_isolation.py
git commit -m "feat: bind agents to station contexts"
```

### Task 6: Compose Profile-Started Apps with English Compatibility

**Files:**
- Modify: `backend/app.py`
- Modify/Test: `tests/backend/test_station_isolation.py`

**Owned files:** the two files above.
**Forbidden files:** all frontend, public snapshot, audio, and deployment files.

**Interfaces:**
- Consumes: selector fields on `Settings`, `load_station_profiles`, context builders, migrated agent/orchestrator constructors.
- Produces: `create_app(settings: Settings | None = None, station_context: StationContext | None = None) -> FastAPI`; `app.state.station_context` is always present. Explicit legacy `Settings` uses the English adapter; default startup loads the selected canonical profile before side effects.

- [ ] **Step 1: Add failing app-composition tests**

```python
def test_create_app_accepts_isolated_station_context(tmp_path: Path) -> None:
    from backend.app import create_app

    french = contexts(tmp_path)["radiotedu-fr"]
    app = create_app(station_context=french)
    assert app.state.station_context.profile.station_id == "radiotedu-fr"
    assert app.state.agent.context is french
    assert app.state.orchestrator.context is french


def test_create_app_settings_argument_remains_english_compatible(tmp_path: Path) -> None:
    from backend.app import create_app

    settings = Settings(database_path=str(tmp_path / "legacy.db"), static_dir=str(tmp_path / "static"))
    app = create_app(settings)
    assert app.state.station_context.profile.station_id == "radiotedu-en"
    assert app.state.settings.database_file == tmp_path / "legacy.db"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/backend/test_station_isolation.py -k "create_app" -q`

Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'station_context'`.

- [ ] **Step 3: Replace only the startup-composition block**

```python
def create_app(settings: Settings | None = None, station_context: StationContext | None = None) -> FastAPI:
    if settings is not None and station_context is not None:
        raise ValueError("pass settings or station_context, not both")
    if station_context is not None:
        context = station_context
    elif settings is not None:
        context = english_compatibility_context(settings)
    else:
        base_settings = Settings.from_env()
        profiles = load_station_profiles(base_settings.station_profiles_path)
        try:
            profile = profiles[base_settings.station_id]
        except KeyError as exc:
            raise StationProfileError(f"unknown STATION_ID: {base_settings.station_id}") from exc
        context = build_station_context(base_settings, profile)

    ensure_station_runtime_dirs(context)
    init_db(context)
    generate_covers(context.settings)
    agent = RadioAgent(context)
    orchestrator = AutonomousOrchestrator(context, agent)
    public_snapshot_pusher = (
        PublicSnapshotPusher(context.settings, agent)
        if context.settings.public_sync_url and context.settings.public_sync_token
        else None
    )
    app = FastAPI(title=context.profile.display_name)
    app.state.station_context = context
    app.state.settings = context.settings
    app.state.agent = agent
    app.state.orchestrator = orchestrator
    app.state.public_snapshot_pusher = public_snapshot_pusher
    settings = context.settings
    # The existing middleware, routes, lifecycle handlers, and return statement continue unchanged below this assignment.
```

Add imports for `StationContext`, `build_station_context`, `english_compatibility_context`, `ensure_station_runtime_dirs`, `StationProfileError`, and `load_station_profiles`. The assignment `settings = context.settings` is the compatibility boundary for every unchanged route closure.

- [ ] **Step 4: Run app and English compatibility regressions**

Run: `python -m pytest tests/backend/test_station_isolation.py -k "create_app" tests/backend/test_core_behaviour.py -q`

Expected: all tests PASS; existing English API assertions still report the legacy local channel ID and `/ai` remains available.

- [ ] **Step 5: Commit**

```bash
git add backend/app.py tests/backend/test_station_isolation.py
git commit -m "feat: compose apps from station contexts"
```

### Task 7: Prove Negative Isolation and Run the Foundation Gate

**Files:**
- Modify/Test: `tests/backend/test_station_profiles.py`
- Modify/Test: `tests/backend/test_station_isolation.py`

**Owned files:** only the two test files.
**Forbidden files:** every production file; failures produce a bounded remediation task for the owning task.

**Interfaces:**
- Consumes: all foundation interfaces from Tasks 1–6.
- Produces: executable evidence that wrong paths fail before writes, databases and writable roots differ, mutations do not cross station boundaries, and legacy English callers still work.

- [ ] **Step 1: Add the final negative tests**

```python
def test_profiles_have_no_shared_writable_or_identity_values() -> None:
    profiles = load_station_profiles("config/stations")
    english, french = profiles["radiotedu-en"], profiles["radiotedu-fr"]
    assert english.runtime.database != french.runtime.database
    assert english.runtime.cache_root != french.runtime.cache_root
    assert english.runtime.log_root != french.runtime.log_root
    assert english.audio.stream_mount != french.audio.stream_mount
    assert english.snapshot_secret_ref != french.snapshot_secret_ref
    assert set(english.public.compatibility_routes).isdisjoint({french.public.route, *french.public.compatibility_routes})


def test_logs_and_channel_names_are_database_local(tmp_path: Path) -> None:
    stations = contexts(tmp_path)
    for context in stations.values():
        init_db(context)
    with connect(stations["radiotedu-en"]) as conn:
        conn.execute("insert into agent_logs(level,message,metadata_json,created_at) values('info','english only','{}','2026-07-10T00:00:00+00:00')")
        conn.commit()
    with connect(stations["radiotedu-fr"]) as conn:
        assert conn.execute("select count(*) from agent_logs where message='english only'").fetchone()[0] == 0
        assert conn.execute("select name from channels where id='radiotedu'").fetchone()[0] == "RadioTEDU Français"
```

- [ ] **Step 2: Run the negative tests**

Run: `python -m pytest tests/backend/test_station_profiles.py tests/backend/test_station_isolation.py -q`

Expected: all tests PASS with no file created outside each test's station root.

- [ ] **Step 3: Run the complete backend gate**

Run: `python -m pytest tests/backend -q`

Expected: all backend tests PASS; no legacy English expectation changes and no warning names a shared station database.

- [ ] **Step 4: Run static import and profile-startup smoke checks**

Run: `python -c "from backend.config import Settings; from backend.stations.loader import load_station_profiles; from backend.stations.context import build_station_context; p=load_station_profiles('config/stations'); assert all(build_station_context(Settings(), v).profile.station_id == k for k, v in p.items()); print('dual-station foundation ok')"`

Expected: exactly `dual-station foundation ok`.

- [ ] **Step 5: Commit**

```bash
git add tests/backend/test_station_profiles.py tests/backend/test_station_isolation.py
git commit -m "test: prove station state isolation"
```

## Execution Order and Review Gates

Tasks 1–3 are sequential because they freeze the shared profile/context interfaces. Task 4 follows Task 3. Task 5 follows Task 4. Task 6 follows Tasks 2–5. Task 7 is read-only production validation after every earlier commit. Mini-class agents may implement Tasks 1, 2, 4, and 5; a stronger reasoning agent reviews Tasks 3 and 6 because they control path isolation and compatibility. OpenCode may independently review Tasks 2, 3, 6, and 7 without editing owned files.

Plan complete and saved to `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-foundation.md`. Recommended execution is subagent-driven with one fresh bounded worker per task and an independent interface/isolation review after Tasks 3, 6, and 7.
