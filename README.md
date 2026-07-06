# RadioTEDU

RadioTEDU is a local-first AI radio station that runs one channel only: `RadioTEDU`. Programs such as Morning Signal, Campus Frequencies, Night Lab, and Weekend Transmission are scheduled blocks inside that channel.

There is no demo mode and no invented listening data. Add your own local music before starting playback. If no playable music exists, the backend and dashboard still run, the station stays idle, and the dashboard asks you to add music and rescan.

## Quickstart

```bash
cd RadioTEDU
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
mkdir -p data/music
python scripts/scan_music.py
python -m backend.app
```

In another terminal:

```bash
npm run dev
```

Open `http://localhost:5173`.

## Current Music Library

The portable default is:

```env
MUSIC_DIR=data/music
```

For this workstation you can point RadioTEDU at the Jazz library:

```env
MUSIC_DIR=F:/Songs/Jazz
```

The scanner walks the directory recursively, stores metadata in SQLite, deduplicates by file path, and keeps selection queries limited so large FLAC libraries stay manageable on an 8 GB CPU-only machine.

## Local AI

The portable default LLM is Ollama with `qwen2.5:0.5b-instruct`:

```bash
ollama pull qwen2.5:0.5b-instruct
```

For this workstation, the live `.env` uses the stronger local 4B model you selected:

```env
OLLAMA_MODEL=qwen3.5:4b
```

Check the local runtime without installing or pulling anything:

```bash
python scripts/check_ollama.py
python scripts/check_ollama.py --json
```

The checker reports whether the Ollama CLI exists, whether the server is reachable, and whether the configured model is installed. It returns suggested commands such as:

```bash
winget install Ollama.Ollama
ollama serve
ollama pull qwen3.5:4b
```

It never installs, starts, or downloads anything unless you explicitly ask it to:

```bash
python scripts/check_ollama.py --pull
```

To explicitly bootstrap the local Windows runtime in one command:

```bash
python scripts/check_ollama.py --install --start --pull
```

The DJ prompt is intentionally small and JSON-only. If Ollama is unavailable or returns invalid JSON, RadioTEDU picks from real candidate tracks deterministically and writes a short deterministic DJ line.

The dashboard separates configured model from runtime health. `health.llm` shows the requested model name, while `health.llm_runtime` checks the Ollama `/api/tags` endpoint and reports whether the server is reachable and whether the configured model is installed. The backend also exposes `GET /api/setup/ollama` for the same setup guidance used by the checker script.

## Autonomous Orchestrator

RadioTEDU can keep the station running continuously while the backend process is alive:

```env
AUTONOMY_ENABLED=true
AUTONOMY_TICK_SECONDS=30
STRATEGY_INTERVAL_MINUTES=240
```

The orchestrator is intentionally local and conservative. It keeps one RadioTEDU channel alive, refills the queue from real local tracks, records real play history, refreshes a long-horizon strategy note, edits the program schedule in SQLite, stores listener feedback as local memory, writes self-reviews, and drafts local segment notes. It also persists a structured strategy policy with goals, next actions, real library signals, and constraints so the dashboard can show what the agent is optimizing. It does not create extra channels, invent analytics, or operate external accounts.

Listener feedback submitted through the dashboard is sanitized for the non-financial station scope, stored as local autonomy memory, and answered with a queued local TTS reply. This works even before music is indexed; it does not invent listener counts or popularity.

Use the dashboard Start and Stop buttons to start or stop the in-process runner. Stop shuts down the runner and leaves the backend available.

For a watchdog that restarts the backend if it exits, run:

```bash
python scripts/run_station_forever.py --root F:/RTAI/RadioTEDU --frontend
```

