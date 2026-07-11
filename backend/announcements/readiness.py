"""Station-local rolling-horizon readiness decisions."""

from __future__ import annotations

from dataclasses import dataclass

from .freshness import DYNAMIC_SPEECH_MINUTES, speech_target_minutes


@dataclass(frozen=True, slots=True)
class HorizonStatus:
    """The recoverable announcement coverage state for one station."""

    station_id: str
    ready_minutes: int
    planned_minutes: int
    failed_minutes: int
    level: str
    can_start: bool
    target_minutes: int = 180

    @property
    def music_only(self) -> bool:
        return self.level == "music-only"


def readiness_status(
    station_id: str,
    *,
    ready_minutes: int,
    planned_minutes: int,
    failed_minutes: int,
    cold_start: bool = False,
) -> HorizonStatus:
    """Classify station readiness without considering any other station's state."""

    _validate_minutes(ready_minutes, planned_minutes, failed_minutes)
    target_minutes = speech_target_minutes(cold_start=cold_start)
    return HorizonStatus(
        station_id=station_id,
        ready_minutes=ready_minutes,
        planned_minutes=planned_minutes,
        failed_minutes=failed_minutes,
        level=_readiness_level(ready_minutes, target_minutes),
        can_start=ready_minutes >= target_minutes,
        target_minutes=target_minutes,
    )


def _readiness_level(ready_minutes: int, target_minutes: int) -> str:
    if ready_minutes < DYNAMIC_SPEECH_MINUTES:
        return "music-only"
    if ready_minutes < 60:
        return "emergency"
    if ready_minutes < target_minutes:
        return "low"
    return "ready"


def _validate_minutes(*minutes: int) -> None:
    if any(value < 0 for value in minutes):
        raise ValueError("horizon minutes must be non-negative")
