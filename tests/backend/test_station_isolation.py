import os
from dataclasses import replace
from datetime import datetime as RealDateTime
from pathlib import Path
from unittest.mock import PropertyMock

import pytest

import backend.database as database_module
import backend.scheduler as scheduler_module
from backend.config import Settings
from backend.database import connect, init_db
from backend.scheduler import current_program, next_programs
from backend.stations.context import StationContext, build_station_context
from backend.stations.loader import load_station_profiles


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_CHANNEL_ID = "radiotedu"


def contexts(tmp_path: Path) -> dict[str, StationContext]:
    profiles = load_station_profiles(PROJECT_ROOT / "config" / "stations")
    result: dict[str, StationContext] = {}
    for station_id, profile in profiles.items():
        data_root = tmp_path / "data" / "stations" / station_id
        runtime = replace(
            profile.runtime,
            data_root=str(data_root),
            database=str(data_root / "radio.db"),
            music_root=str(tmp_path / "media" / "stations" / station_id / "music"),
            announcement_root=str(data_root / "announcements"),
            cache_root=str(data_root / "cache"),
            log_root=str(data_root / "logs"),
        )
        result[station_id] = build_station_context(
            Settings(static_dir=str(data_root / "public")),
            replace(profile, runtime=runtime),
        )
    return result


def test_station_databases_do_not_share_program_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stations = contexts(tmp_path)
    for context in stations.values():
        init_db(context)

    with connect(stations["radiotedu-en"]) as conn:
        conn.execute(
            "update programs set name=? where id=? and channel_id=?",
            ("English-only edit", "morning_signal", DATABASE_CHANNEL_ID),
        )
        conn.execute(
            "insert into listener_events (channel_id, event_type, created_at, metadata_json) values (?, ?, ?, ?)",
            (DATABASE_CHANNEL_ID, "english-only-event", "2026-07-11T00:00:00+00:00", "{}"),
        )
        conn.commit()
    with connect(stations["radiotedu-fr"]) as conn:
        conn.execute(
            "insert into listener_events (channel_id, event_type, created_at, metadata_json) values (?, ?, ?, ?)",
            (DATABASE_CHANNEL_ID, "french-only-event", "2026-07-11T00:00:00+00:00", "{}"),
        )
        conn.commit()
        name = conn.execute(
            "select name from programs where id=? and channel_id=?",
            ("morning_signal", DATABASE_CHANNEL_ID),
        ).fetchone()[0]
        french_events = [row[0] for row in conn.execute("select event_type from listener_events order by id")]
    with connect(stations["radiotedu-en"]) as conn:
        english_events = [row[0] for row in conn.execute("select event_type from listener_events order by id")]

    assert name != "English-only edit"
    assert english_events == ["english-only-event"]
    assert french_events == ["french-only-event"]
    assert stations["radiotedu-en"].database_file != stations["radiotedu-fr"].database_file


def test_connect_rejects_cross_station_database_path_before_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stations = contexts(tmp_path)
    english = stations["radiotedu-en"]
    french = stations["radiotedu-fr"]
    expected_english_database = english.settings.path(english.profile.runtime.database).resolve()
    french_database = french.database_file
    english.settings.database_path = str(french_database)
    opened: list[object] = []

    def forbidden_sqlite_connect(*args, **kwargs):
        opened.append((args, kwargs))
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(database_module.sqlite3, "connect", forbidden_sqlite_connect)

    with pytest.raises(ValueError, match="database path mismatch"):
        with connect(english):
            pass

    assert opened == []
    assert not expected_english_database.exists()
    assert not french_database.exists()


def test_connect_rejects_profile_database_escape_before_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    context = contexts(tmp_path)["radiotedu-en"]
    escaped_database = tmp_path / "outside.db"
    escaped_profile = replace(
        context.profile,
        runtime=replace(context.profile.runtime, database=str(escaped_database)),
    )
    escaped_context = build_station_context(context.settings, escaped_profile)
    opened: list[object] = []

    def forbidden_sqlite_connect(*args, **kwargs):
        opened.append((args, kwargs))
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(database_module.sqlite3, "connect", forbidden_sqlite_connect)

    with pytest.raises(ValueError, match="escape"):
        with connect(escaped_context):
            pass

    assert opened == []
    assert not escaped_database.exists()


