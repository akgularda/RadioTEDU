# Website Server Codex Prompt

```text
You are Codex on the RadioTEDU website server.

Repository:
https://github.com/akgularda/RadioTEDU

Goal:
Host the public RadioTEDU dashboard at https://radiotedu.com/ai. This server does not own the music library and does not control playback. It receives sanitized snapshots from the broadcast computer and displays a public, Andon-style, single-channel dashboard with a live stream player.

Hard constraints:
- Not Streamlit.
- Use the project’s React/Vite frontend and FastAPI backend.
- Exactly one public channel card: RadioTEDU.
- No admin controls on the public page.
- No start/stop/skip/rescan buttons.
- No logs, incidents, internal autonomous tasks, local file paths, or secrets.
- No financial features or money-like metrics.
- No invented listener counts, invented popularity, invented play history, invented songs, or invented now-playing data.
- If the broadcast computer stops syncing, show an honest offline/waiting state.

Initial setup:
1. Clone/pull:
   https://github.com/akgularda/RadioTEDU
2. Create `.env` from `.env.example`.
3. Set:
   PUBLIC_DASHBOARD_ENABLED=true
   PUBLIC_DASHBOARD_ROUTE=/ai
   PUBLIC_SYNC_TOKEN=<same shared secret used by broadcast computer>
   PUBLIC_STREAM_URL=<public Icecast/Liquidsoap stream URL>
   SNAPSHOT_TTL_SECONDS=30
   AUTONOMY_ENABLED=false
   PLAYBACK_BACKEND=simulate
4. Install and verify:
   pip install -r requirements.txt
   npm install
   python -m pytest tests/backend -q
   npm test
   npm run build

Implementation tasks:
- Serve FastAPI behind the production web server.
- Serve the Vite build for `/ai`.
- Keep `/api/public/status` reachable by the frontend.
- Keep CORS/proxy config same-domain friendly.
- Confirm the broadcast computer can POST snapshots from its network.
- Confirm the stream player can play the configured public stream URL.
- Keep the public API sanitized: no local paths, logs, secrets, incidents, autonomous tasks, or operator controls.

Verification:
- `python -m pytest tests/backend -q` passes.
- `npm test` passes.
- `npm run build` passes.
- Visiting `https://radiotedu.com/ai` shows one RadioTEDU public card.
- With no snapshot, the page says it is waiting/offline.
- With a fresh snapshot, the page shows real now-playing and schedule.
- Listener counts change only from real browser sessions.
- No private/admin/financial fields appear in the public UI or JSON.
```
