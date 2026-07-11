from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.stations.context import build_station_context
from backend.stations.loader import load_station_profiles


class RecordingAgent:
    def __init__(self, context) -> None:
        self.context = context
        self.starts = 0
        self.stops = 0

    def start(self) -> dict:
        self.starts += 1
        return {"started": True, "source": "music"}

    def stop(self) -> dict:
        self.stops += 1
        return {"stopped": True}


class FailingAutonomy:
    def __init__(self, context) -> None:
        self.context = context
        self.starts = 0
        self.stops = 0

    def start_background(self) -> dict:
        self.starts += 1
        raise RuntimeError("AI is unavailable")

    def stop_background(self) -> dict:
        self.stops += 1
        return {"running": False}


class RecordingPusher:
    def __init__(self, context) -> None:
        self.context = context
        self.starts = 0
        self.stops = 0

    def start_background(self) -> dict:
        self.starts += 1
        return {"running": True}

    def stop_background(self) -> dict:
        self.stops += 1
        return {"running": False}


def station_context(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[2]
    profile = load_station_profiles(project_root / "config" / "stations")["radiotedu-en"]
    data_root = tmp_path / "data" / "stations" / "radiotedu-en"
    runtime = replace(
        profile.runtime,
        data_root=str(data_root),
        database=str(data_root / "radio.db"),
        music_root=str(tmp_path / "media" / "stations" / "radiotedu-en" / "music"),
        announcement_root=str(data_root / "announcements"),
        cache_root=str(data_root / "cache"),
        log_root=str(data_root / "logs"),
    )
    return build_station_context(
        Settings(static_dir=str(data_root / "public"), autonomy_enabled=False),
        replace(profile, runtime=runtime),
    )


def test_station_runtime_keeps_music_available_when_ai_lifecycle_fails() -> None:
    from backend.runtime.station_runtime import StationRuntime

    context = SimpleNamespace(profile=SimpleNamespace(station_id="radiotedu-en"))
    agent = RecordingAgent(context)
    autonomy = FailingAutonomy(context)
    pusher = RecordingPusher(context)
    runtime = StationRuntime(context, agent, autonomy, pusher)

    started = runtime.start()
    stopped = runtime.stop()

    assert started["station_id"] == "radiotedu-en"
    assert started["music"] == {"started": True, "source": "music"}
    assert started["autonomy"] == {"running": False, "reason": "unavailable"}
    assert agent.starts == 1
    assert autonomy.starts == 1
    assert pusher.starts == 1
    assert stopped["music"] == {"stopped": True}
    assert agent.stops == 1
    assert autonomy.stops == 1
    assert pusher.stops == 1


def test_station_runtime_starts_and_stops_each_owned_component_once() -> None:
    from backend.runtime.station_runtime import StationRuntime

    context = SimpleNamespace(profile=SimpleNamespace(station_id="radiotedu-fr"))
    agent = RecordingAgent(context)
    autonomy = RecordingPusher(context)
    pusher = RecordingPusher(context)
    runtime = StationRuntime(context, agent, autonomy, pusher)

    runtime.start()
    runtime.start()
    runtime.stop()
    runtime.stop()

    assert agent.starts == 1
    assert autonomy.starts == 1
    assert pusher.starts == 1
    assert agent.stops == 1
    assert autonomy.stops == 1
    assert pusher.stops == 1


def test_app_delegates_public_state_lifecycle_to_its_station_runtime(tmp_path: Path, monkeypatch) -> None:
    from backend.app import create_app

    monkeypatch.chdir(tmp_path)
    context = station_context(tmp_path)
    pusher = RecordingPusher(context)
    app = create_app(station_context=context, snapshot_pusher=pusher)

    with TestClient(app):
        assert app.state.runtime.context is context

    assert pusher.starts == 1
    assert pusher.stops == 1