def test_connect_opens_the_same_database_path_snapshot_that_was_validated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stations = contexts(tmp_path)
    english = stations["radiotedu-en"]
    validated_database = english.settings.path(english.profile.runtime.database).resolve()
    foreign_database = stations["radiotedu-fr"].database_file
    database_file = PropertyMock(side_effect=[validated_database, foreign_database])
    monkeypatch.setattr(Settings, "database_file", database_file)
    opened: list[Path] = []

    class RecordingConnection:
        row_factory = None

        def execute(self, statement: str):
            assert statement == "pragma foreign_keys = on"

        def close(self) -> None:
            pass

    def recording_sqlite_connect(path):
        opened.append(path)
        return RecordingConnection()

    monkeypatch.setattr(database_module.sqlite3, "connect", recording_sqlite_connect)

    with connect(english):
        pass

    assert database_file.call_count == 1
    assert opened == [validated_database]


def test_database_path_normalization_follows_platform_case_rules(tmp_path: Path) -> None:
    upper_case_path = tmp_path / "Station" / "radio.db"
    lower_case_path = tmp_path / "station" / "radio.db"
    platform_aliases_paths = os.path.normcase(str(upper_case_path.resolve())) == os.path.normcase(
        str(lower_case_path.resolve())
    )

    normalized_paths_are_equal = database_module._casefolded_resolved_path(
        upper_case_path
    ) == database_module._casefolded_resolved_path(lower_case_path)

    assert normalized_paths_are_equal is platform_aliases_paths


def test_connect_closes_connection_when_setup_fails(monkeypatch) -> None:
    class SetupFailingConnection:
        row_factory = None
        closed = False

        def execute(self, statement: str):
            assert statement == "pragma foreign_keys = on"
            raise RuntimeError("pragma setup failed")

        def close(self) -> None:
            self.closed = True

    connection = SetupFailingConnection()
    monkeypatch.setattr(database_module.sqlite3, "connect", lambda path: connection)

    with pytest.raises(RuntimeError, match="pragma setup failed"):
        with connect(Settings(database_path="ignored.db")):
            pass

    assert connection.closed is True


def test_station_channel_seed_uses_profile_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stations = contexts(tmp_path)
    rows: dict[str, dict] = {}
    for station_id, context in stations.items():
        init_db(context)
        with connect(context) as conn:
            row = conn.execute(
                "select id, name, description from channels where id=?",
                (DATABASE_CHANNEL_ID,),
            ).fetchone()
        assert row is not None
        rows[station_id] = dict(row)

    assert rows["radiotedu-en"] == {
        "id": DATABASE_CHANNEL_ID,
        "name": "RadioTEDU",
        "description": "Local AI radio running on your machine.",
    }
    assert rows["radiotedu-fr"] == {
        "id": DATABASE_CHANNEL_ID,
        "name": "RadioTEDU Français",
        "description": "Radio IA locale en français diffusée depuis votre ordinateur.",
    }


def test_scheduler_reads_only_the_selected_station_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stations = contexts(tmp_path)
    for context in stations.values():
        init_db(context)

    with connect(stations["radiotedu-en"]) as conn:
        conn.execute(
            "update programs set name=? where id=? and channel_id=?",
            ("English schedule", "morning_signal", DATABASE_CHANNEL_ID),
        )
        conn.commit()

    monday_morning = RealDateTime(2026, 7, 6, 7, 0)
    assert current_program(stations["radiotedu-en"], now=monday_morning)["name"] == "English schedule"
    assert current_program(stations["radiotedu-fr"], now=monday_morning)["name"] != "English schedule"
    assert next_programs(stations["radiotedu-en"], limit=1)[0]["name"] == "English schedule"
    assert next_programs(stations["radiotedu-fr"], limit=1)[0]["name"] != "English schedule"


