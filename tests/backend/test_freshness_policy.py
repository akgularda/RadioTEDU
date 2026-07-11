from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.util import find_spec

from backend.announcements.models import AnnouncementJob, AnnouncementState


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def make_job(
    kind: str,
    *,
    state: AnnouncementState = AnnouncementState.AUDIO_READY,
) -> AnnouncementJob:
    return AnnouncementJob(
        station_id="en",
        language="en",
        kind=kind,
        planner_key=f"{kind}:2026-07-11T12:00:00Z",
        planned_airtime=NOW,
        deadline=NOW,
        freshness_class="broadcast",
        priority=1,
        state=state,
    )


def freshness_policy():
    assert find_spec("backend.announcements.freshness"), (
        "freshness policy module must exist"
    )
    from backend.announcements import freshness

    return freshness


def test_speech_targets_and_dynamic_gate_are_deterministic() -> None:
    freshness = freshness_policy()

    assert freshness.speech_target_minutes() == 180
    assert freshness.speech_target_minutes(cold_start=True) == 60
    assert freshness.dynamic_speech_enabled(10)
    assert not freshness.dynamic_speech_enabled(9)


def test_news_and_weather_have_generation_deadlines_before_airtime() -> None:
    freshness = freshness_policy()

    news = freshness.apply_generation_deadline(make_job("news"))
    weather = freshness.apply_generation_deadline(make_job("weather"))

    assert news.deadline == NOW - timedelta(minutes=15)
    assert weather.deadline == NOW - timedelta(minutes=10)


def test_stale_news_is_skipped_at_airtime_while_music_continues() -> None:
    freshness = freshness_policy()

    decision = freshness.evaluate_job(make_job("news"), now=NOW)

    assert decision.job.state is AnnouncementState.SKIPPED
    assert decision.play_speech is False
    assert decision.music_continues is True
    assert decision.reason == "stale"


def test_missing_speech_is_skipped_without_stopping_music() -> None:
    freshness = freshness_policy()

    decision = freshness.evaluate_job(
        make_job("weather", state=AnnouncementState.TEXT_READY), now=NOW
    )

    assert decision.job.state is AnnouncementState.SKIPPED
    assert decision.play_speech is False
    assert decision.music_continues is True
    assert decision.reason == "missing-speech"
