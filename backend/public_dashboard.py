from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .database import connect, init_db, log_event, now_iso, rows_to_dicts
from .scheduler import current_program, next_programs


PUBLIC_EMPTY_NOW = {
    "type": "idle",
    "title": "Waiting for RadioTEDU broadcast.",
    "artist": None,
    "started_at": None,
}


def public_snapshot_from_state(settings: Settings, agent) -> dict:
    init_db(settings)
    with connect(settings) as conn:
        channel = dict(conn.execute("select * from channels where id='radiotedu'").fetchone())
        programs = rows_to_dicts(conn.execute("select * from programs where channel_id='radiotedu' order by start_time").fetchall())
        top_songs_rows = conn.execute(
            """
            select tracks.id, tracks.title, tracks.artist, count(play_history.id) as plays
            from play_history
            join tracks on tracks.id = play_history.track_id
            where play_history.played_at >= datetime('now', '-14 days')
            group by tracks.id, tracks.title, tracks.artist
            order by plays desc, tracks.title asc
            limit 10
            """
        ).fetchall()
        top_genres_rows = conn.execute(
            """
            select coalesce(tracks.genre, 'unknown') as genre, count(play_history.id) as plays
            from play_history
            join tracks on tracks.id = play_history.track_id
            where play_history.played_at >= datetime('now', '-14 days')
            group by coalesce(tracks.genre, 'unknown')
            order by plays desc, genre asc
            limit 10
            """
        ).fetchall()
        music_count = conn.execute("select count(*) from play_history").fetchone()[0]
        talk_count = conn.execute("select count(*) from generated_clips").fetchone()[0]
        listener_notes = rows_to_dicts(
            conn.execute(
                """
                select content, source, created_at
                from autonomy_memory
                where kind='listener_feedback'
                order by created_at desc, id desc
                limit 4
                """
            ).fetchall()
        )
        broadcast_logs = rows_to_dicts(
            conn.execute(
                """
                select message, created_at
                from agent_logs
                where level='info' and message like 'Queued %'
                order by created_at desc, id desc
                limit 4
                """
            ).fetchall()
        )
    playback = agent.playback.state()
    current = current_program(settings)
    upcoming = next_programs(settings)
    snapshot = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(5, settings.snapshot_ttl_seconds))).isoformat(),
        "channel": _public_channel(channel),
        "now_playing": _public_playback(playback),
        "current_program": _public_program(current),
        "current_minutes_left": _minutes_left(current.get("end_time")),
        "next_program": _public_program_or_none(upcoming[0]) if upcoming else None,
        "next_programs": [_public_program(program) for program in upcoming],
        "programs": [_public_program(program) for program in programs],
        "top_songs": [dict(row) for row in top_songs_rows],
        "top_genres": [dict(row) for row in top_genres_rows],
        "content_breakdown": _content_breakdown(music_count, talk_count),
        "activity": _activity_from_state(listener_notes, broadcast_logs),
        "stream": {
            "url": settings.public_stream_url,
            "status": "configured" if settings.public_stream_url else "unconfigured",
        },
        "metrics": {
            "current_listeners": None,
            "popularity": None,
            "average_session": None,
        },
    }
    return sanitize_public_snapshot(snapshot)


def sanitize_public_snapshot(payload: dict) -> dict:
    safe = {
        "schema_version": _nullable_int(payload.get("schema_version"), 1, 1) or 1,
        "generated_at": _text(payload.get("generated_at")),
        "expires_at": _text(payload.get("expires_at")),
        "channel": _public_channel(_dict(payload.get("channel"))),
        "now_playing": _public_playback(_dict(payload.get("now_playing"))),
        "current_program": _public_program_or_none(payload.get("current_program")),
        "current_minutes_left": _nullable_int(payload.get("current_minutes_left"), 0, 1440),
        "next_program": _public_program_or_none(payload.get("next_program")),
        "next_programs": [_public_program(item) for item in _list(payload.get("next_programs"))[:4]],
        "programs": [_public_program(item) for item in _list(payload.get("programs"))[:8]],
        "top_songs": [_public_song(item) for item in _list(payload.get("top_songs"))[:10]],
        "top_genres": [_public_genre(item) for item in _list(payload.get("top_genres"))[:10]],
        "content_breakdown": [_public_breakdown(item) for item in _list(payload.get("content_breakdown"))[:4]],
        "activity": [_public_activity(item) for item in _list(payload.get("activity"))[:8]],
        "stream": _public_stream(_dict(payload.get("stream"))),
    }
    safe["content_breakdown"] = [item for item in safe["content_breakdown"] if item]
    safe["activity"] = [item for item in safe["activity"] if item]
    safe["metrics"] = {
        "current_listeners": None,
        "popularity": None,
        "average_session": None,
    }
    return safe