def test_scheduler_uses_station_timezone_for_implicit_now(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    context = contexts(tmp_path)["radiotedu-en"]
    init_db(context)

    class RecordingDateTime:
        observed_timezone = None

        @classmethod
        def now(cls, timezone=None):
            cls.observed_timezone = timezone
            return RealDateTime(2026, 7, 6, 7, 0, tzinfo=timezone)

    monkeypatch.setattr(scheduler_module, "datetime", RecordingDateTime)

    assert current_program(context)["id"] == "morning_signal"
    assert str(RecordingDateTime.observed_timezone) == "Europe/Istanbul"


def test_direct_settings_database_and_scheduler_behavior_is_preserved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        database_path=str(tmp_path / "legacy" / "radio.db"),
        music_dir=str(tmp_path / "legacy" / "music"),
        static_dir=str(tmp_path / "legacy" / "static"),
    )

    init_db(settings)
    with connect(settings) as conn:
        channel = conn.execute(
            "select id, name, description from channels where id=?",
            (DATABASE_CHANNEL_ID,),
        ).fetchone()

    assert dict(channel) == {
        "id": DATABASE_CHANNEL_ID,
        "name": "RadioTEDU",
        "description": "Local AI radio running on your machine.",
    }
    assert current_program(settings, now=RealDateTime(2026, 7, 6, 7, 0))["id"] == "morning_signal"
    assert next_programs(settings, limit=1)[0]["id"] == "morning_signal"


def test_agent_and_orchestrator_retain_their_station_contexts(tmp_path: Path, monkeypatch) -> None:
    from backend import orchestrator as orchestrator_module
    from backend import radio_agent as radio_agent_module

    class StubPlayback:
        def __init__(self, settings):
            self.settings = settings

    class StubPusher:
        def __init__(self, settings, agent):
            self.settings = settings
            self.agent = agent

    initialized: list[StationContext] = []
    monkeypatch.setattr(radio_agent_module, "PlaybackController", StubPlayback)
    monkeypatch.setattr(radio_agent_module, "build_tts_provider", lambda settings: object())
    monkeypatch.setattr(radio_agent_module, "init_db", initialized.append)
    monkeypatch.setattr(orchestrator_module, "PublicSnapshotPusher", StubPusher)
    stations = contexts(tmp_path)

    agents = {
        station_id: radio_agent_module.RadioAgent(context)
        for station_id, context in stations.items()
    }
    orchestrators = {
        station_id: orchestrator_module.AutonomousOrchestrator(stations[station_id], agent)
        for station_id, agent in agents.items()
    }

    assert initialized == list(stations.values())
    for station_id, context in stations.items():
        agent = agents[station_id]
        orchestrator = orchestrators[station_id]
        assert agent.context is context
        assert agent.settings is context.settings
        assert agent._database_runtime is context
        assert agent.playback.settings is context.settings
        assert orchestrator.context is context
        assert orchestrator.settings is context.settings
        assert orchestrator._database_runtime is context
        assert orchestrator.agent is agent
        assert orchestrator.public_pusher.settings is context.settings
    assert agents["radiotedu-en"].context.profile.station_id == "radiotedu-en"
    assert orchestrators["radiotedu-fr"].context.profile.station_id == "radiotedu-fr"
    assert orchestrators["radiotedu-en"]._thread_name != orchestrators["radiotedu-fr"]._thread_name