On Windows, you can register that watchdog at login:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows_task.ps1 -ProjectRoot F:\RTAI\RadioTEDU -WithFrontend
```

### Announcement prebuffer

For weaker machines, RadioTEDU can build a spoken-announcement buffer before it allows broadcast startup:

```env
MIN_READY_ANNOUNCEMENTS=5
MAX_READY_ANNOUNCEMENTS=8
```

The agent fills `announcement_queue` with ready TTS clips, starts playback only when the ready count reaches the minimum, then consumes one prepared announcement before each real track. When playable tracks exist, each prepared announcement stores the planned real `track_id`, title, artist, genre, and decision reason in `metadata_json`, so the spoken intro and the song stay paired. If Ollama is unavailable, fallback intros still use real search/RSS snippets when supplied, then local metadata such as album, genre, mood, or duration; they do not invent song facts. Legacy generic agent prebuffer rows are retired as `stale` once real track-bound announcements can be prepared. This avoids generating every DJ line at the last second.

Autonomous ticks also maintain the prebuffer even when another item, such as a listener reply, is already queued. The tick response includes the current prebuffer snapshot so operators can see whether the station is ready to broadcast.

## TTS

Qwen TTS is configured through a command template:

```env
QWEN_TTS_COMMAND=python scripts/qwen_tts_command.py --text {text} --out {output_path} --voice {voice}
```

The wrapper uses `QWEN_TTS_HTTP_URL` when you have a Qwen TTS HTTP endpoint that returns WAV bytes. If no endpoint is configured, it exits quickly and the configured fallback provider handles the clip.

On Windows, set the fallback to SAPI for real local speech when the Qwen command is empty:

```env
FALLBACK_TTS_PROVIDER=sapi
```

The dummy provider still exists as the final reliability fallback. It writes a short silent WAV and a `.txt` sidecar containing the narration text.

## Search

RSS is the default lightweight search provider:

```env
SEARCH_PROVIDER=rss
RSS_FEEDS_PATH=data/rss_feeds.json
```

To use SearXNG:

```env
SEARCH_PROVIDER=searxng
SEARXNG_URL=http://localhost:8080
```

Search is throttled by `WEB_SEARCH_INTERVAL_MINUTES` and never blocks playback.

## Weather

Weather context is optional and real-only. When enabled, RadioTEDU fetches current conditions from Open-Meteo and passes a short summary into the DJ decision prompt; if the provider is disabled, unconfigured, or unreachable, the status payload and dashboard show `No weather data.`.

Portable default:

```env
WEATHER_ENABLED=false
WEATHER_PROVIDER=open_meteo
WEATHER_LOCATION=Ankara
WEATHER_LATITUDE=
WEATHER_LONGITUDE=
WEATHER_INTERVAL_MINUTES=30
```

This workstation can enable Ankara weather with:

```env
WEATHER_ENABLED=true
WEATHER_LOCATION=Ankara
WEATHER_LATITUDE=39.9208
WEATHER_LONGITUDE=32.8541
```

## Public Dashboard And Website Sync

The operator dashboard is local. The public website should use the `/ai` route and the public API only. The broadcast computer pushes sanitized snapshots outward to the website server; the website server does not call into the broadcast computer.

Broadcast computer example:

```env
PUBLIC_SYNC_URL=https://radiotedu.com/api/public/snapshot
PUBLIC_SYNC_TOKEN=change-this-shared-secret
PUBLIC_STREAM_URL=https://radiotedu.com/live.mp3
PUBLIC_SYNC_INTERVAL_SECONDS=10
```

Website server example:

```env
PUBLIC_DASHBOARD_ENABLED=true
PUBLIC_DASHBOARD_ROUTE=/ai
PUBLIC_SYNC_TOKEN=change-this-shared-secret
PUBLIC_STREAM_URL=https://radiotedu.com/live.mp3
SNAPSHOT_TTL_SECONDS=30
AUTONOMY_ENABLED=false
PLAYBACK_BACKEND=simulate
```

Public endpoints:

```text
POST /api/public/snapshot
GET  /api/public/status
POST /api/public/session/start
POST /api/public/session/heartbeat
POST /api/public/session/end
```

Snapshot POSTs require `X-RadioTEDU-Sync-Token`. Public status intentionally excludes local file paths, logs, incidents, autonomous tasks, secrets, and operator controls. Listener counts and average session values are derived only from real browser session events on the website server; empty data is shown as `No data` or `0`, never invented.

The two Codex handoff prompts are stored in:

```text
docs/BROADCAST_COMPUTER_CODEX_PROMPT.md
docs/WEBSITE_SERVER_CODEX_PROMPT.md
```

## Curated RSS News

RadioTEDU can read short news notes from configured RSS feeds:

```env
NEWS_ENABLED=true
NEWS_INTERVAL_MINUTES=60
RSS_FEEDS_PATH=data/rss_feeds.json
```

News is retrieval-first. The agent uses titles/snippets from configured RSS feeds, queues a short announcement in the same prebuffer as DJ/song/weather/listener lines, and skips news if the feed is empty or unreachable. The model must not invent headlines.

## Playback

The portable default playback backend is safe simulation:

```env
PLAYBACK_BACKEND=simulate
```

To use local players:

```env
PLAYBACK_BACKEND=auto
MPV_PATH=mpv
FFPLAY_PATH=ffplay
```

`auto` tries `mpv`, then `ffplay`, and falls back to simulation only if neither player is available. You can also force a player:

```env
PLAYBACK_BACKEND=mpv
```

## Liquidsoap

RadioTEDU can render a Liquidsoap playlist and config without changing the one-channel model:

```env
LIQUIDSOAP_ENABLED=false
LIQUIDSOAP_QUEUE_PATH=data/liquidsoap/queue.m3u
LIQUIDSOAP_SCRIPT_PATH=data/liquidsoap/radiotedu.liq
LIQUIDSOAP_HOST=127.0.0.1
LIQUIDSOAP_PORT=8001
```

Generate the files from the API:

```bash
python - <<'PY'
from backend.config import Settings
from backend.liquidsoap import render_liquidsoap_config
print(render_liquidsoap_config(Settings.from_env()))
PY
```

When `PLAYBACK_BACKEND=liquidsoap`, queued audio paths are appended to the Liquidsoap playlist for an external Liquidsoap process to stream.

## Cover Art

RadioTEDU generates original deterministic square cover art with Python. Refresh assets with:

```bash
python - <<'PY'
from backend.art.cover_generator import generate_covers
from backend.config import Settings
generate_covers(Settings.from_env())
PY
```

The prompts in `backend/art/prompts.py` can also be pasted into an external image generator later.

## Programs

Programs remain schedule blocks inside the one RadioTEDU channel. You can edit start time, end time, days, and vibe from the dashboard. The API is:

```http
PATCH /api/programs/{program_id}
```

Edits are recorded in `schedule_revisions`.

## Observability

The dashboard includes Runtime Watch: announcement prebuffer readiness, uptime, generated clips, recent errors, restart count, and current playback state. These values come from real SQLite/runtime state, not invented analytics.

## Future Streaming

The playback abstraction leaves room for later Liquidsoap or Icecast integration without changing the one-channel data model.
