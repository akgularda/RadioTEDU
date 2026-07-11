"""Deadline-and-deficit dispatch for station-isolated generation work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from .models import AnnouncementJob, AnnouncementState
from .planner import GenerationInput


_HEAVY_STATES = frozenset({AnnouncementState.PLANNED, AnnouncementState.TEXT_READY})
_STATIC_KINDS = frozenset({"imaging", "static-imaging", "jingle", "sweeper"})
_FAIRNESS_WINDOW = 2
_URGENT_SLACK = timedelta(seconds=90)


@dataclass(frozen=True, slots=True)
class StationDispatchTarget:
    """One station's context, agent, and current ready-speech coverage."""

    context: Any
    agent: Any
    speech_ready_minutes: int
    last_model_turn_at: datetime | None = None

    def __post_init__(self) -> None:
        profile = getattr(self.context, "profile", None)
        agent_context = getattr(self.agent, "context", None)
        if not getattr(profile, "station_id", "") or not getattr(profile, "language", ""):
            raise ValueError("station context must provide a station id and language")
        if agent_context is not self.context:
            raise ValueError("station context and agent mismatch")
        if self.speech_ready_minutes < 0:
            raise ValueError("speech_ready_minutes must not be negative")

    @property
    def station_id(self) -> str:
        return self.context.profile.station_id

    @property
    def language(self) -> str:
        return self.context.profile.language

    @property
    def deficit_minutes(self) -> int:
        return max(0, 180 - self.speech_ready_minutes)

    def accepts(self, job: AnnouncementJob) -> bool:
        return job.station_id == self.station_id and job.language.casefold() == self.language.casefold()

    def enqueue(self, job: AnnouncementJob, *, dispatch_rule: str, dispatch_inputs: dict[str, object]) -> dict:
        if not self.accepts(job):
            raise ValueError("announcement job does not belong to the dispatch target")
        return self.agent.enqueue_announcement_job(
            job,
            dispatch_rule=dispatch_rule,
            dispatch_inputs=dispatch_inputs,
        )


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    """An auditable selection that has not yet started model work."""

    input: GenerationInput
    target: StationDispatchTarget
    rule: str
    deadline_slack: timedelta
    deficit_minutes: int

    @property
    def job(self) -> AnnouncementJob:
        return self.input.job

    @property
    def event_inputs(self) -> dict[str, object]:
        return {
            "station_id": self.target.station_id,
            "job_id": self.job.job_id,
            "deadline_slack_seconds": int(self.deadline_slack.total_seconds()),
            "deficit_minutes": self.deficit_minutes,
            "speech_ready_minutes": self.target.speech_ready_minutes,
        }


class BilingualDispatcher:
    """Select work fairly without making model work part of the playout path."""

    def select(
        self,
        inputs: Iterable[GenerationInput],
        targets: Iterable[StationDispatchTarget],
        *,
        now: datetime,
        completed_heavy_stations: Sequence[str] = (),
    ) -> DispatchDecision | None:
        """Return the next viable station-local job, or ``None`` when none can run."""

        target_list = tuple(targets)
        target_by_station = {target.station_id: target for target in target_list}
        if len(target_by_station) != len(target_list):
            raise ValueError("only one dispatch target is allowed per station")

        candidates = [
            (input, target_by_station[input.job.station_id], input.deadline - now)
            for input in inputs
            if input.job.station_id in target_by_station
            and self._runnable(input, target_by_station[input.job.station_id], now)
        ]
        if not candidates:
            return None

        recent_stations = tuple(completed_heavy_stations[-_FAIRNESS_WINDOW:])
        missing_stations = set(target_by_station).difference(recent_stations)
        urgent_elsewhere = any(
            slack < _URGENT_SLACK and station_id not in missing_stations
            for input, _, slack in candidates
            for station_id in (input.job.station_id,)
        )
        if len(missing_stations) == 1 and not urgent_elsewhere:
            selected_station = next(iter(missing_stations))
            fairness_candidates = [candidate for candidate in candidates if candidate[0].job.station_id == selected_station]
            if fairness_candidates:
                input, target, slack = self._rank(fairness_candidates)[0]
                return DispatchDecision(input, target, "bounded-fairness", slack, target.deficit_minutes)

        input, target, slack = self._rank(candidates)[0]
        return DispatchDecision(input, target, "deadline-slack", slack, target.deficit_minutes)

    def dispatch(self, decision: DispatchDecision) -> dict:
        """Queue selected work only; the agent never synthesizes it inline here."""

        return decision.target.enqueue(
            decision.job,
            dispatch_rule=decision.rule,
            dispatch_inputs=decision.event_inputs,
        )

    @staticmethod
    def _runnable(input: GenerationInput, target: StationDispatchTarget, now: datetime) -> bool:
        job = input.job
        return (
            target.accepts(job)
            and job.state in _HEAVY_STATES
            and job.planned_airtime > now
            and input.deadline > now
            and job.freshness_class.casefold() != "static"
            and job.kind.casefold() not in _STATIC_KINDS
        )

    @staticmethod
    def _rank(
        candidates: Iterable[tuple[GenerationInput, StationDispatchTarget, timedelta]],
    ) -> list[tuple[GenerationInput, StationDispatchTarget, timedelta]]:
        oldest_possible_turn = datetime.min.replace(tzinfo=timezone.utc)
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate[2],
                -candidate[1].deficit_minutes,
                candidate[1].last_model_turn_at or oldest_possible_turn,
                candidate[0].job.priority,
                candidate[1].station_id,
                candidate[0].job.job_id,
            ),
        )
