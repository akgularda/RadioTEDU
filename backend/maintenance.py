from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .database import connect, init_db, now_iso


def run_maintenance(settings: Settings, clip_retention_days: int = 7, max_agent_logs: int = 500) -> dict:
    init_db(settings)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(0, int(clip_retention_days)))).isoformat()
    clips_deleted = 0
    files_deleted = 0
    with connect(settings) as conn:
        old_clips = conn.execute(
            "select id, file_path from generated_clips where created_at < ? order by created_at asc",
            (cutoff,),
        ).fetchall()
        for row in old_clips:
            files_deleted += _delete_clip_files(settings, row["file_path"])
            conn.execute("delete from generated_clips where id=?", (row["id"],))
            clips_deleted += 1
        log_ids = [
            row["id"]
            for row in conn.execute(
                """
                select id from agent_logs
                where id not in (
                    select id from agent_logs order by created_at desc, id desc limit ?
                )
                """,
                (max(0, int(max_agent_logs)),),
            ).fetchall()
        ]
        if log_ids:
            placeholders = ",".join("?" for _ in log_ids)
            conn.execute(f"delete from agent_logs where id in ({placeholders})", log_ids)
        conn.execute(
            "insert or replace into station_metrics (channel_id, key, value, updated_at) values ('radiotedu', ?, ?, ?)",
            ("last_maintenance_json", f"clips={clips_deleted};files={files_deleted};logs={len(log_ids)}", now_iso()),
        )
        conn.commit()
    return {
        "clips_deleted": clips_deleted,
        "files_deleted": files_deleted,
        "logs_deleted": len(log_ids),
        "clip_retention_days": int(clip_retention_days),
        "max_agent_logs": int(max_agent_logs),
    }


def maintenance_summary(settings: Settings) -> dict:
    init_db(settings)
    with connect(settings) as conn:
        generated = conn.execute("select count(*) from generated_clips").fetchone()[0]
        logs = conn.execute("select count(*) from agent_logs").fetchone()[0]
        last = conn.execute("select value, updated_at from station_metrics where key='last_maintenance_json'").fetchone()
    return {
        "generated_clip_count": int(generated),
        "agent_log_count": int(logs),
        "last_maintenance": dict(last) if last else None,
    }


def watchdog_summary(settings: Settings) -> dict:
    init_db(settings)
    with connect(settings) as conn:
        stale_prebuffer = conn.execute("select count(*) from announcement_queue where status in ('failed', 'stale')").fetchone()[0]
        ready_prebuffer = conn.execute("select count(*) from announcement_queue where status='ready'").fetchone()[0]
        errors = conn.execute("select count(*) from agent_logs where level='error'").fetchone()[0]
    return {
        "stale_prebuffer": int(stale_prebuffer),
        "ready_prebuffer": int(ready_prebuffer),
        "error_log_count": int(errors),
    }


def _delete_clip_files(settings: Settings, file_path: str) -> int:
    path = Path(file_path)
    try:
        resolved = path.resolve()
        tts_root = settings.tts_path.resolve()
        if tts_root not in resolved.parents and resolved != tts_root:
            return 0
    except OSError:
        return 0
    deleted = 0
    for candidate in (path, path.with_suffix(".txt")):
        try:
            if candidate.exists():
                candidate.unlink()
                deleted += 1
        except OSError:
            continue
    return deleted
