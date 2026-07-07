# RadioTEDU Website Server Runbook

This machine hosts the public listener page at `radiotedu.com/ai`. It receives
sanitized snapshots from the broadcast computer and tracks real public listener
sessions. It does not own the music library and it does not control playback.

## Hard Rules

- Not Streamlit.
- Use the FastAPI backend and React/Vite frontend from this repository.
- Exactly one public channel card: RadioTEDU.
- No admin controls.
- No start, stop, skip, rescan, Test TTS, strategy, incident, or log views.
- No local file paths, secrets, private task details, or internal logs.
- No financial features or money-like stats.
- No synthetic listener counts, synthetic play history, invented songs, or invented now-playing data.
- If snapshots expire, show an honest offline or waiting state.

## Setup

Clone or pull the repository:

```bash
git clone https://github.com/akgularda/RadioTEDU.git /opt/RadioTEDU
cd /opt/RadioTEDU
```

Create `.env` from `.env.example`, then set:

```env
PUBLIC_DASHBOARD_ENABLED=true
PUBLIC_DASHBOARD_ROUTE=/ai
PUBLIC_SYNC_TOKEN=replace-with-shared-secret
PUBLIC_STREAM_URL=https://radiotedu.com/ai
SNAPSHOT_TTL_SECONDS=30
AUTONOMY_ENABLED=false
PLAYBACK_BACKEND=simulate
```

Install and verify:

```bash
pip install -r requirements.txt
npm install
python -m pytest tests/backend -q
npm test
npm run build
```

## Public API

The website server exposes public-safe endpoints:

```text
POST /api/public/snapshot
GET /api/public/status
POST /api/public/session/start
POST /api/public/session/heartbeat
POST /api/public/session/end
```

Snapshot writes must include:

```text
X-RadioTEDU-Sync-Token: <shared secret>
```

Missing or wrong token requests must be rejected. Public reads must never return
private fields from the broadcast computer.

## Session Metrics

Listener metrics are real-only:

- Current listeners come from active browser sessions.
- Average session length comes from ended real sessions.
- Popularity is derived from real engagement or shown as `No data`.
- No synthetic counters or filler values.

## Public Page

The listener page at `radiotedu.com/ai` should be a compact Andon-style public
card for one station:

- RadioTEDU logo and cover image.
- Live stream player using `PUBLIC_STREAM_URL`.
- Live dot when the fresh snapshot says the broadcast is live.
- Now playing.
- Current program and next schedule.
- Schedule progress.
- Top songs and top genres from real play history.
- Real listener/session stats.
- Offline/waiting state when no fresh snapshot exists.

No admin controls means no operator buttons, logs, paths, incidents, internal
health details, or autonomy controls appear on this page.

## Deployment Shape

Run FastAPI behind the production web server and serve the Vite build for `/ai`.
The same domain should proxy API calls to FastAPI so the frontend can call:

```text
/api/public/status
/api/public/session/start
/api/public/session/heartbeat
/api/public/session/end
```

Allow the broadcast computer to reach:

```text
POST /api/public/snapshot
```

Use TLS on the public domain. Keep `PUBLIC_SYNC_TOKEN` server-side only.

## Smoke Test

After deployment, run:

```bash
python scripts/smoke_public_server.py --base-url https://radiotedu.com --token "$PUBLIC_SYNC_TOKEN" --json
```

Expected results:

- `/api/public/status` is reachable.
- `session/start`, heartbeat, and end work.
- A valid snapshot token is accepted.
- A wrong token is rejected.
- Expired snapshots show offline/waiting state in public JSON.

## Troubleshooting

- If the page is offline, check whether the broadcast computer is pushing fresh snapshots.
- If listener counts do not move, inspect session endpoint proxying.
- If the stream player fails, check `PUBLIC_STREAM_URL` and the Icecast `/ai` mount.
- If snapshot POST returns unauthorized, rotate and match `PUBLIC_SYNC_TOKEN` on both machines.
