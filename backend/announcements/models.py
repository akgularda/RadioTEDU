"""Durable announcement-job contracts.

The state is intentionally a single, explicit value.  The text and audio
fields remain available to the later planner and dispatcher work orders, but
they are derived from that state by the store so callers cannot persist an
inconsistent combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class AnnouncementState(str, Enum):
    PLANNED = "planned"
    TEXT_READY = "text-ready"
    SYNTHESIZING = "synthesizing"
    AUDIO_READY = "audio-ready"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    SKIPPED = "skipped"
    FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AnnouncementJob:
    station_id: str
    language: str
    kind: str
    planner_key: str
    planned_airtime: datetime
    deadline: datetime
    freshness_class: str
    priority: int
    job_id: str = field(default_factory=lambda: str(uuid4()))
    state: AnnouncementState = AnnouncementState.PLANNED
    text_state: str = "pending"
    audio_state: str = "pending"
    attempts: int = 0
    text_hash: str | None = None
    audio_path: str | None = None
    audio_checksum: str | None = None
    lease_expires_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for name in ("station_id", "language", "kind", "planner_key", "freshness_class"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")


@dataclass(frozen=True)
class AnnouncementJobEvent:
    event_id: str
    job_id: str
    from_state: AnnouncementState
    to_state: AnnouncementState
    actor: str
    reason: str | None
    metadata: dict[str, object]
    occurred_at: datetime
