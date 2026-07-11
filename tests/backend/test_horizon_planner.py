from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.announcements.models import AnnouncementJob, AnnouncementState
from backend.announcements.planner import AnnouncementHorizon
from backend.announcements.readiness import readiness_status


NOW = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)


def _job(
    station_id: str,
    planner_key: str,
    *,
    state: AnnouncementState = AnnouncementState.AUDIO_READY,
    minutes_from_now: int = 10,
) -> AnnouncementJob:
    return AnnouncementJob(
        station_id=station_id,
        language="en" if station_id.endswith("en") else "fr",
        kind="track",
        planner_key=planner_key,
        planned_airtime=NOW + timedelta(minutes=minutes_from_now),
        deadline=NOW + timedelta(minutes=minutes_from_now - 1),
        freshness_class="durable",
        priority=1,
        state=state,
    )


def test_horizon_persists_only_its_station_entries(tmp_path) -> None:
    english = AnnouncementHorizon(tmp_path, "radiotedu-en")
    english.upsert(_job("radiotedu-en", "en-1"), duration_minutes=30)

    french = AnnouncementHorizon(tmp_path, "radiotedu-fr")
    french.upsert(_job("radiotedu-fr", "fr-1"), duration_minutes=45)

    restored_english = AnnouncementHorizon(tmp_path, "radiotedu-en")

    assert [entry.job.planner_key for entry in restored_english.entries()] == ["en-1"]
    assert restored_english.coverage(now=NOW).ready_minutes == 30
    assert french.coverage(now=NOW).ready_minutes == 45


def test_readiness_uses_cold_start_and_normal_targets_and_preserves_music_below_minimum() -> None:
    cold_start = readiness_status(
        "radiotedu-en",
        ready_minutes=60,
        planned_minutes=80,
        failed_minutes=0,
        cold_start=True,
    )
    normal = readiness_status(
        "radiotedu-en",
        ready_minutes=60,
        planned_minutes=80,
        failed_minutes=0,
    )
    music_only = readiness_status(
        "radiotedu-en",
        ready_minutes=9,
        planned_minutes=30,
        failed_minutes=0,
    )

    assert cold_start.target_minutes == 60
    assert cold_start.can_start is True
    assert normal.target_minutes == 180
    assert normal.can_start is False
    assert music_only.level == "music-only"
    assert music_only.music_only is True


def test_generation_inputs_are_station_local_and_ordered_by_deadline(tmp_path) -> None:
    english = AnnouncementHorizon(tmp_path, "radiotedu-en")
    english.upsert(
        _job("radiotedu-en", "later", state=AnnouncementState.PLANNED, minutes_from_now=40),
        duration_minutes=1,
    )
    english.upsert(
        _job("radiotedu-en", "urgent", state=AnnouncementState.PLANNED, minutes_from_now=15),
        duration_minutes=1,
    )
    AnnouncementHorizon(tmp_path, "radiotedu-fr").upsert(
        _job("radiotedu-fr", "other-station", state=AnnouncementState.PLANNED, minutes_from_now=5),
        duration_minutes=1,
    )

    inputs = english.generation_inputs(now=NOW)

    assert [item.job.planner_key for item in inputs] == ["urgent", "later"]
    assert [item.deadline for item in inputs] == [
        NOW + timedelta(minutes=14),
        NOW + timedelta(minutes=39),
    ]
