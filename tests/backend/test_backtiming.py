from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.audio.segue_policy import CueMetadata, Genre, MediaKind, SegueItem, SegueKind
from backend.programming.backtiming import Backtimer, BacktimingCandidate, BacktimingError
from backend.programming.clocks import ClockPosition, ProgramClock


BOUNDARY = datetime(2026, 7, 11, 10, tzinfo=timezone.utc)


def clock(station_id: str = "radiotedu-en") -> ProgramClock:
    positions = (
        ClockPosition(1, 0, "music", "current", "soft", 30, {}),
        ClockPosition(2, 180, "music", "recurrent", "soft", 30, {}),
        ClockPosition(3, 360, "imaging", "station-id", "hard", 2, {}),
    )
    return ProgramClock(
        clock_id="morning-v1",
        station_id=station_id,
        name="Morning",
        daypart="morning",
        timezone_name="Europe/Istanbul",
        version=1,
        effective_from=date(2026, 7, 1),
        effective_until=None,
        active=True,
        checksum="a" * 64,
        positions=positions,
    )


def pop_music() -> SegueItem:
    return SegueItem(
        media_kind=MediaKind.MUSIC,
        duration_seconds=180,
        genre=Genre.POP,
        cue=CueMetadata(
            cue_in_seconds=0,
            cue_out_seconds=180,
            intro_end_seconds=5,
            intro_confidence=0.95,
            overlap_validated=True,
        ),
    )


def test_backtimer_hits_hard_boundary_without_overlapping_an_approved_crossfade() -> None:
    program_clock = clock()
    candidates = (
        BacktimingCandidate("track-1", "radiotedu-en", pop_music(), program_clock.positions[0]),
        BacktimingCandidate("track-2", "radiotedu-en", pop_music(), program_clock.positions[1]),
        BacktimingCandidate(
            "station-id-1",
            "radiotedu-en",
            SegueItem(MediaKind.FULL_JINGLE, 8),
            program_clock.positions[2],
        ),
    )

    plan = Backtimer().plan("radiotedu-en", program_clock, BOUNDARY, candidates)

    assert plan.ends_at == BOUNDARY
    assert plan.within_hard_boundary is True
    assert all(
        current.end_at <= following.start_at
        for current, following in zip(plan.items, plan.items[1:])
    )
    assert plan.items[0].transition.kind is SegueKind.SEQUENTIAL
    assert "no overlap" in plan.items[0].transition.reason


def test_backtimer_refuses_candidates_from_another_station() -> None:
    program_clock = clock()
    candidate = BacktimingCandidate(
        "foreign-track", "radiotedu-fr", pop_music(), program_clock.positions[0]
    )

    with pytest.raises(BacktimingError, match="station"):
        Backtimer().plan("radiotedu-en", program_clock, BOUNDARY, (candidate,))
