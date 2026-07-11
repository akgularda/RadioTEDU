"""Pure freshness and deadline decisions for announcement jobs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .models import AnnouncementJob, AnnouncementState


NORMAL_SPEECH_TARGET_MINUTES = 180
COLD_START_SPEECH_TARGET_MINUTES = 60
DYNAMIC_SPEECH_MINUTES = 10

_GENERATION_LEAD_MINUTES = {
    "news": 15,
    "weather": 10,
}


@dataclass(frozen=True)
class FreshnessDecision:
    """The typed job state to use at its scheduled playout point."""

    job: AnnouncementJob
    play_speech: bool
    music_continues: bool
    reason: str | None = None


def speech_target_minutes(*, cold_start: bool = False) -> int:
    """Return the required speech-ready coverage for the station mode."""

    return COLD_START_SPEECH_TARGET_MINUTES if cold_start else NORMAL_SPEECH_TARGET_MINUTES


def dynamic_speech_enabled(speech_ready_minutes: int) -> bool:
    """Dynamic speech must not be queued below its minimum ready coverage."""

    return speech_ready_minutes >= DYNAMIC_SPEECH_MINUTES


def generation_deadline(job: AnnouncementJob) -> datetime:
    """Return the final generation time for time-sensitive content."""

    lead_minutes = _GENERATION_LEAD_MINUTES.get(job.kind.casefold())
    if lead_minutes is None:
        return job.deadline
    return job.planned_airtime - timedelta(minutes=lead_minutes)


def apply_generation_deadline(job: AnnouncementJob) -> AnnouncementJob:
    """Return a typed job copy with its deterministic generation deadline."""

    return replace(job, deadline=generation_deadline(job))


def evaluate_job(job: AnnouncementJob, *, now: datetime) -> FreshnessDecision:
    """Skip stale or unavailable speech and leave music available to continue."""

    if job.state is not AnnouncementState.AUDIO_READY:
        return _skip(job, "missing-speech")
    if now >= job.planned_airtime:
        return _skip(job, "stale")
    return FreshnessDecision(
        job=job,
        play_speech=True,
        music_continues=False,
    )


def _skip(job: AnnouncementJob, reason: str) -> FreshnessDecision:
    return FreshnessDecision(
        job=replace(job, state=AnnouncementState.SKIPPED),
        play_speech=False,
        music_continues=True,
        reason=reason,
    )
