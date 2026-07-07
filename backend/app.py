from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .art.cover_generator import generate_covers
from .config import Settings, ensure_runtime_dirs
from .database import connect, init_db, log_event, now_iso, rows_to_dicts
from .liquidsoap import liquidsoap_status, render_liquidsoap_config, start_liquidsoap, stop_liquidsoap
from .llm import ollama_runtime_status
from .models import ListenerFeedbackRequest, ProgramUpdateRequest, PublicSessionRequest, SayRequest, SearchRequest
from .music_library import scan_music
from .ollama_setup import check_ollama_setup
from .orchestrator import AutonomousOrchestrator
from .public_dashboard import (
    PublicSnapshotPusher,
    public_session_end,
    public_session_heartbeat,
    public_session_start,
    public_status,
    store_public_snapshot,
)
from .radio_agent import RadioAgent
from .scheduler import current_program, next_programs
from .search.rss import RSSSearchProvider
from .search.searxng import SearXNGSearchProvider


STARTED_AT = datetime.now(timezone.utc)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    ensure_runtime_dirs(settings)
    init_db(settings)
    generate_covers(settings)
    agent = RadioAgent(settings)
    orchestrator = AutonomousOrchestrator(settings, agent)
    public_snapshot_pusher = (
        PublicSnapshotPusher(settings, agent)
        if settings.public_sync_url and settings.public_sync_token
        else None
    )
    app = FastAPI(title="RadioTEDU")
    app.state.settings = settings
    app.state.agent = agent
    app.state.orchestrator = orchestrator
    app.state.public_snapshot_pusher = public_snapshot_pusher
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings.frontend_port}",
            f"http://127.0.0.1:{settings.frontend_port}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=str(settings.static_path)), name="static")

    @app.on_event("startup")
    def startup() -> None:
        if settings.autonomy_enabled:
            orchestrator.start_background()
        if public_snapshot_pusher:
            public_snapshot_pusher.start_background()

    @app.on_event("shutdown")
    def shutdown() -> None:
        if public_snapshot_pusher:
            public_snapshot_pusher.stop_background()
        orchestrator.stop_background()

    @app.get("/api/status")
    def status() -> dict:
        return build_status(settings, agent, orchestrator, public_snapshot_pusher)

    @app.get("/api/public/status")
    def public_status_endpoint() -> dict:
        return public_status(settings)

    @app.post("/api/public/snapshot")
    def public_snapshot_endpoint(
        payload: dict = Body(...),
        x_radiotedu_sync_token: str | None = Header(default=None),
    ) -> dict:
        if not settings.public_sync_token or x_radiotedu_sync_token != settings.public_sync_token:
            raise HTTPException(status_code=401, detail="invalid sync token")
        snapshot = store_public_snapshot(settings, payload)
        return {"stored": True, "channel": snapshot["channel"]["id"]}

    @app.post("/api/public/session/start")
    def public_session_start_endpoint(request: PublicSessionRequest, raw: Request) -> dict:
        try:
            return public_session_start(settings, request.session_id, raw.headers.get("user-agent"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/public/session/heartbeat")
    def public_session_heartbeat_endpoint(request: PublicSessionRequest) -> dict:
        try:
            return public_session_heartbeat(settings, request.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/public/session/end")
    def public_session_end_endpoint(request: PublicSessionRequest) -> dict:
        try:
            return public_session_end(settings, request.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/channel")
    def channel() -> dict:
        with connect(settings) as conn:
            return dict(conn.execute("select * from channels where id='radiotedu'").fetchone())

    @app.get("/api/programs")
    def programs() -> list[dict]:
        with connect(settings) as conn:
            return rows_to_dicts(conn.execute("select * from programs where channel_id='radiotedu' order by start_time").fetchall())

    @app.patch("/api/programs/{program_id}")
    def update_program(program_id: str, request: ProgramUpdateRequest) -> dict:
        return patch_program(settings, program_id, request)

    @app.get("/api/tracks/top")
    def tracks_top() -> list[dict]:
        return top_songs(settings)

    @app.get("/api/genres/top")
    def genres_top() -> list[dict]:
        return top_genres(settings)

    @app.get("/api/logs")
    def logs() -> list[dict]:
        return recent_logs(settings)

    @app.get("/api/setup/ollama")
    def ollama_setup() -> dict:
        return check_ollama_setup(settings)

    @app.post("/api/control/start")
    def start() -> dict:
        return orchestrator.start_background()

    @app.post("/api/air/start")
    def air_start() -> dict:
        readiness = air_start_readiness(settings, agent)
        if not readiness["ready"]:
            with connect(settings) as conn:
                log_event(conn, "warning", "Run Air refused because local readiness checks failed.", readiness)
                conn.commit()
            return {"started": False, "reason": readiness["reason"], **readiness}
        stream = start_liquidsoap(settings) if settings.liquidsoap_enabled else {"started": True, "reason": "liquidsoap_disabled"}
        if settings.liquidsoap_enabled and not stream.get("started"):
            with connect(settings) as conn:
                log_event(conn, "error", "Run Air failed before broadcast start.", stream)
                conn.commit()
            return {"started": False, "stream": stream, "orchestrator": orchestrator.status()}
        runner = orchestrator.start_background()
        return {"started": bool(runner.get("running")), "stream": stream, "orchestrator": runner}

    @app.post("/api/air/stop")
    def air_stop() -> dict:
        runner = orchestrator.stop_background()
        stopped = agent.stop()
        stream = stop_liquidsoap(settings) if settings.liquidsoap_enabled else {"stopped": True, "reason": "liquidsoap_disabled"}
        return {"stopped": True, "stream": stream, "orchestrator": runner, "playback": stopped}

    @app.post("/api/control/stop")
    def stop() -> dict:
        orchestrator.stop_background()
        return agent.stop()

    @app.post("/api/control/skip")
    def skip() -> dict:
        return agent.skip()

    @app.post("/api/control/say")
    def say(request: SayRequest) -> dict:
        return agent.say(request.text)

    @app.post("/api/control/search")
    def search(request: SearchRequest) -> dict:
        provider = SearXNGSearchProvider(settings.searxng_url) if settings.search_provider == "searxng" else RSSSearchProvider(settings.rss_feeds_path)
        results = [item.__dict__ for item in provider.search(request.query, limit=5)]
        return {"results": results}

    @app.post("/api/listener/feedback")
    def listener_feedback(request: ListenerFeedbackRequest) -> dict:
        return orchestrator.record_listener_feedback(request.text, request.source)

    @app.get("/api/listener/messages")
    def listener_messages() -> list[dict]:
        return recent_listener_messages(settings)

    @app.post("/api/autonomy/strategy")
    def refresh_strategy() -> dict:
        return orchestrator.maintain_long_horizon_strategy()

    @app.post("/api/autonomy/tick")
    def autonomy_tick() -> dict:
        return orchestrator.tick()

    @app.post("/api/music/rescan")
    def rescan() -> dict:
        result = scan_music(settings)
        return result.__dict__

    @app.post("/api/art/generate-program-covers")
    def covers() -> dict:
        paths = generate_covers(settings)
        with connect(settings) as conn:
            log_event(conn, "info", "Cover art generated.", {"count": len(paths)})
            conn.commit()
        return {"generated": paths}

    @app.post("/api/liquidsoap/render")
    def liquidsoap_render() -> dict:
        return render_liquidsoap_config(settings)

    @app.get("/api/liquidsoap/status")
    def liquidsoap_status_endpoint() -> dict:
        return liquidsoap_status(settings)

    @app.post("/api/liquidsoap/start")
    def liquidsoap_start_endpoint() -> dict:
        result = start_liquidsoap(settings)
        with connect(settings) as conn:
            log_event(conn, "info" if result.get("started") else "warning", "Liquidsoap start requested.", result)
            conn.commit()
        return result

    @app.post("/api/liquidsoap/stop")
    def liquidsoap_stop_endpoint() -> dict:
        result = stop_liquidsoap(settings)
        with connect(settings) as conn:
            log_event(conn, "info", "Liquidsoap stop requested.", result)
            conn.commit()
        return result

    return app


def build_status(
    settings: Settings,
    agent: RadioAgent,
    orchestrator: AutonomousOrchestrator,
    public_snapshot_pusher: PublicSnapshotPusher | None = None,
) -> dict:
    with connect(settings) as conn:
        channel = dict(conn.execute("select * from channels where id='radiotedu'").fetchone())
        track_count = conn.execute("select count(*) from tracks").fetchone()[0]
        programs = rows_to_dicts(conn.execute("select * from programs where channel_id='radiotedu' order by start_time").fetchall())
    has_music = track_count > 0
    current = current_program(settings)
    if agent.playback.now_playing:
        now_playing = agent.playback.state()
    elif has_music:
        now_playing = {
            "type": "idle",
            "title": "Idle — ready to start RadioTEDU.",
            "artist": None,
            "started_at": None,
        }
    else:
        now_playing = {
            "type": "idle",
            "title": "Idle — waiting for music library.",
            "artist": None,
            "started_at": None,
        }
    if now_playing["type"] == "idle" and channel["status"] == "live":
        channel["status"] = "idle"
    liquidsoap = liquidsoap_status(settings)
    if settings.liquidsoap_enabled and not liquidsoap["running"] and channel["status"] == "live":
        channel["status"] = "idle"
    return {
        "channel": channel,
        "now_playing": now_playing,
        "queue": [item.__dict__ for item in agent.playback.queue],
        "current_program": current,
        "programs": programs,
        "next_programs": next_programs(settings),
        "orchestrator": orchestrator.status(),
        "metrics": metrics(settings),
        "top_songs": top_songs(settings),
        "top_genres": top_genres(settings),
        "listener_messages": recent_listener_messages(settings),
        "incidents": recent_incidents(settings),
        "autonomous_tasks": recent_autonomous_tasks(settings),
        "weather": agent.weather_provider.current_context().to_dict(),
        "observability": observability(settings, agent),
        "logs": recent_logs(settings),
        "health": health(settings, agent),
        "liquidsoap": liquidsoap,
        "music_library": music_library_status(settings),
        "configuration": operator_configuration(settings),
        "website_sync": website_sync_health(settings, public_snapshot_pusher),
        "setup": {
            "has_music": has_music,
            "message": "" if has_music else "No music library found. Add audio files to data/music and click Rescan.",
        },
    }


def air_start_readiness(settings: Settings, agent: RadioAgent) -> dict:
    library = music_library_status(settings)
    if library["playable_track_count"] <= 0:
        return {"ready": False, "reason": "no_music", "music_library": library}
    program = current_program(settings)
    buffer_state = agent.ensure_announcement_prebuffer(program["id"])
    if not buffer_state["ready_to_broadcast"]:
        return {
            "ready": False,
            "reason": "announcement_prebuffer_not_ready",
            "music_library": library,
            "announcement_buffer": buffer_state,
        }
    return {
        "ready": True,
        "reason": "ready",
        "music_library": library,
        "announcement_buffer": buffer_state,
    }


def music_library_status(settings: Settings) -> dict:
    with connect(settings) as conn:
        total = conn.execute("select count(*) from tracks").fetchone()[0]
        playable = conn.execute("select count(*) from tracks where file_path <> ''").fetchone()[0]
        scan = conn.execute(
            """
            select created_at
            from agent_logs
            where message like 'Music scan complete:%'
            order by created_at desc, id desc
            limit 1
            """
        ).fetchone()
    return {
        "total_indexed_tracks": int(total),
        "playable_track_count": int(playable),
        "last_scan_time": scan["created_at"] if scan else None,
    }


def operator_configuration(settings: Settings) -> dict:
    mount = settings.liquidsoap_mount if settings.liquidsoap_mount.startswith("/") else f"/{settings.liquidsoap_mount}"
    tts_command = settings.qwen_tts_command or settings.piper_tts_command or settings.tts_provider
    return {
        "MUSIC_DIR": settings.music_dir,
        "OLLAMA_MODEL": settings.ollama_model,
        "TTS_COMMAND": tts_command,
        "LIQUIDSOAP_PATH": settings.liquidsoap_command,
        "LIQUIDSOAP_SCRIPT": settings.liquidsoap_script_path,
        "ICECAST_URL": f"http://{settings.liquidsoap_host}:{settings.liquidsoap_port}{mount}",
        "ICECAST_MOUNT": mount,
        "PUBLIC_SYNC_URL": settings.public_sync_url,
        "PUBLIC_STREAM_URL": settings.public_stream_url,
        "BUFFER_SIZES": {
            "min": int(settings.min_ready_announcements),
            "max": int(settings.max_ready_announcements),
        },
    }


def website_sync_health(settings: Settings, public_snapshot_pusher: PublicSnapshotPusher | None = None) -> dict:
    configured = bool(settings.public_sync_url and settings.public_sync_token)
    pusher_status = public_snapshot_pusher.status() if public_snapshot_pusher else None
    return {
        "configured": configured,
        "health": "running" if pusher_status and pusher_status["running"] else ("configured" if configured else "not_configured"),
        "public_sync_url": settings.public_sync_url,
        "public_stream_url": settings.public_stream_url,
        "interval_seconds": int(settings.public_sync_interval_seconds),
        "pusher": pusher_status,
    }


def patch_program(settings: Settings, program_id: str, request: ProgramUpdateRequest) -> dict:
    allowed = {
        "name": request.name,
        "description": request.description,
        "vibe": request.vibe,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "days_of_week": request.days_of_week,
        "host_name": request.host_name,
        "host_gender": request.host_gender,
        "voice": request.voice,
        "personality": request.personality,
        "active": request.active,
    }
    updates = {key: value for key, value in allowed.items() if value is not None}
    if not updates:
        with connect(settings) as conn:
            row = conn.execute("select * from programs where id=? and channel_id='radiotedu'", (program_id,)).fetchone()
            return dict(row) if row else {"updated": False, "reason": "not_found"}
    with connect(settings) as conn:
        previous = conn.execute("select * from programs where id=? and channel_id='radiotedu'", (program_id,)).fetchone()
        if previous is None:
            return {"updated": False, "reason": "not_found"}
        assignments = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [now_iso(), program_id]
        conn.execute(f"update programs set {assignments}, updated_at=? where id=? and channel_id='radiotedu'", values)
        current = conn.execute("select * from programs where id=? and channel_id='radiotedu'", (program_id,)).fetchone()
        conn.execute(
            """
            insert into schedule_revisions (
                program_id, old_start_time, old_end_time, old_days_of_week,
                new_start_time, new_end_time, new_days_of_week, reason, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                program_id,
                previous["start_time"],
                previous["end_time"],
                previous["days_of_week"],
                current["start_time"],
                current["end_time"],
                current["days_of_week"],
                "dashboard program edit",
                now_iso(),
            ),
        )
        log_event(conn, "info", "Program edited from dashboard.", {"program_id": program_id, "fields": sorted(updates)})
        conn.commit()
        return dict(current)


def metrics(settings: Settings) -> dict:
    with connect(settings) as conn:
        listener_count = conn.execute("select count(*) from listener_events").fetchone()[0]
        feedback_count = conn.execute("select count(*) from listener_events where event_type='feedback'").fetchone()[0]
    return {
        "local_listeners": listener_count if listener_count else None,
        "popularity": None,
        "average_session": None,
        "feedback_count": feedback_count,
    }


def recent_listener_messages(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
            """
            select created_at, metadata_json
            from listener_events
            where event_type='feedback'
            order by created_at desc, id desc
            limit 25
            """
        ).fetchall()
    messages = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        content = " ".join(str(metadata.get("text", "")).split())
        source = " ".join(str(metadata.get("source", "dashboard")).split()) or "dashboard"
        if content:
            messages.append({"content": content, "source": source, "created_at": row["created_at"]})
    return messages


def recent_incidents(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
            """
            select id, component, severity, status, summary, created_at, updated_at
            from incidents
            where status='open'
            order by case severity when 'critical' then 0 when 'warning' then 1 else 2 end, updated_at desc
            limit 6
            """
        ).fetchall()
    return rows_to_dicts(rows)


def recent_autonomous_tasks(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
            """
            select id, task_type, component, title, status, priority, attempts, created_at, updated_at
            from autonomous_tasks
            where status in ('queued', 'running')
            order by priority desc, created_at asc
            limit 6
            """
        ).fetchall()
    return rows_to_dicts(rows)


def observability(settings: Settings, agent: RadioAgent) -> dict:
    now = datetime.now(timezone.utc)
    with connect(settings) as conn:
        ready = conn.execute("select count(*) from announcement_queue where status='ready'").fetchone()[0]
        used = conn.execute("select count(*) from announcement_queue where status='used'").fetchone()[0]
        failed = conn.execute("select count(*) from announcement_queue where status='failed'").fetchone()[0]
        generated = conn.execute("select count(*) from generated_clips").fetchone()[0]
        errors = rows_to_dicts(
            conn.execute(
                "select message, created_at from agent_logs where level='error' order by created_at desc, id desc limit 5"
            ).fetchall()
        )
        restarts = conn.execute("select value from station_metrics where key='supervisor_restarts'").fetchone()
    return {
        "uptime_seconds": int((now - STARTED_AT).total_seconds()),
        "announcement_prebuffer": {
            "ready": int(ready),
            "used": int(used),
            "failed": int(failed),
            "required": int(settings.min_ready_announcements),
            "ready_to_broadcast": int(ready) >= int(settings.min_ready_announcements),
        },
        "generated_clips": int(generated),
        "recent_errors": errors,
        "supervisor_restarts": int(restarts["value"]) if restarts else 0,
        "playback_now": agent.playback.state(),
    }


def top_songs(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
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
    return rows_to_dicts(rows)


def top_genres(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute(
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
    return rows_to_dicts(rows)


def recent_logs(settings: Settings) -> list[dict]:
    with connect(settings) as conn:
        rows = conn.execute("select level, message, metadata_json, created_at from agent_logs order by created_at desc, id desc limit 50").fetchall()
    logs = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except Exception:
            item["metadata"] = {}
        logs.append(item)
    return logs


def health(settings: Settings, agent: RadioAgent) -> dict:
    llm_runtime = ollama_runtime_status(settings)
    llm_setup = check_ollama_setup(settings, runtime=llm_runtime)
    return {
        "database": "ok" if Path(settings.database_path).exists() else "missing",
        "llm": settings.ollama_model,
        "llm_runtime": llm_runtime,
        "llm_setup": llm_setup,
        "tts": getattr(agent.tts, "provider_name", settings.tts_provider),
        "search": settings.search_provider,
        "weather": settings.weather_provider if settings.weather_enabled else "disabled",
        "playback": agent.playback.health(),
        "website_sync": website_sync_health(settings)["health"],
    }


app = create_app()


if __name__ == "__main__":
    settings = Settings.from_env()
    uvicorn.run("backend.app:app", host=settings.api_host, port=settings.api_port, reload=False)
