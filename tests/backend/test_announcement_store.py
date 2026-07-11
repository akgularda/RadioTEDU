from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.announcements.models import AnnouncementJob, AnnouncementState
from backend.announcements.store import (
    AnnouncementJobStore,
    InvalidAnnouncementTransition,
)
from backend.database import apply_migrations


NOW = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)


def make_job(
    *,
    station_id: str = "radiotedu-en",
    planner_key: str = "artist-fact-1200",
    deadline: datetime = NOW + timedelta(minutes=15),
) -> AnnouncementJob:
    return AnnouncementJob(
        station_id=station_id,
        language="en" if station_id.endswith("en") else "fr",
        kind="artist-fact",
        planner_key=planner_key,
        planned_airtime=NOW + timedelta(minutes=10),
        deadline=deadline,
        freshness_class="standard",
        priority=50,
    )


def make_store() -> AnnouncementJobStore:
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    apply_migrations(conn)
    return AnnouncementJobStore(conn)


def test_create_is_station_scoped_and_idempotent_by_planner_key() -> None:
    store = make_store()
    english = store.create(make_job())
    duplicate = store.create(make_job())
    french = store.create(make_job(station_id="radiotedu-fr"))

    assert duplicate.job_id == english.job_id
    assert french.job_id != english.job_id
    assert store.get("radiotedu-en", english.job_id) == english
    assert store.get("radiotedu-fr", english.job_id) is None
    assert store.list_for_station("radiotedu-en") == [english]
    assert store.list_for_station("radiotedu-fr") == [french]


def test_transition_is_atomic_records_events_and_is_idempotent() -> None:
    store = make_store()
    job = store.create(make_job())

    text_ready = store.transition(
        "radiotedu-en", job.job_id, AnnouncementState.TEXT_READY, actor="planner"
    )
    same_state = store.transition(
        "radiotedu-en", job.job_id, AnnouncementState.TEXT_READY, actor="retry"
    )
    synthesizing = store.transition(
        "radiotedu-en", job.job_id, AnnouncementState.SYNTHESIZING, actor="tts"
    )
    audio_ready = store.transition(
        "radiotedu-en", job.job_id, AnnouncementState.AUDIO_READY, actor="tts"
    )
    consumed = store.transition(
        "radiotedu-en", job.job_id, AnnouncementState.CONSUMED, actor="playout"
    )

    assert text_ready.state is AnnouncementState.TEXT_READY
    assert same_state == text_ready
    assert synthesizing.state is AnnouncementState.SYNTHESIZING
    assert audio_ready.state is AnnouncementState.AUDIO_READY
    assert consumed.state is AnnouncementState.CONSUMED
    assert [
        (event.from_state, event.to_state)
        for event in store.events("radiotedu-en", job.job_id)
    ] == [
        (AnnouncementState.PLANNED, AnnouncementState.TEXT_READY),
        (AnnouncementState.TEXT_READY, AnnouncementState.SYNTHESIZING),
        (AnnouncementState.SYNTHESIZING, AnnouncementState.AUDIO_READY),
        (AnnouncementState.AUDIO_READY, AnnouncementState.CONSUMED),
    ]

    with pytest.raises(InvalidAnnouncementTransition):
        store.transition(
            "radiotedu-en", job.job_id, AnnouncementState.FAILED, actor="late-retry"
        )

    assert store.get("radiotedu-en", job.job_id) == consumed
    assert len(store.events("radiotedu-en", job.job_id)) == 4


def test_expire_due_preserves_other_station_and_terminal_paths() -> None:
    store = make_store()
    stale_english = store.create(
        make_job(planner_key="stale-en", deadline=NOW - timedelta(seconds=1))
    )
    stale_french = store.create(
        make_job(
            station_id="radiotedu-fr",
            planner_key="stale-fr",
            deadline=NOW - timedelta(seconds=1),
        )
    )
    future_english = store.create(make_job(planner_key="future-en"))

    expired = store.expire_due("radiotedu-en", NOW, actor="freshness")
    skipped = store.transition(
        "radiotedu-en", future_english.job_id, AnnouncementState.SKIPPED, actor="planner"
    )
    assert store.get("radiotedu-fr", stale_french.job_id).state is AnnouncementState.PLANNED
    failed = store.transition(
        "radiotedu-fr", stale_french.job_id, AnnouncementState.FAILED, actor="tts"
    )

    assert [job.job_id for job in expired] == [stale_english.job_id]
    assert expired[0].state is AnnouncementState.EXPIRED
    assert skipped.state is AnnouncementState.SKIPPED
    assert failed.state is AnnouncementState.FAILED
