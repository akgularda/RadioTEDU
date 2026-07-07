# RadioTEDU Broadcast Computer Runbook

This machine runs the actual local RadioTEDU broadcast. It owns the real music
library, local AI, TTS, Liquidsoap/Icecast output, announcement prebuffer, and
the sanitized snapshot push to the public website.

It is not the public website server. It must never expose local paths, secrets,
logs, incidents, or internal task details to `radiotedu.com/ai`.

## Hard Rules

- Exactly one channel: RadioTEDU.
- Programs are schedule blocks inside RadioTEDU, not separate stations.
- No demo mode, invented songs, invented artists, synthetic play history, synthetic listener counts, or synthetic stats.
- No financial features.
- Use real local music from `MUSIC_DIR=F:/Songs/Jazz` on this machine.
- Keep `MIN_READY_ANNOUNCEMENTS=5` so the AI host works 4-5 songs ahead.
- Run Air should not wait on the model during live playback.

## Setup

Clone or pull the repository:

```powershell
git clone https://github.com/akgularda/RadioTEDU.git F:\RTAI\RadioTEDU
cd F:\RTAI\RadioTEDU
```

Create `.env` from `.env.example`, then set the broadcast values:

```env
MUSIC_DIR=F:/Songs/Jazz
OLLAMA_MODEL=qwen3.5:4b
TTS_PROVIDER=qwen
QWEN_TTS_COMMAND=python scripts/qwen_tts_command.py --text {text} --out {output_path} --voice {voice}
PLAYBACK_BACKEND=liquidsoap
LIQUIDSOAP_ENABLED=true
LIQUIDSOAP_QUEUE_PATH=data/liquidsoap/queue.m3u
LIQUIDSOAP_SCRIPT_PATH=data/liquidsoap/radiotedu.liq
LIQUIDSOAP_COMMAND=liquidsoap
ICECAST_HOST=127.0.0.1
ICECAST_PORT=8001
ICECAST_MOUNT=/ai
PUBLIC_STREAM_URL=https://radiotedu.com/ai
PUBLIC_SYNC_URL=https://radiotedu.com/api/public/snapshot
PUBLIC_SYNC_TOKEN=replace-with-shared-secret
AUTONOMY_ENABLED=true
MIN_READY_ANNOUNCEMENTS=5
MAX_READY_ANNOUNCEMENTS=8
NEWS_ENABLED=true
```

Install and verify:

```powershell
pip install -r requirements.txt
npm install
python scripts/check_ollama.py --install --start --pull
python scripts/scan_music.py
python scripts/run_broadcast_computer.py --check-only
python scripts/smoke_broadcast.py --json
```

## Local Admin App

Start the admin panel as the broadcast application:

```powershell
npm run desktop:dev
```

The Electron app starts the local FastAPI backend unless
`RADIOTEDU_MANAGE_BACKEND=0` is set. Use the local dashboard for operator
actions only.

Expected operator checks before Run Air:

- Music library has real indexed tracks from `F:/Songs/Jazz`.
- Ollama reports the configured Qwen model ready.
- Test TTS succeeds for each program voice.
- Liquidsoap is installed or reachable by `LIQUIDSOAP_COMMAND`.
- Icecast is reachable and the `/ai` mount can become active.
- Public snapshot sync is configured.
- Announcement prebuffer has at least 5 ready items.

Use the dashboard's `Test TTS` button before real air. Use `Run Air` only after
the readiness checklist is green enough for the intended output mode.

## Liquidsoap And Icecast

RadioTEDU renders a Liquidsoap config from environment values and writes a queue
file at `LIQUIDSOAP_QUEUE_PATH`. The queue contains local audio paths for
Liquidsoap only; those paths must never be sent to the public server.

Icecast should expose the public stream mount:

```text
/ai
```

The public website should use `PUBLIC_STREAM_URL`, not a private LAN URL, when
it renders the listener player.

## Snapshot Push

The broadcast backend starts a snapshot pusher automatically when
`PUBLIC_SYNC_URL` and `PUBLIC_SYNC_TOKEN` are configured. It sends only
sanitized public state:

- RadioTEDU channel state.
- Current program.
- Now playing title, artist, and type.
- Schedule and next program.
- Top songs and genres derived from real play history.
- Public stream URL/status.
- Public cover URLs.
- Timestamp.

It must not send:

- `F:/Songs/Jazz` or any other local path.
- Secrets or `.env` values.
- Logs, incidents, or autonomous task internals.
- Generated private clip paths.

If website sync fails, the broadcast continues and the failure is logged locally.

## News Reading

When `NEWS_ENABLED=true`, news must come only from configured RSS feeds. The
agent can summarize retrieved source text and queue short announcements into
the same prebuffer used for song, weather, and listener announcements.

If RSS data is missing, stale, or unreachable, skip news. Do not invent news.

## Verification

Run before real air:

```powershell
python -m pytest tests/backend -q
npm test
npm run build
python scripts/run_broadcast_computer.py --check-only
python scripts/smoke_broadcast.py --json
```

The target healthy state is:

- `/api/status` shows Qwen ready.
- Prebuffer has at least 5 ready announcements.
- A real track from `F:/Songs/Jazz` can be queued.
- Liquidsoap can feed Icecast `/ai`.
- Snapshot push reaches `POST /api/public/snapshot`.

## Troubleshooting

- If Qwen is missing, run `python scripts/check_ollama.py --install --start --pull`.
- If no tracks are indexed, check `MUSIC_DIR=F:/Songs/Jazz` and run `python scripts/scan_music.py`.
- If Run Air blocks, inspect the Air Readiness panel instead of forcing playback.
- If Liquidsoap is missing, install it or switch temporarily to simulation for local tests.
- If public sync fails, verify `PUBLIC_SYNC_URL`, `PUBLIC_SYNC_TOKEN`, and website reachability.