def test_agent_and_orchestrator_database_and_schedule_calls_use_injected_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend import orchestrator as orchestrator_module
    from backend import radio_agent as radio_agent_module

    class StubPlayback:
        def __init__(self, settings):
            self.settings = settings

        def add(self, item) -> None:
            self.item = item

    class StubTTS:
        provider_name = "stub"

        def synthesize(self, text, output_path, voice=None):
            return output_path

    class StubPusher:
        def __init__(self, settings, agent):
            self.settings = settings
            self.agent = agent

    monkeypatch.chdir(tmp_path)
    station = contexts(tmp_path)["radiotedu-fr"]
    monkeypatch.setattr(radio_agent_module, "PlaybackController", StubPlayback)
    monkeypatch.setattr(radio_agent_module, "build_tts_provider", lambda settings: StubTTS())
    monkeypatch.setattr(orchestrator_module, "PublicSnapshotPusher", StubPusher)
    agent_connect = radio_agent_module.connect
    orchestrator_connect = orchestrator_module.connect
    agent_connect_calls: list[StationContext] = []
    orchestrator_connect_calls: list[StationContext] = []
    schedule_calls: list[StationContext] = []

    def recording_agent_connect(runtime):
        agent_connect_calls.append(runtime)
        return agent_connect(runtime)

    def recording_orchestrator_connect(runtime):
        orchestrator_connect_calls.append(runtime)
        return orchestrator_connect(runtime)

    def recording_current_program(runtime):
        schedule_calls.append(runtime)
        return {"id": "morning_signal", "name": "Morning Signal"}

    monkeypatch.setattr(radio_agent_module, "connect", recording_agent_connect)
    monkeypatch.setattr(radio_agent_module, "current_program", recording_current_program)
    monkeypatch.setattr(orchestrator_module, "connect", recording_orchestrator_connect)

    agent = radio_agent_module.RadioAgent(station)
    agent.queue_listener_reply("Bonjour", "test")
    orchestrator = orchestrator_module.AutonomousOrchestrator(station, agent)
    orchestrator.status()

    assert schedule_calls == [station]
    assert agent_connect_calls and all(runtime is station for runtime in agent_connect_calls)
    assert orchestrator_connect_calls and all(runtime is station for runtime in orchestrator_connect_calls)


def test_direct_settings_keep_a_narrow_legacy_database_and_scheduler_runtime(tmp_path: Path, monkeypatch) -> None:
    from backend import orchestrator as orchestrator_module
    from backend import radio_agent as radio_agent_module

    class StubPlayback:
        def __init__(self, settings):
            self.settings = settings

    class StubTTS:
        def synthesize(self, text, output_path, voice=None):
            return output_path

    class StubPusher:
        def __init__(self, settings, agent):
            self.settings = settings
            self.agent = agent

    class StubResult:
        def __init__(self, row=None):
            self.row = row

        def fetchone(self):
            return self.row

    class StubConnection:
        def execute(self, sql, parameters=()):
            return StubResult((0,) if "count(*)" in sql else None)

        def commit(self) -> None:
            pass

    class StubConnect:
        def __enter__(self):
            return StubConnection()

        def __exit__(self, exc_type, exc, traceback):
            return False

    settings = Settings(
        database_path=str(tmp_path / "legacy" / "radio.db"),
        music_dir=str(tmp_path / "legacy" / "music"),
        static_dir=str(tmp_path / "legacy" / "static"),
    )
    initialized = []
    agent_connect_calls = []
    orchestrator_connect_calls = []
    schedule_calls = []
    monkeypatch.setattr(radio_agent_module, "PlaybackController", StubPlayback)
    monkeypatch.setattr(radio_agent_module, "build_tts_provider", lambda runtime: StubTTS())
    monkeypatch.setattr(radio_agent_module, "init_db", initialized.append)
    monkeypatch.setattr(
        radio_agent_module,
        "connect",
        lambda runtime: agent_connect_calls.append(runtime) or StubConnect(),
    )
    monkeypatch.setattr(
        radio_agent_module,
        "current_program",
        lambda runtime: schedule_calls.append(runtime) or {"id": "morning_signal", "name": "Morning Signal"},
    )
    monkeypatch.setattr(orchestrator_module, "PublicSnapshotPusher", StubPusher)
    monkeypatch.setattr(
        orchestrator_module,
        "connect",
        lambda runtime: orchestrator_connect_calls.append(runtime) or StubConnect(),
    )

    agent = radio_agent_module.RadioAgent(settings)
    orchestrator = orchestrator_module.AutonomousOrchestrator(settings, agent)
    agent_context = agent.context
    orchestrator_context = orchestrator.context
    settings.station_id = "radiotedu-fr"
    settings.database_path = str(tmp_path / "mutated" / "radio.db")
    settings.music_dir = str(tmp_path / "mutated" / "music")

    agent._narrate("Legacy context", "morning_signal")
    orchestrator.stop_background()

    assert agent.context is agent_context
    assert orchestrator.context is orchestrator_context
    assert agent.context.profile.station_id == "radiotedu-en"
    assert orchestrator.context.profile.station_id == "radiotedu-en"
    assert agent.settings.station_id == "radiotedu-en"
    assert orchestrator.settings.station_id == "radiotedu-en"
    assert agent.settings.database_path.endswith("legacy\\radio.db") or agent.settings.database_path.endswith("legacy/radio.db")
    assert orchestrator.settings.database_path.endswith("legacy\\radio.db") or orchestrator.settings.database_path.endswith("legacy/radio.db")
    assert agent.settings is not settings
    assert orchestrator.settings is not settings
    assert initialized == [agent.settings]
    assert agent._database_runtime is agent.settings
    assert orchestrator._database_runtime is orchestrator.settings
    assert schedule_calls == [agent.settings]
    assert agent_connect_calls == [agent.settings]
    assert orchestrator_connect_calls == [orchestrator.settings]