def store_public_snapshot(settings: Settings, payload: dict) -> dict:
    init_db(settings)
    sanitized = sanitize_public_snapshot(payload)
    with connect(settings) as conn:
        conn.execute(
            "insert into public_snapshots (payload_json, received_at) values (?, ?)",
            (json.dumps(sanitized, ensure_ascii=True), now_iso()),
        )
        conn.execute(
            "delete from public_snapshots where id not in (select id from public_snapshots order by received_at desc, id desc limit 10)"
        )
        conn.commit()
    return sanitized


def public_status(settings: Settings) -> dict:
    init_db(settings)
    with connect(settings) as conn:
        row = conn.execute(
            "select payload_json, received_at from public_snapshots order by received_at desc, id desc limit 1"
        ).fetchone()
    metrics = public_session_metrics(settings)
    if row is None:
        return _offline_public_status(settings, metrics)
    try:
        payload = sanitize_public_snapshot(json.loads(row["payload_json"] or "{}"))
    except Exception:
        return _offline_public_status(settings, metrics)
    stale = _is_stale(row["received_at"], settings.snapshot_ttl_seconds)
    payload["online"] = not stale
    payload["received_at"] = row["received_at"]
    payload["metrics"] = metrics
    if stale:
        payload["channel"]["status"] = "idle"
        payload["now_playing"] = PUBLIC_EMPTY_NOW
        payload["message"] = "Waiting for the broadcast computer to sync."
    else:
        payload["message"] = ""
    return payload


def public_session_start(settings: Settings, session_id: str, user_agent: str | None = None) -> dict:
    init_db(settings)
    clean_id = _clean_session_id(session_id)
    now = now_iso()
    with connect(settings) as conn:
        conn.execute(
            """
            insert into public_listener_sessions (session_id, started_at, last_seen_at, ended_at, user_agent)
            values (?, ?, ?, null, ?)
            on conflict(session_id) do update set last_seen_at=excluded.last_seen_at, ended_at=null
            """,
            (clean_id, now, now, (user_agent or "")[:160]),
        )
        conn.commit()
    return {"session_id": clean_id, "metrics": public_session_metrics(settings)}


def public_session_heartbeat(settings: Settings, session_id: str) -> dict:
    init_db(settings)
    clean_id = _clean_session_id(session_id)
    with connect(settings) as conn:
        conn.execute(
            "update public_listener_sessions set last_seen_at=?, ended_at=null where session_id=?",
            (now_iso(), clean_id),
        )
        if conn.total_changes == 0:
            conn.execute(
                "insert into public_listener_sessions (session_id, started_at, last_seen_at, ended_at) values (?, ?, ?, null)",
                (clean_id, now_iso(), now_iso()),
            )
        conn.commit()
    return {"session_id": clean_id, "metrics": public_session_metrics(settings)}


def public_session_end(settings: Settings, session_id: str) -> dict:
    init_db(settings)
    clean_id = _clean_session_id(session_id)
    with connect(settings) as conn:
        conn.execute(
            "update public_listener_sessions set last_seen_at=?, ended_at=? where session_id=?",
            (now_iso(), now_iso(), clean_id),
        )
        conn.commit()
    return {"session_id": clean_id, "metrics": public_session_metrics(settings)}


