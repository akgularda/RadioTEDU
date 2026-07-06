from __future__ import annotations

from datetime import datetime

from .config import Settings
from .database import connect, rows_to_dicts
from .database import PROGRAMS


DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _programs_from_db(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
            """
            select id, name, description, vibe, start_time, end_time, days_of_week, cover_path, active
            from programs
            where channel_id='radiotedu' and active=1
            order by start_time
            """
        ).fetchall()
    return rows_to_dicts(rows)


def _matches(program: dict, day: str, minute: int) -> bool:
    if day not in str(program["days_of_week"]).split(","):
        return False
    start = _minutes(program["start_time"])
    end = _minutes(program["end_time"])
    if start <= end:
        return start <= minute <= end
    return minute >= start or minute <= end


def current_program(settings: Settings | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    day = DAY_KEYS[now.weekday()]
    minute = now.hour * 60 + now.minute
    programs = _programs_from_db(settings) if settings is not None else [dict(program) for program in PROGRAMS]
    for program in programs:
        if _matches(program, day, minute):
            return dict(program)
    return dict(programs[0] if programs else PROGRAMS[0])


def next_programs(settings: Settings | None = None, limit: int = 4) -> list[dict]:
    programs = _programs_from_db(settings) if settings is not None else [dict(program) for program in PROGRAMS]
    return [dict(program) for program in programs[:limit]]
