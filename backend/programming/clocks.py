from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import sqlite3
from typing import Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo


ISTANBUL_TIMEZONE = "Europe/Istanbul"
DAYPARTS = frozenset({"morning", "daytime", "night", "weekend"})
BOUNDARY_KINDS = frozenset({"soft", "hard"})


class ClockValidationError(ValueError):
    """Raised when a clock cannot be safely published."""


@dataclass(frozen=True)
class ClockPosition:
    ordinal: int
    offset_seconds: int
    item_kind: str
    category: str
    boundary_kind: str
    maximum_lateness_seconds: int
    rules: Mapping[str, object]


@dataclass(frozen=True)
class ProgramClock:
    clock_id: str
    station_id: str
    name: str
    daypart: str
    timezone_name: str
    version: int
    effective_from: date
    effective_until: date | None
    active: bool
    checksum: str
    positions: tuple[ClockPosition, ...]


class ProgramClockStore:
    """Persists append-only clock versions in a single SQLite transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def create_clock(
        self,
        *,
        station_id: str,
        name: str,
        daypart: str,
        timezone_name: str,
        effective_from: date,
        effective_until: date | None,
        positions: Sequence[ClockPosition],
    ) -> ProgramClock:
        normalized_positions = tuple(positions)
        self._validate_clock(
            station_id=station_id,
            name=name,
            daypart=daypart,
            timezone_name=timezone_name,
            effective_from=effective_from,
            effective_until=effective_until,
            positions=normalized_positions,
        )
        clock_id = uuid4().hex
        checksum = self._checksum(
            station_id=station_id,
            name=name,
            daypart=daypart,
            timezone_name=timezone_name,
            effective_from=effective_from,
            effective_until=effective_until,
            positions=normalized_positions,
        )
        try:
            self._connection.execute("begin immediate")
            self._raise_if_active_range_overlaps(
                station_id, daypart, effective_from, effective_until
            )
            version = self._connection.execute(
                """
                select coalesce(max(version), 0) + 1
                from station_clocks
                where station_id=? and daypart=?
                """,
                (station_id, daypart),
            ).fetchone()[0]
            self._connection.execute(
                """
                insert into station_clocks (
                    clock_id, station_id, name, daypart, timezone_name, version,
                    effective_from, effective_until, active, checksum
                ) values (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    clock_id,
                    station_id,
                    name,
                    daypart,
                    timezone_name,
                    version,
                    effective_from.isoformat(),
                    effective_until.isoformat() if effective_until else None,
                    checksum,
                ),
            )
            for position in normalized_positions:
                self._connection.execute(
                    """
                    insert into clock_positions (
                        position_id, clock_id, ordinal, offset_seconds, item_kind,
                        category, boundary_kind, maximum_lateness_seconds, rules_json
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        clock_id,
                        position.ordinal,
                        position.offset_seconds,
                        position.item_kind,
                        position.category,
                        position.boundary_kind,
                        position.maximum_lateness_seconds,
                        json.dumps(position.rules, sort_keys=True, separators=(",", ":")),
                    ),
                )
            self._connection.execute("commit")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("rollback")
            raise
        return self._clock_by_id(clock_id)

    def active_clock(
        self, station_id: str, daypart: str, at: datetime
    ) -> ProgramClock | None:
        self._validate_station_and_daypart(station_id, daypart)
        if at.tzinfo is None:
            raise ClockValidationError("clock lookup requires a timezone-aware datetime")
        local_date = at.astimezone(ZoneInfo(ISTANBUL_TIMEZONE)).date().isoformat()
        row = self._connection.execute(
            """
            select clock_id
            from station_clocks
            where station_id=?
              and daypart=?
              and active=1
              and effective_from <= ?
              and (effective_until is null or effective_until >= ?)
            order by version desc, clock_id asc
            limit 1
            """,
            (station_id, daypart, local_date, local_date),
        ).fetchone()
        return self._clock_by_id(row["clock_id"]) if row else None

    def history(self, station_id: str, daypart: str) -> tuple[ProgramClock, ...]:
        self._validate_station_and_daypart(station_id, daypart)
        rows = self._connection.execute(
            """
            select clock_id
            from station_clocks
            where station_id=? and daypart=?
            order by version desc, clock_id asc
            """,
            (station_id, daypart),
        ).fetchall()
        return tuple(self._clock_by_id(row["clock_id"]) for row in rows)

    def _clock_by_id(self, clock_id: str) -> ProgramClock:
        row = self._connection.execute(
            """
            select clock_id, station_id, name, daypart, timezone_name, version,
                   effective_from, effective_until, active, checksum
            from station_clocks
            where clock_id=?
            """,
            (clock_id,),
        ).fetchone()
        if row is None:
            raise ClockValidationError(f"unknown clock: {clock_id}")
        position_rows = self._connection.execute(
            """
            select ordinal, offset_seconds, item_kind, category, boundary_kind,
                   maximum_lateness_seconds, rules_json
            from clock_positions
            where clock_id=?
            order by ordinal
            """,
            (clock_id,),
        ).fetchall()
        return ProgramClock(
            clock_id=row["clock_id"],
            station_id=row["station_id"],
            name=row["name"],
            daypart=row["daypart"],
            timezone_name=row["timezone_name"],
            version=row["version"],
            effective_from=date.fromisoformat(row["effective_from"]),
            effective_until=(
                date.fromisoformat(row["effective_until"])
                if row["effective_until"]
                else None
            ),
            active=bool(row["active"]),
            checksum=row["checksum"],
            positions=tuple(
                ClockPosition(
                    ordinal=position["ordinal"],
                    offset_seconds=position["offset_seconds"],
                    item_kind=position["item_kind"],
                    category=position["category"],
                    boundary_kind=position["boundary_kind"],
                    maximum_lateness_seconds=position["maximum_lateness_seconds"],
                    rules=json.loads(position["rules_json"]),
                )
                for position in position_rows
            ),
        )

    def _raise_if_active_range_overlaps(
        self,
        station_id: str,
        daypart: str,
        effective_from: date,
        effective_until: date | None,
    ) -> None:
        row = self._connection.execute(
            """
            select clock_id
            from station_clocks
            where station_id=?
              and daypart=?
              and active=1
              and (? is null or effective_from <= ?)
              and (effective_until is null or effective_until >= ?)
            limit 1
            """,
            (
                station_id,
                daypart,
                effective_until.isoformat() if effective_until else None,
                effective_until.isoformat() if effective_until else None,
                effective_from.isoformat(),
            ),
        ).fetchone()
        if row:
            raise ClockValidationError("clock effective range overlaps an active version")

    @staticmethod
    def _checksum(
        *,
        station_id: str,
        name: str,
        daypart: str,
        timezone_name: str,
        effective_from: date,
        effective_until: date | None,
        positions: Sequence[ClockPosition],
    ) -> str:
        payload = {
            "station_id": station_id,
            "name": name,
            "daypart": daypart,
            "timezone_name": timezone_name,
            "effective_from": effective_from.isoformat(),
            "effective_until": effective_until.isoformat() if effective_until else None,
            "positions": [
                {
                    "ordinal": position.ordinal,
                    "offset_seconds": position.offset_seconds,
                    "item_kind": position.item_kind,
                    "category": position.category,
                    "boundary_kind": position.boundary_kind,
                    "maximum_lateness_seconds": position.maximum_lateness_seconds,
                    "rules": position.rules,
                }
                for position in positions
            ],
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_clock(
        *,
        station_id: str,
        name: str,
        daypart: str,
        timezone_name: str,
        effective_from: date,
        effective_until: date | None,
        positions: Sequence[ClockPosition],
    ) -> None:
        ProgramClockStore._validate_station_and_daypart(station_id, daypart)
        if not isinstance(name, str) or not name.strip():
            raise ClockValidationError("clock name must not be empty")
        if timezone_name != ISTANBUL_TIMEZONE:
            raise ClockValidationError("clock timezone must be Europe/Istanbul")
        if not isinstance(effective_from, date):
            raise ClockValidationError("effective_from must be a date")
        if effective_until is not None and (
            not isinstance(effective_until, date) or effective_until < effective_from
        ):
            raise ClockValidationError("effective range is invalid")
        if not positions:
            raise ClockValidationError("clock requires at least one position")
        ordinals = [position.ordinal for position in positions]
        offsets = [position.offset_seconds for position in positions]
        if ordinals != list(range(1, len(positions) + 1)):
            raise ClockValidationError("clock ordinals must be contiguous")
        if offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
            raise ClockValidationError("clock position offsets must increase")
        for position in positions:
            if (
                not isinstance(position.item_kind, str)
                or not position.item_kind.strip()
                or not isinstance(position.category, str)
                or not position.category.strip()
            ):
                raise ClockValidationError("clock positions require item kind and category")
            if position.offset_seconds < 0 or position.maximum_lateness_seconds < 0:
                raise ClockValidationError("clock position timing must not be negative")
            if position.boundary_kind not in BOUNDARY_KINDS:
                raise ClockValidationError("clock position boundary kind is invalid")
            if not isinstance(position.rules, Mapping):
                raise ClockValidationError("clock position rules must be a mapping")

    @staticmethod
    def _validate_station_and_daypart(station_id: str, daypart: str) -> None:
        if not isinstance(station_id, str) or not station_id.strip():
            raise ClockValidationError("station id must not be empty")
        if daypart not in DAYPARTS:
            raise ClockValidationError("clock daypart is invalid")