def public_session_metrics(settings: Settings) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max(15, settings.snapshot_ttl_seconds))).isoformat()
    with connect(settings) as conn:
        active = conn.execute(
            "select count(*) from public_listener_sessions where ended_at is null and last_seen_at >= ?",
            (cutoff,),
        ).fetchone()[0]
        rows = conn.execute(
            "select started_at, coalesce(ended_at, last_seen_at) as finished_at from public_listener_sessions"
        ).fetchall()
    durations: list[int] = []
    for row in rows:
        try:
            start = datetime.fromisoformat(row["started_at"])
            end = datetime.fromisoformat(row["finished_at"])
            seconds = max(0, int((end - start).total_seconds()))
        except Exception:
            continue
        if seconds > 0:
            durations.append(seconds)
    return {
        "current_listeners": int(active),
        "popularity": _popularity(active, durations),
        "average_session": _format_duration(sum(durations) // len(durations)) if durations else None,
    }


class PublicSnapshotPusher:
    def __init__(self, settings: Settings, agent) -> None:
        self.settings = settings
        self.agent = agent
        self.last_push_at = time.time()
        self.last_result: dict | None = None
        self.failures = 0
        self.running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start_background(self) -> dict:
        if not self.settings.public_sync_url or not self.settings.public_sync_token:
            return {"running": False, "reason": "not_configured"}
        if self.running:
            return {"running": True, "reason": "already_running"}
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, name="radiotedu-public-snapshot-pusher", daemon=True)
        self._thread.start()
        return {"running": True, "reason": "started"}

    def stop_background(self) -> dict:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        self.running = False
        self._thread = None
        return {"running": False, "reason": "stopped"}

    def status(self) -> dict:
        return {
            "configured": bool(self.settings.public_sync_url and self.settings.public_sync_token),
            "running": self.running,
            "last_push_at": self.last_push_at if self.last_result else None,
            "last_result": self.last_result,
            "consecutive_failures": self.failures,
            "interval_seconds": max(5, int(self.settings.public_sync_interval_seconds)),
        }

    def _run_loop(self) -> None:
        while not self._stop.wait(1):
            self.last_result = self.maybe_push()

    def maybe_push(self) -> dict:
        if not self.settings.public_sync_url or not self.settings.public_sync_token:
            self.last_result = {"pushed": False, "reason": "not_configured"}
            return self.last_result
        now = time.time()
        interval = max(5, int(self.settings.public_sync_interval_seconds))
        backoff = min(120, interval * max(1, self.failures))
        wait = backoff if self.failures else interval
        if now - self.last_push_at < wait:
            self.last_result = {"pushed": False, "reason": "waiting"}
            return self.last_result
        self.last_push_at = now
        payload = public_snapshot_from_state(self.settings, self.agent)
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(
            self.settings.public_sync_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-RadioTEDU-Sync-Token": self.settings.public_sync_token,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status = response.status
            self.failures = 0
            self.last_result = {"pushed": True, "status": status}
            return self.last_result
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            self.failures += 1
            with connect(self.settings) as conn:
                log_event(conn, "warning", "Public snapshot push failed.", {"error": str(exc), "failures": self.failures})
                conn.commit()
            self.last_result = {"pushed": False, "reason": "push_failed", "error": str(exc)}
            return self.last_result


def _offline_public_status(settings: Settings, metrics: dict) -> dict:
    return {
        "online": False,
        "schema_version": 1,
        "received_at": None,
        "generated_at": None,
        "expires_at": None,
        "message": "Waiting for the broadcast computer to sync.",
        "channel": {
            "id": "radiotedu",
            "name": "RadioTEDU",
            "description": "AI radio from RadioTEDU.",
            "host_model": "",
            "status": "idle",
            "cover_path": "/static/generated/covers/radiotedu_station.png",
        },
        "now_playing": PUBLIC_EMPTY_NOW,
        "current_program": None,
        "current_minutes_left": None,
        "next_program": None,
        "next_programs": [],
        "programs": [],
        "top_songs": [],
        "top_genres": [],
        "content_breakdown": [],
        "activity": [],
        "stream": {"url": settings.public_stream_url, "status": "configured" if settings.public_stream_url else "unconfigured"},
        "metrics": metrics,
    }


def _public_channel(channel: dict) -> dict:
    return {
        "id": "radiotedu",
        "name": _text(channel.get("name") or "RadioTEDU")[:80],
        "description": _text(channel.get("description") or "AI radio from RadioTEDU.")[:180],
        "host_model": _text(channel.get("host_model"))[:80],
        "status": _status(channel.get("status")),
        "cover_path": _public_path(channel.get("cover_path")),
    }


def _public_playback(item: dict) -> dict:
    return {
        "type": _text(item.get("type") or "idle")[:32],
        "title": _text(item.get("title") or PUBLIC_EMPTY_NOW["title"])[:160],
        "artist": _nullable_text(item.get("artist"), 120),
        "started_at": _nullable_text(item.get("started_at"), 80),
    }


def _public_program_or_none(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return None
    return _public_program(item)


def _public_program(program: dict) -> dict:
    item = _dict(program)
    return {
        "id": _text(item.get("id"))[:80],
        "name": _text(item.get("name"))[:100],
        "description": _text(item.get("description"))[:220],
        "vibe": _nullable_text(item.get("vibe"), 160),
        "start_time": _text(item.get("start_time"))[:16],
        "end_time": _text(item.get("end_time"))[:16],
        "days_of_week": _text(item.get("days_of_week"))[:80],
        "cover_path": _public_path(item.get("cover_path")),
        "active": int(item.get("active") or 0),
    }


def _public_song(song: dict) -> dict:
    item = _dict(song)
    return {
        "id": int(item.get("id") or 0),
        "title": _text(item.get("title"))[:140],
        "artist": _text(item.get("artist"))[:120],
        "plays": max(0, int(item.get("plays") or 0)),
    }


def _public_genre(genre: dict) -> dict:
    item = _dict(genre)
    return {"genre": _text(item.get("genre") or "unknown")[:80], "plays": max(0, int(item.get("plays") or 0))}


def _public_breakdown(value: dict) -> dict | None:
    item = _dict(value)
    label = _text(item.get("label"))[:40]
    if label not in {"Music", "Talking"}:
        return None
    try:
        percent = int(item.get("percent") or 0)
    except (TypeError, ValueError):
        percent = 0
    return {"label": label, "percent": max(0, min(100, percent))}


def _public_activity(value: dict) -> dict | None:
    item = _dict(value)
    kind = _text(item.get("kind")).lower()[:24]
    if kind not in {"listener", "host", "broadcast"}:
        return None
    content = _text(item.get("content"))[:220]
    if not content or _has_private_terms(content):
        return None
    actor = _text(item.get("actor") or ("RadioTEDU" if kind != "listener" else "Listener"))[:80]
    if _has_private_terms(actor):
        actor = "RadioTEDU" if kind != "listener" else "Listener"
    return {
        "kind": kind,
        "actor": actor,
        "content": content,
        "created_at": _nullable_text(item.get("created_at"), 80),
    }


def _public_stream(stream: dict) -> dict:
    url = _text(stream.get("url"))[:300]
    return {"url": url, "status": "configured" if url else "unconfigured"}


def _is_stale(received_at: str, ttl_seconds: int) -> bool:
    try:
        received = datetime.fromisoformat(received_at)
    except Exception:
        return True
    return datetime.now(timezone.utc) - received > timedelta(seconds=max(5, ttl_seconds))


def _clean_session_id(session_id: str) -> str:
    clean = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in {"-", "_"})[:80]
    if len(clean) < 8:
        raise ValueError("session_id must be at least 8 safe characters")
    return clean


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    return f"{minutes}m {secs:02d}s"


def _popularity(active: int, durations: list[int]) -> int | None:
    if active == 0 and not durations:
        return None
    score = min(100, active * 10 + min(60, len(durations) * 4))
    return int(score)


def _content_breakdown(music_count: int, talk_count: int) -> list[dict]:
    total = max(0, int(music_count)) + max(0, int(talk_count))
    if total <= 0:
        return []
    music_percent = round((max(0, int(music_count)) / total) * 100)
    talking_percent = 100 - music_percent
    return [
        {"label": "Music", "percent": music_percent},
        {"label": "Talking", "percent": talking_percent},
    ]


def _activity_from_state(listener_notes: list[dict], broadcast_logs: list[dict]) -> list[dict]:
    activity: list[dict] = []
    for note in listener_notes:
        activity.append(
            {
                "kind": "listener",
                "actor": "Listener",
                "content": note.get("content"),
                "created_at": note.get("created_at"),
            }
        )
    for log in broadcast_logs:
        activity.append(
            {
                "kind": "broadcast",
                "actor": "RadioTEDU",
                "content": log.get("message"),
                "created_at": log.get("created_at"),
            }
        )
    return activity[:8]


def _minutes_left(end_time: Any) -> int | None:
    text = _text(end_time)
    try:
        hour, minute = [int(part) for part in text.split(":", 1)]
    except (TypeError, ValueError):
        return None
    now = datetime.now()
    end = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if end <= now:
        end += timedelta(days=1)
    return max(0, int((end - now).total_seconds() // 60))


def _nullable_int(value: Any, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, number))


def _has_private_terms(value: str) -> bool:
    lowered = value.lower()
    private_terms = ("\\", "f:/", "c:/", "file_path", "private", "donation", "payment", "money", "support", "token")
    return any(term in lowered for term in private_terms)


def _public_path(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if "\\" in text or ":" in text:
        return None
    if text.startswith("/static/") or text.startswith("https://") or text.startswith("http://"):
        return text[:300]
    return None


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _nullable_text(value: Any, limit: int) -> str | None:
    text = _text(value)
    return text[:limit] if text else None


def _status(value: Any) -> str:
    text = _text(value).lower()
    return text if text in {"live", "idle", "stopped", "error"} else "idle"
