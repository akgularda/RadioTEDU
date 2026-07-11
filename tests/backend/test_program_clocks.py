from __future__ import annotations

from datetime import date, datetime, timezone
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from backend.database import apply_migrations
from backend.programming.clocks import (
    ClockPosition,
    ClockValidationError,
    ProgramClockStore,
)


ISTANBUL = ZoneInfo("Europe/Istanbul")


def make_store() -> ProgramClockStore:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    apply_migrations(conn)
    return ProgramClockStore(conn)


def positions() -> tuple[ClockPosition, ...]:
    return (
        ClockPosition(
            ordinal=1,
            offset_seconds=0,
            item_kind="music",
            category="current",
            boundary_kind="soft",
            maximum_lateness_seconds=30,
            rules={"energy": "high"},
        ),
        ClockPosition(
            ordinal=2,
            offset_seconds=180,
            item_kind="imaging",
            category="station-id",
            boundary_kind="hard",
            maximum_lateness_seconds=2,
            rules={},
        ),
    )


def create_clock(
    store: ProgramClockStore,
    *,
    station_id: str = "radiotedu-en",
    effective_from: date = date(2026, 7, 1),
    effective_until: date | None = None,
):
    return store.create_clock(
        station_id=station_id,
        name="Morning Signal",
        daypart="morning",
        timezone_name="Europe/Istanbul",
        effective_from=effective_from,
        effective_until=effective_until,
        positions=positions(),
    )


def test_persists_immutable_versioned_clock_positions_and_history() -> None:
    store = make_store()
    first = create_clock(store, effective_until=date(2026, 7, 31))
    second = create_clock(store, effective_from=date(2026, 8, 1))

    history = store.history("radiotedu-en", "morning")

    assert first.version == 1
    assert second.version == 2
    assert first.clock_id != second.clock_id
    assert first.checksum
    assert [clock.version for clock in history] == [2, 1]
    assert history[1].positions == positions()
    assert history[1].effective_until == date(2026, 7, 31)


def test_active_clock_lookup_is_station_scoped_timezone_aware_and_deterministic() -> None:
    store = make_store()
    english = create_clock(store, effective_until=date(2026, 7, 31))
    english_next = create_clock(store, effective_from=date(2026, 8, 1))
    french = create_clock(
        store,
        station_id="radiotedu-fr",
        effective_from=date(2026, 7, 1),
    )

    before_midnight_utc = datetime(2026, 7, 31, 20, 30, tzinfo=timezone.utc)
    after_midnight_utc = datetime(2026, 7, 31, 21, 30, tzinfo=timezone.utc)

    assert store.active_clock("radiotedu-en", "morning", before_midnight_utc) == english
    assert store.active_clock("radiotedu-en", "morning", after_midnight_utc) == english_next
    assert store.active_clock("radiotedu-fr", "morning", after_midnight_utc) == french
    assert store.active_clock("radiotedu-en", "night", after_midnight_utc) is None


def test_rejects_invalid_dayparts_timezones_overlaps_and_partial_writes() -> None:
    store = make_store()
    first = create_clock(store, effective_until=date(2026, 7, 31))

    with pytest.raises(ClockValidationError, match="timezone"):
        store.create_clock(
            station_id="radiotedu-en",
            name="Morning Signal",
            daypart="morning",
            timezone_name="UTC",
            effective_from=date(2026, 8, 1),
            effective_until=None,
            positions=positions(),
        )
    with pytest.raises(ClockValidationError, match="daypart"):
        store.create_clock(
            station_id="radiotedu-en",
            name="Morning Signal",
            daypart="late-night",
            timezone_name="Europe/Istanbul",
            effective_from=date(2026, 8, 1),
            effective_until=None,
            positions=positions(),
        )
    with pytest.raises(ClockValidationError, match="overlaps"):
        create_clock(
            store,
            effective_from=date(2026, 7, 15),
            effective_until=date(2026, 8, 15),
        )
    with pytest.raises(ClockValidationError, match="offsets"):
        store.create_clock(
            station_id="radiotedu-en",
            name="Morning Signal",
            daypart="morning",
            timezone_name="Europe/Istanbul",
            effective_from=date(2026, 8, 1),
            effective_until=None,
            positions=(
                ClockPosition(1, 240, "music", "current", "soft", 30, {}),
                ClockPosition(2, 180, "imaging", "station-id", "hard", 2, {}),
            ),
        )

    assert store.history("radiotedu-en", "morning") == (first,)
