# RadioTEDU Website Server Codex Prompt

You are Codex on the RadioTEDU website server.

Repository:
https://github.com/akgularda/RadioTEDU

Goal:
Deploy the public RadioTEDU listener page at `https://radiotedu.com/ai`. This server does not own music, AI generation, TTS, local playback, Liquidsoap source, or broadcast control. It only hosts the public dashboard, receives sanitized snapshots from the broadcast computer, tracks approximate active public player sessions, and serves the public stream player.

Andon-inspired design target:
- Keep the compact, single-channel listener-page concept and information density associated with Andon FM.
- Preserve the original RadioTEDU name, blue visual identity, typography, cover art, and copy.
- Do not clone Andon Labs branding, colors, assets, or exact layout.
- This must feel like a polished radio listener page, not an admin dashboard or debug console.

Hard constraints:
- Exactly one public channel: `RadioTEDU`.
- Public route must be `/ai`.
- Not Streamlit.
- Use the repo's FastAPI backend and Vite/React frontend.
- Do not show admin controls.
- Do not expose logs, incidents, local file paths, generated private clip paths, secrets, API tokens, strategy internals, or operator-only controls.
- No financial features or donation/support wording. Never invent listener counts, analytics, songs, or now-playing data.
- If the broadcast computer stops syncing, show the honest waiting/offline state.
- Obtain every secret from the gitignored repo-root `.env` file or an externally injected service environment/secret store. Never echo, paste into chat/output, log, or commit a secret; redact command output before sharing it.

Setup:
1. Clone the repository if absent, then fetch without deploying a mutable branch tip:
   ```bash
   git clone https://github.com/akgularda/RadioTEDU
   cd RadioTEDU
   git fetch --tags --prune
   git status --short
   git checkout --detach <approved-release-tag-or-full-commit-sha>
   git rev-parse HEAD
   ```
   Stop if the tree is dirty or the approved revision is unavailable. Record the full deployed SHA and the currently known-good rollback SHA before changing the service.

2. Create `.env` from `.env.example` if needed.

3. Configure:
   ```env
   API_HOST=127.0.0.1
   PUBLIC_SYNC_TOKEN=<same shared secret used by broadcast computer>
   PUBLIC_STREAM_URL=https://radiotedu.com/live.mp3
   SNAPSHOT_TTL_SECONDS=30
   AUTONOMY_ENABLED=false
   PLAYBACK_BACKEND=simulate
   LIQUIDSOAP_ENABLED=false
   ADMIN_API_TOKEN=<strong server-only random token>
   ```

4. Install into an isolated environment. `requirements.txt` contains open-ended bounds and is not a production lock; before live cutover, require an approved pinned, hash-verified Python lock that includes the test tools. If that lock is absent, stop and report the reproducibility blocker.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --require-hashes -r <approved-python-lock-file>
   npm ci
   ```

5. Verify:
   ```bash
   python -m pytest tests/backend -q
   npm test
   npm run build
   ```

6. Stage this exact revision in a separate release directory and virtual environment. Validate the reverse-proxy configuration, `/ai`, public API smoke checks, and HTTPS stream before switching traffic. Keep the prior release directory, service definition, redacted config backup, and full rollback SHA until post-cutover health checks pass; restore them immediately if checks fail.

Implementation/deployment tasks:
- Serve FastAPI behind the production web server for `radiotedu.com`.
- Serve the Vite build and make sure `https://radiotedu.com/ai` returns the React public dashboard.
- Bind FastAPI to loopback and configure the reverse proxy to expose only `/ai`, `/assets/*`, public image assets under `/static/generated/covers/*`, `/api/public/*`, and the HTTPS stream proxy `/live.mp3`. Explicitly deny `/static/generated/tts/*`, `/static/generated/clips/*`, and every admin/status/control/log/program endpoint at the public proxy.
- Ensure `/api/public/status` is reachable from the same domain.
- Ensure `POST /api/public/snapshot` accepts only requests with `X-RadioTEDU-Sync-Token: <shared secret>`.
- Confirm missing/wrong sync token returns `401`.
- Confirm `/api/public/status` never exposes local paths, secrets, logs, incidents, admin data, or financial terms.
- Confirm public listener sessions work:
  - `POST /api/public/session/start`
  - `POST /api/public/session/heartbeat`
  - `POST /api/public/session/end`
- Rate-limit the public session endpoints and add basic abuse controls at the proxy.
- Label current listeners as an approximate count of recently active player sessions, not authenticated unique people. If trustworthy unique-listener metrics are required, implement server-issued/signed session IDs before making that claim.
- Keep production frontend/API traffic same-origin through the reverse proxy. Do not enable wildcard CORS; retain localhost-only CORS solely for local development.
- Reverse-proxy the Icecast `/ai` mount to `https://radiotedu.com/live.mp3` (or another same-origin HTTPS URL) with TLS. Never point the HTTPS page at an `http://` IP/port stream.
- Confirm the browser audio player points to the HTTPS `PUBLIC_STREAM_URL` without mixed-content errors.
- If the stream URL is not reachable yet, keep the page online but show honest waiting/stream unavailable state.

Useful commands:
```bash
python -m backend.app
npm run build
```

Production checks:
- Visit `https://radiotedu.com/ai`.
- With no snapshot, it says waiting for broadcast computer.
- After the broadcast computer posts a snapshot, it shows real now playing, current program, schedule, top songs/genres, share card, and clearly labeled approximate active-player session metrics.
- No admin controls appear.
- No local file path appears.
- No financial wording appears.

Do not invent data. If there is no snapshot, no music, no listeners, or no stream, show no-data/waiting states.
