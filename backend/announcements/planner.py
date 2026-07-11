"""Durable, station-scoped announcement horizon planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable

from .freshness import generation_deadline
from .models import AnnouncementJob, AnnouncementState


_TERMINAL_STATES = {
    AnnouncementState.CONSUMED,
    AnnouncementState.EXPIRED,
    AnnouncementState.SKIPPED,
    AnnouncementState.FAILED,
}


@dataclass(frozen=True, slots=True)
class HorizonEntry:
    """One durable scheduled announcement and its expected spoken coverage."""

    job: AnnouncementJob
    duration_minutes: int

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")


@dataclass(frozen=True, slots=True)
class HorizonCoverage:
    station_id: str
    ready_minutes: int
    planned_minutes: int
    failed_minutes: int


@dataclass(frozen=True, slots=True)
class GenerationInput:
    """A station-local job ordered by the time it must finish generation."""

    job: AnnouncementJob
    duration_minutes: int
    deadline: datetime


class AnnouncementHorizon:
    """Persist and recover only one station's future announcement horizon."""

    def __init__(self, root: Path | str, station_id: str) -> None:
        if not station_id.strip():
            raise ValueError("station_id must not be empty")
        self.station_id = station_id
        self.path = Path(root) / station_id / "announcement-horizon.json"

    def entries(self) -> tuple[HorizonEntry, ...]:
        if not self.path.exists():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("station_id") != self.station_id:
            raise ValueError("horizon state belongs to another station")
        entries = tuple(_entry_from_dict(item) for item in payload.get("entries", ()))
        if any(entry.job.station_id != self.station_id for entry in entries):
            raise ValueError("horizon entry belongs to another station")
        return entries

    def upsert(self, job: AnnouncementJob, *, duration_minutes: int) -> HorizonEntry:
        if job.station_id != self.station_id:
            raise ValueError("cannot add another station's announcement")
        entry = HorizonEntry(job=job, duration_minutes=duration_minutes)
        existing = {item.job.planner_key: item for item in self.entries()}
        existing[job.planner_key] = entry
        self._persist(existing.values())
        return entry

    def coverage(self, *, now: datetime) -> HorizonCoverage:
        ready = planned = failed = 0
        for entry in self.entries():
            job = entry.job
            if job.planned_airtime <= now:
                continue
            if job.state is AnnouncementState.AUDIO_READY:
                ready += entry.duration_minutes
                planned += entry.duration_minutes
            elif job.state is AnnouncementState.FAILED:
                failed += entry.duration_minutes
            elif job.state not in _TERMINAL_STATES:
                planned += entry.duration_minutes
        return HorizonCoverage(
            station_id=self.station_id,
            ready_minutes=ready,
            planned_minutes=planned,
            failed_minutes=failed,
        )

    def generation_inputs(self, *, now: datetime) -> tuple[GenerationInput, ...]:
        """Return only this station's viable generation jobs, deadline first."""

        inputs = []
        for entry in self.entries():
            job = entry.job
            deadline = generation_deadline(job)
            if job.state not in {AnnouncementState.PLANNED, AnnouncementState.TEXT_READY}:
                continue
            if job.planned_airtime <= now or deadline <= now:
                continue
            inputs.append(
                GenerationInput(
                    job=job,
                    duration_minutes=entry.duration_minutes,
                    deadline=deadline,
                )
            )
        return tuple(
            sorted(
                inputs,
                key=lambda item: (
                    item.deadline,
                    -item.job.priority,
                    item.job.planned_airtime,
                    item.job.planner_key,
                ),
            )
        )

    def _persist(self, entries: Iterable[HorizonEntry]) -> None:
        ordered = sorted(entries, key=lambda item: (item.job.planned_airtime, item.job.planner_key))
        payload = {
            "station_id": self.station_id,
            "entries": [_entry_to_dict(entry) for entry in ordered],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(self.path)


HorizonPlanner = AnnouncementHorizon


def _entry_to_dict(entry: HorizonEntry) -> dict[str, object]:
    job = entry.job
    return {
        "duration_minutes": entry.duration_minutes,
        "job": {
            "station_id": job.station_id,
            "language": job.language,
            "kind": job.kind,
            "planner_key": job.planner_key,
            "planned_airtime": job.planned_airtime.isoformat(),
            "deadline": job.deadline.isoformat(),
            "freshness_class": job.freshness_class,
            "priority": job.priority,
            "job_id": job.job_id,
            "state": job.state.value,
            "text_state": job.text_state,
            "audio_state": job.audio_state,
            "attempts": job.attempts,
            "text_hash": job.text_hash,
            "audio_path": job.audio_path,
            "audio_checksum": job.audio_checksum,
            "lease_expires_at": _datetime_to_text(job.lease_expires_at),
            "failure_reason": job.failure_reason,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        },
    }


def _entry_from_dict(payload: dict[str, object]) -> HorizonEntry:
    job_data = dict(payload["job"])
    for key in ("planned_airtime", "deadline", "created_at", "updated_at", "lease_expires_at"):
        value = job_data[key]
        job_data[key] = datetime.fromisoformat(value) if value is not None else None
    job_data["state"] = AnnouncementState(job_data["state"])
    return HorizonEntry(
        job=AnnouncementJob(**job_data),
        duration_minutes=int(payload["duration_minutes"]),
    )


def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
