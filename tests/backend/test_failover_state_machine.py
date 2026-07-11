from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.runtime.failover import FailoverController, FailoverState
from backend.runtime.supervisor import RuntimeMode, StationSupervisor


BASE_TIME = datetime(2026, 7, 11, tzinfo=timezone.utc)


class SourceSwitch:
    """In-memory source switch that rejects listener-visible source overlap."""

    def __init__(self) -> None:
        self.primary_connected = True
        self.fallback_connected = False
        self.actions: list[str] = []

    def disconnect_primary(self) -> None:
        self.primary_connected = False
        self.actions.append("disconnect-primary")

    def enable_fallback(self) -> None:
        assert not self.primary_connected
        self.fallback_connected = True
        self.actions.append("enable-fallback")

    def disconnect_fallback(self) -> None:
        self.fallback_connected = False
        self.actions.append("disconnect-fallback")

    def enable_primary(self) -> None:
        assert not self.fallback_connected
        self.primary_connected = True
        self.actions.append("enable-primary")


def build_failover(station_id: str = "en") -> tuple[FailoverController, SourceSwitch]:
    source_switch = SourceSwitch()
    controller = FailoverController(
        station_id=station_id,
        disconnect_primary=source_switch.disconnect_primary,
        enable_fallback=source_switch.enable_fallback,
        disconnect_fallback=source_switch.disconnect_fallback,
        enable_primary=source_switch.enable_primary,
    )
    return controller, source_switch


def move_to_fallback(controller: FailoverController) -> None:
    controller.evaluate(BASE_TIME, primary_healthy=False, silence_seconds=1.0)
    status = controller.evaluate(
        BASE_TIME + timedelta(seconds=0.5),
        primary_healthy=False,
        silence_seconds=1.5,
    )
    assert status.state is FailoverState.FALLBACK


def test_silence_degrades_at_one_second_and_activates_fallback_by_one_point_five() -> None:
    controller, source_switch = build_failover()

    degraded = controller.evaluate(BASE_TIME, primary_healthy=True, silence_seconds=1.0)
    fallback = controller.evaluate(
        BASE_TIME + timedelta(seconds=0.5),
        primary_healthy=True,
        silence_seconds=1.5,
    )

    assert degraded.state is FailoverState.DEGRADED_PRIMARY
    assert fallback.state is FailoverState.FALLBACK
    assert fallback.active_source == "fallback"
    assert source_switch.actions == ["disconnect-primary", "enable-fallback"]
    assert not source_switch.primary_connected
    assert source_switch.fallback_connected


def test_primary_never_overlaps_fallback_when_recovery_releases_it() -> None:
    controller, source_switch = build_failover()
    move_to_fallback(controller)

    controller.evaluate(
        BASE_TIME + timedelta(seconds=1),
        primary_healthy=True,
        silence_seconds=0,
        recovery_healthy=True,
    )
    recovering = controller.evaluate(
        BASE_TIME + timedelta(seconds=61),
        primary_healthy=True,
        silence_seconds=0,
        recovery_healthy=True,
    )
    restored = controller.evaluate(
        BASE_TIME + timedelta(seconds=91),
        primary_healthy=True,
        silence_seconds=0,
        recovery_healthy=True,
    )

    assert recovering.state is FailoverState.RECOVERING
    assert restored.state is FailoverState.PRIMARY_RESTORED
    assert restored.active_source == "primary"
    assert source_switch.actions == [
        "disconnect-primary",
        "enable-fallback",
        "disconnect-fallback",
        "enable-primary",
    ]
    assert source_switch.primary_connected
    assert not source_switch.fallback_connected


def test_failover_recovery_failure_returns_to_fallback() -> None:
    controller, _ = build_failover()
    move_to_fallback(controller)

    controller.evaluate(
        BASE_TIME + timedelta(seconds=1),
        primary_healthy=True,
        silence_seconds=0,
        recovery_healthy=True,
    )
    controller.evaluate(
        BASE_TIME + timedelta(seconds=61),
        primary_healthy=True,
        silence_seconds=0,
        recovery_healthy=True,
    )
    fallback = controller.evaluate(
        BASE_TIME + timedelta(seconds=62),
        primary_healthy=False,
        silence_seconds=1.0,
        recovery_healthy=False,
    )

    assert fallback.state is FailoverState.FALLBACK
    assert fallback.active_source == "fallback"


def test_music_only_recovery_needs_three_qwen_probes_and_five_stable_samples() -> None:
    supervisor = StationSupervisor(station_id="en")

    music_only = supervisor.evaluate(
        qwen_healthy=False,
        speech_ready_minutes=0,
        normal_ready_minutes=0,
    )
    for _ in range(2):
        still_music_only = supervisor.evaluate(
            qwen_healthy=True,
            speech_ready_minutes=60,
            normal_ready_minutes=60,
        )
        assert still_music_only.mode is RuntimeMode.MUSIC_ONLY

    recovering = supervisor.evaluate(
        qwen_healthy=True,
        speech_ready_minutes=60,
        normal_ready_minutes=60,
    )
    for _ in range(4):
        still_recovering = supervisor.evaluate(
            qwen_healthy=True,
            speech_ready_minutes=60,
            normal_ready_minutes=60,
        )
        assert still_recovering.mode is RuntimeMode.RECOVERING

    live = supervisor.evaluate(
        qwen_healthy=True,
        speech_ready_minutes=60,
        normal_ready_minutes=60,
    )

    assert music_only.mode is RuntimeMode.MUSIC_ONLY
    assert recovering.mode is RuntimeMode.RECOVERING
    assert live.mode is RuntimeMode.LIVE


def test_station_supervisors_do_not_share_recovery_counters() -> None:
    en_supervisor = StationSupervisor(station_id="en")
    fr_supervisor = StationSupervisor(station_id="fr")
    for supervisor in (en_supervisor, fr_supervisor):
        supervisor.evaluate(qwen_healthy=False, speech_ready_minutes=0, normal_ready_minutes=0)

    for _ in range(3):
        en_status = en_supervisor.evaluate(
            qwen_healthy=True,
            speech_ready_minutes=60,
            normal_ready_minutes=60,
        )

    fr_status = fr_supervisor.evaluate(
        qwen_healthy=True,
        speech_ready_minutes=60,
        normal_ready_minutes=60,
    )

    assert en_status.mode is RuntimeMode.RECOVERING
    assert fr_status.mode is RuntimeMode.MUSIC_ONLY