def _agent_without_constructor(context: StationContext):
    from backend.radio_agent import RadioAgent

    agent = object.__new__(RadioAgent)
    agent.context = context
    agent.settings = context.settings
    agent._database_runtime = context
    return agent


def _assert_orchestrator_pair_rejected_before_side_effects(runtime, agent, monkeypatch) -> None:
    from backend import orchestrator as orchestrator_module

    side_effects = []

    class StubEvent:
        def __init__(self):
            side_effects.append("thread-event")

    class StubPusher:
        def __init__(self, settings, selected_agent):
            side_effects.append("public-pusher")

    def forbidden_database(*args, **kwargs):
        side_effects.append("database")
        raise AssertionError("database work must not start for a mismatched pair")

    monkeypatch.setattr(orchestrator_module.threading, "Event", StubEvent)
    monkeypatch.setattr(orchestrator_module, "PublicSnapshotPusher", StubPusher)
    monkeypatch.setattr(orchestrator_module, "connect", forbidden_database)
    monkeypatch.setattr(orchestrator_module, "init_db", forbidden_database)

    with pytest.raises(ValueError, match="station runtime and agent context mismatch"):
        orchestrator_module.AutonomousOrchestrator(runtime, agent)

    assert side_effects == []


def test_orchestrator_rejects_french_context_with_english_agent_before_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stations = contexts(tmp_path)
    _assert_orchestrator_pair_rejected_before_side_effects(
        stations["radiotedu-fr"],
        _agent_without_constructor(stations["radiotedu-en"]),
        monkeypatch,
    )


def test_orchestrator_rejects_equivalent_but_different_explicit_context_before_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = contexts(tmp_path)["radiotedu-fr"]
    equivalent = build_station_context(context.settings, context.profile)
    assert equivalent == context
    assert equivalent is not context

    _assert_orchestrator_pair_rejected_before_side_effects(
        context,
        _agent_without_constructor(equivalent),
        monkeypatch,
    )


def test_legacy_orchestrator_rejects_explicit_french_agent_before_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=str(tmp_path / "legacy" / "radio.db"),
        music_dir=str(tmp_path / "legacy" / "music"),
        static_dir=str(tmp_path / "legacy" / "static"),
    )
    french = contexts(tmp_path)["radiotedu-fr"]

    _assert_orchestrator_pair_rejected_before_side_effects(
        settings,
        _agent_without_constructor(french),
        monkeypatch,
    )


def test_legacy_orchestrator_rejects_english_agent_with_different_database_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.stations.context import coerce_station_context

    orchestrator_settings = Settings(
        database_path=str(tmp_path / "orchestrator" / "radio.db"),
        music_dir=str(tmp_path / "orchestrator" / "music"),
        static_dir=str(tmp_path / "orchestrator" / "static"),
    )
    agent_settings = Settings(
        database_path=str(tmp_path / "agent" / "radio.db"),
        music_dir=str(tmp_path / "agent" / "music"),
        static_dir=str(tmp_path / "agent" / "static"),
    )

    _assert_orchestrator_pair_rejected_before_side_effects(
        orchestrator_settings,
        _agent_without_constructor(coerce_station_context(agent_settings)),
        monkeypatch,
    )
