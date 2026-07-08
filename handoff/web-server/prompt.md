# RadioTEDU Website Server Codex Prompt

You are Codex on the RadioTEDU website server.

Repository:
https://github.com/akgularda/RadioTEDU

Goal:
Deploy the public RadioTEDU listener page at `https://radiotedu.com/ai`. This server does not own music, AI generation, TTS, local playback, Liquidsoap source, or broadcast control. It only hosts the public dashboard, receives sanitized snapshots from the broadcast computer, tracks real public listener sessions, and serves the public stream player.

Hard constraints:
- Exactly one public channel: `RadioTEDU`.
- Public route must be `/ai`.
- Not Streamlit.
- Use the repo's FastAPI backend and Vite/React frontend.
- Do not show admin controls.
- Do not expose logs, incidents, local file paths, generated private clip paths, secrets, API tokens, strategy internals, or operator-only controls.
- No financial features, donation/support wording, fake listeners, fake analytics, fake songs, or fake now-playing data.
- If the broadcast computer stops syncing, show the honest waiting/offline state.

Setup:
1. Clone or pull:
   ```bash
   git clone https://github.com/akgularda/RadioTEDU
   cd RadioTEDU
   ```
   If the repo already exists:
   ```bash
   git pull --ff-only
   ```

2. Create `.env` from `.env.example` if needed.

3. Configure:
   ```env
   PUBLIC_DASHBOARD_ENABLED=true
   PUBLIC_DASHBOARD_ROUTE=/ai
   PUBLIC_SYNC_TOKEN=<same shared secret used by broadcast computer>
   PUBLIC_STREAM_URL=http://<BROADCAST_PUBLIC_OR_TUNNEL_IP>:8001/ai
   SNAPSHOT_TTL_SECONDS=30
   AUTONOMY_ENABLED=false
   PLAYBACK_BACKEND=simulate
   LIQUIDSOAP_ENABLED=false
   ADMIN_API_TOKEN=
   ```

4. Install:
   ```bash
   pip install -r requirements.txt
   npm install
   ```

5. Verify:
   ```bash
   python -m pytest tests/backend -q
   npm test
   npm run build
   ```

Implementation/deployment tasks:
- Serve FastAPI behind the production web server for `radiotedu.com`.
- Serve the Vite build and make sure `https://radiotedu.com/ai` returns the React public dashboard.
- Ensure `/api/public/status` is reachable from the same domain.
- Ensure `POST /api/public/snapshot` accepts only requests with `X-RadioTEDU-Sync-Token: <shared secret>`.
- Confirm missing/wrong sync token returns `401`.
- Confirm `/api/public/status` never exposes local paths, secrets, logs, incidents, admin data, or financial terms.
- Confirm public listener sessions work:
  - `POST /api/public/session/start`
  - `POST /api/public/session/heartbeat`
  - `POST /api/public/session/end`
- Confirm current listeners come only from active browser sessions.
- Configure reverse proxy/CORS so same-domain frontend can call the API.
- Confirm the browser audio player points to `PUBLIC_STREAM_URL`.
- If the stream URL is not reachable yet, keep the page online but show honest waiting/stream unavailable state.

Useful commands:
```bash
python -m backend.app
npm run build
```

Production checks:
- Visit `https://radiotedu.com/ai`.
- With no snapshot, it says waiting for broadcast computer.
- After broadcast computer posts a snapshot, it shows real now playing, current program, schedule, top songs/genres, share card, and public listener metrics.
- No admin controls appear.
- No local file path appears.
- No financial wording appears.

Do not invent data. If there is no snapshot, no music, no listeners, or no stream, show no-data/waiting states.
