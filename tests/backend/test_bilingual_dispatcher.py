from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from backend.announcements.dispatcher import BilingualDispatcher, StationDispatchTarget
from backend.announcements.models import AnnouncementJob
from backend.announcements.planner import GenerationInput


NOW = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Profile:
    station_id: str
    language: str


@dataclass(frozen=True)
class _Context:
    profile: _Profile


class _Agent:
    def __init__(self, context: _Context) -> None:
        self.context = context
        self.calls: list[tuple[AnnouncementJob, str, dict[str, object]]] = []

    def enqueue_announcement_job(
        self,
        job: AnnouncementJob,
        *,
        dispatch_rule: str,
        dispatch_inputs: dict[str, object],
    ) -> dict:
        self.calls.append((job, dispatch_rule, dispatch_inputs))
        return {"queued": True, "job_id": job.job_id}


def _target(station_id: str, language: str, ready_minutes: int) -> tuple[StationDispatchTarget, _Agent]:
    context = _Context(_Profile(station_id, language))
    agent = _Agent(context)
    return (
        StationDispatchTarget(
            context=context,
            agent=agent,
            speech_ready_minutes=ready_minutes,
        ),
        agent,
    )


def _generation_input(
    station_id: str,
    language: str,
    job_id: str,
    *,
    deadline_in: timedelta,
    airtime_in: timedelta = timedelta(minutes=30),
    priority: int = 50,
) -> GenerationInput:
    job = AnnouncementJob(
        station_id=station_id,
        language=language,
        kind="news",
        planner_key=job_id,
        job_id=job_id,
        planned_airtime=NOW + airtime_in,
        deadline=NOW + deadline_in,
        freshness_class="dynamic",
        priority=priority,
    )
    return GenerationInput(job=job, duration_minutes=2, deadline=job.deadline)


def test_missing_station_turn_wins_before_deadline_deficit_and_priority() -> None:
    english, _ = _target("radiotedu-en", "en", ready_minutes=170)
    french, _ = _target("radiotedu-fr", "fr", ready_minutes=20)
    dispatcher = BilingualDispatcher()

    decision = dispatcher.select(
        [
            _generation_input("radiotedu-en", "en", "en-sooner", deadline_in=timedelta(minutes=2)),
            _generation_input("radiotedu-fr", "fr", "fr-deficit", deadline_in=timedelta(minutes=3)),
        ],
        [english, french],
        now=NOW,
        completed_heavy_stations=("radiotedu-en", "radiotedu-en"),
    )

    assert decision is not None
    assert decision.job.job_id == "fr-deficit"
    assert decision.rule == "bounded-fairness"
    assert decision.deficit_minutes == 160


def test_urgent_deadline_overrides_fairness_and_queues_only_matching_agent() -> None:
    english, english_agent = _target("radiotedu-en", "en", ready_minutes=170)
    french, french_agent = _target("radiotedu-fr", "fr", ready_minutes=20)
    dispatcher = BilingualDispatcher()

    decision = dispatcher.select(
        [
            _generation_input("radiotedu-en", "en", "en-urgent", deadline_in=timedelta(seconds=60)),
            _generation_input("radiotedu-fr", "fr", "fr-fair", deadline_in=timedelta(minutes=3)),
        ],
        [english, french],
        now=NOW,
        completed_heavy_stations=("radiotedu-en", "radiotedu-en"),
    )

    assert decision is not None
    assert decision.job.job_id == "en-urgent"
    assert decision.rule == "deadline-slack"
    assert dispatcher.dispatch(decision) == {"queued": True, "job_id": "en-urgent"}
    assert [job.job_id for job, _, _ in english_agent.calls] == ["en-urgent"]
    assert english_agent.calls[0][1:] == (
        "deadline-slack",
        {
            "station_id": "radiotedu-en",
            "job_id": "en-urgent",
            "deadline_slack_seconds": 60,
            "deficit_minutes": 10,
            "speech_ready_minutes": 170,
        },
    )
    assert french_agent.calls == []


def test_stale_jobs_are_never_dispatched_and_station_context_must_match_agent() -> None:
    english, _ = _target("radiotedu-en", "en", ready_minutes=0)
    stale = _generation_input(
        "radiotedu-en",
        "en",
        "stale",
        deadline_in=timedelta(minutes=1),
        airtime_in=timedelta(seconds=-1),
    )

    assert BilingualDispatcher().select([stale], [english], now=NOW) is None

    french_context = _Context(_Profile("radiotedu-fr", "fr"))
    english_agent = _Agent(_Context(_Profile("radiotedu-en", "en")))
    with pytest.raises(ValueError, match="station context and agent mismatch"):
        StationDispatchTarget(context=french_context, agent=english_agent, speech_ready_minutes=0)
