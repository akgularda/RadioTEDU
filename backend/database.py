from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable

from .config import Settings, ensure_runtime_dirs


PROGRAMS = [
    {
        "id": "morning_signal",
        "name": "Morning Signal",
        "description": "Bright, curious, optimistic music with short updates to start the day.",
        "vibe": "upbeat, warm, fresh",
        "start_time": "06:00",
        "end_time": "10:00",
        "days_of_week": "mon,tue,wed,thu,fri",
        "cover_path": "/static/generated/covers/morning_signal.png",
    },
    {
        "id": "campus_frequencies",
        "name": "Campus Frequencies",
        "description": "Indie, electronic, and global sounds for focused work and study.",
        "vibe": "focused, intelligent, mellow",
        "start_time": "10:00",
        "end_time": "18:00",
        "days_of_week": "mon,tue,wed,thu,fri",
        "cover_path": "/static/generated/covers/campus_frequencies.png",
    },
    {
        "id": "night_lab",
        "name": "Night Lab",
        "description": "Late-night ambient, experimental, and thoughtful tracks.",
        "vibe": "nocturnal, spacious, reflective",
        "start_time": "18:00",
        "end_time": "23:59",
        "days_of_week": "mon,tue,wed,thu,fri,sat,sun",
        "cover_path": "/static/generated/covers/night_lab.png",
    },
    {
        "id": "weekend_transmission",
        "name": "Weekend Transmission",
        "description": "Relaxed discoveries, classics, and feel-good weekend selections.",
        "vibe": "relaxed, sunny, eclectic",
        "start_time": "08:00",
        "end_time": "18:00",
        "days_of_week": "sat,sun",
        "cover_path": "/static/generated/covers/weekend_transmission.png",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(settings: Settings):
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    try:
        yield conn
    finally:
        conn.close()


def init_db(settings: Settings) -> None:
    ensure_runtime_dirs(settings)
    with connect(settings) as conn:
        conn.executescript(SCHEMA)
        conn.execute("drop table if exists donations")
        seed_channel(conn, settings)
        seed_programs(conn)
        conn.commit()


def seed_channel(conn: sqlite3.Connection, settings: Settings) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        insert into channels (id, name, description, host_model, status, cover_path, created_at, updated_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            name=excluded.name,
            description=excluded.description,
            host_model=excluded.host_model,
            cover_path=excluded.cover_path,
            updated_at=excluded.updated_at
        """,
        (
            "radiotedu",
            "RadioTEDU",
            "Local AI radio running on your machine.",
            settings.ollama_model,
            "idle",
            "/static/generated/covers/radiotedu_station.png",
            timestamp,
            timestamp,
        ),
    )


def seed_programs(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    for program in PROGRAMS:
        conn.execute(
            """
            insert into programs (
                id, channel_id, name, description, vibe, start_time, end_time,
                days_of_week, cover_path, active, created_at, updated_at
            )
            values (?, 'radiotedu', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            on conflict(id) do update set
                name=excluded.name,
                description=excluded.description,
                vibe=excluded.vibe,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                days_of_week=excluded.days_of_week,
                cover_path=excluded.cover_path,
                active=1,
                updated_at=excluded.updated_at
            """,
            (
                program["id"],
                program["name"],
                program["description"],
                program["vibe"],
                program["start_time"],
                program["end_time"],
                program["days_of_week"],
                program["cover_path"],
                timestamp,
                timestamp,
            ),
        )


def log_event(conn: sqlite3.Connection, level: str, message: str, metadata: dict | None = None) -> None:
    conn.execute(
        "insert into agent_logs (level, message, metadata_json, created_at) values (?, ?, ?, ?)",
        (level, message, json.dumps(metadata or {}, ensure_ascii=True), now_iso()),
    )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


SCHEMA = """
create table if not exists channels (
    id text primary key,
    name text not null,
    description text not null,
    host_model text not null,
    status text not null,
    cover_path text,
    created_at text not null,
    updated_at text not null
);

create table if not exists programs (
    id text primary key,
    channel_id text not null references channels(id),
    name text not null,
    description text not null,
    vibe text,
    start_time text not null,
    end_time text not null,
    days_of_week text not null,
    cover_path text,
    active integer not null default 1,
    created_at text not null,
    updated_at text not null
);

create table if not exists tracks (
    id integer primary key autoincrement,
    title text not null,
    artist text not null,
    album text,
    genre text,
    mood text,
    bpm integer,
    duration_seconds real,
    file_path text not null unique,
    cover_path text,
    last_played_at text,
    play_count integer not null default 0,
    created_at text not null,
    updated_at text not null
);

create table if not exists play_history (
    id integer primary key autoincrement,
    track_id integer not null references tracks(id),
    program_id text references programs(id),
    played_at text not null,
    duration_seconds real,
    source text not null
);

create table if not exists generated_clips (
    id integer primary key autoincrement,
    clip_type text not null,
    text text not null,
    file_path text not null,
    voice text,
    program_id text references programs(id),
    created_at text not null
);

create table if not exists station_metrics (
    id integer primary key autoincrement,
    channel_id text not null references channels(id),
    key text not null,
    value text not null,
    updated_at text not null,
    unique(channel_id, key)
);

create table if not exists listener_events (
    id integer primary key autoincrement,
    channel_id text not null references channels(id),
    event_type text not null,
    created_at text not null,
    metadata_json text not null default '{}'
);

create table if not exists agent_logs (
    id integer primary key autoincrement,
    level text not null,
    message text not null,
    metadata_json text not null default '{}',
    created_at text not null
);

create table if not exists autonomy_memory (
    id integer primary key autoincrement,
    kind text not null,
    content text not null,
    source text not null,
    weight real not null default 1.0,
    created_at text not null
);

create table if not exists schedule_revisions (
    id integer primary key autoincrement,
    program_id text not null references programs(id),
    old_start_time text not null,
    old_end_time text not null,
    old_days_of_week text not null,
    new_start_time text not null,
    new_end_time text not null,
    new_days_of_week text not null,
    reason text not null,
    created_at text not null
);

create table if not exists outbound_drafts (
    id integer primary key autoincrement,
    draft_type text not null,
    content text not null,
    status text not null default 'draft',
    created_at text not null
);

create table if not exists incidents (
    id integer primary key autoincrement,
    component text not null,
    severity text not null,
    status text not null default 'open',
    summary text not null,
    details_json text not null default '{}',
    created_at text not null,
    updated_at text not null,
    resolved_at text
);

create table if not exists autonomous_tasks (
    id integer primary key autoincrement,
    task_type text not null,
    component text not null,
    title text not null,
    status text not null default 'queued',
    priority integer not null default 50,
    attempts integer not null default 0,
    details_json text not null default '{}',
    created_at text not null,
    updated_at text not null,
    completed_at text
);

create table if not exists announcement_queue (
    id integer primary key autoincrement,
    text text not null,
    file_path text not null,
    status text not null,
    program_id text references programs(id),
    source text not null,
    created_at text not null,
    used_at text,
    metadata_json text not null default '{}'
);

create table if not exists public_snapshots (
    id integer primary key autoincrement,
    payload_json text not null,
    received_at text not null
);

create table if not exists public_listener_sessions (
    session_id text primary key,
    started_at text not null,
    last_seen_at text not null,
    ended_at text,
    user_agent text
);

create index if not exists idx_tracks_file_path on tracks(file_path);
create index if not exists idx_tracks_last_played on tracks(last_played_at);
create index if not exists idx_play_history_played_at on play_history(played_at);
create index if not exists idx_agent_logs_created_at on agent_logs(created_at);
create index if not exists idx_autonomy_memory_created_at on autonomy_memory(created_at);
create index if not exists idx_announcement_queue_status on announcement_queue(status, created_at);
create index if not exists idx_incidents_status on incidents(status, severity, created_at);
create index if not exists idx_autonomous_tasks_status on autonomous_tasks(status, priority, created_at);
create index if not exists idx_public_snapshots_received_at on public_snapshots(received_at);
create index if not exists idx_public_listener_sessions_seen on public_listener_sessions(last_seen_at, ended_at);
"""
