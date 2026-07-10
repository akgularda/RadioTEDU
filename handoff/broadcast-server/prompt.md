# RadioTEDU Broadcast Server Codex Prompt

You are Codex on the RadioTEDU broadcast computer.

Repository:
https://github.com/akgularda/RadioTEDU

Goal:
Run the real RadioTEDU broadcast machine. This machine owns the music library, AI host, Qwen/Ollama, TTS, announcement prebuffer, playback, Liquidsoap/Icecast source, and snapshot push to the website server. It must stream to the `/ai` mount and push sanitized public state to `radiotedu.com/ai`.

Machine boundary:
- This prompt runs on the broadcast computer, not on the separate build workstation.
- Clone or update the GitHub repository here and install the runtime dependencies here.
- The current installer is a UI-shell-only build, not a working broadcast runtime: it omits the Python backend/runtime files, and its packaged `file://` frontend does not yet have a verified HTTP API origin. Do not deploy it for live operation until packaging and API-origin handling are fixed.
- After any packaging fix, require an end-to-end packaged-app smoke test: launch the installed UI, confirm the UI itself renders live health from `/api/status` without `file://`/CORS errors, and verify a safe read-only admin view. A separate backend health probe alone is not sufficient.
- Before running a supplied installer, verify its SHA-256 against the build handoff and inspect its Authenticode status. If it is unsigned, report that clearly and follow the operator's security policy; never disable system-wide protections.
- The current source checkout is the authoritative live-operation path: the broadcast services and hardware integrations run from this repository unless a verified self-contained runtime package is supplied.
- Never depend on the build workstation for music files, audio devices, AI/TTS, streaming, or website synchronization.

Secret handling:
- Obtain every secret from the gitignored repo-root `.env` file or an externally injected service environment/secret store.
- Never echo, paste into chat/output, log, or commit a secret; redact command output before sharing it.
- Treat any credential that has ever been committed as compromised: rotate it at the owning service and update the runtime secret store without printing the old or new value.

Andon-inspired product target:
- Preserve the repo's compact, single-channel, information-dense public listener experience inspired by Andon FM.
- Keep the original RadioTEDU branding and do not copy Andon Labs branding, colors, assets, or exact layout.

Repository setup:
1. Clone the repository if absent, then fetch without deploying a mutable branch tip:
   ```bash
   git clone https://github.com/akgularda/RadioTEDU
   cd RadioTEDU
   git fetch --tags --prune
   git status --short
   git checkout --detach <approved-release-tag-or-full-commit-sha>
   git rev-parse HEAD
   ```
   Stop if the tree is dirty or the approved revision is unavailable. Record the full deployed SHA and the currently known-good rollback SHA. Never update the working tree that currently owns live air; stage and verify a separate checkout before cutover.

2. Create `.env` from `.env.example` if needed.

Core config:
```env
MUSIC_DIR=F:/Songs/Jazz
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_URL=http://127.0.0.1:11434
PLAYBACK_BACKEND=liquidsoap
AUTONOMY_ENABLED=true
MIN_READY_ANNOUNCEMENTS=5
MAX_READY_ANNOUNCEMENTS=8
NEWS_ENABLED=true
WEATHER_ENABLED=true
```

TTS:
```env
TTS_PROVIDER=qwen
QWEN_TTS_COMMAND=<your real Qwen TTS command wrapper>
FALLBACK_TTS_PROVIDER=sapi
```

Liquidsoap/Icecast:
```env
LIQUIDSOAP_ENABLED=true
LIQUIDSOAP_QUEUE_PATH=data/liquidsoap/queue.m3u
LIQUIDSOAP_SCRIPT_PATH=data/liquidsoap/radiotedu.liq
LIQUIDSOAP_COMMAND=liquidsoap
LIQUIDSOAP_HOST=<correct Icecast host/IP>
LIQUIDSOAP_PORT=8001
LIQUIDSOAP_MOUNT=/ai
LIQUIDSOAP_ICECAST_PASSWORD=<existing Icecast source password>
ICECAST_HOST=<correct Icecast host/IP>
ICECAST_PORT=8001
ICECAST_MOUNT=/ai
ICECAST_PASSWORD=<same Icecast source password>
```

External broadcast prerequisites:
- Install/provision Liquidsoap separately; confirm the configured `LIQUIDSOAP_COMMAND` resolves and report its version.
- Install or reach a separately managed Icecast server; confirm its host/port, `/ai` mount, and matching source credential from the runtime secret store.
- Confirm the broadcast computer can reach Icecast and that the website's HTTPS stream proxy can reach the mount.
- Run `/api/liquidsoap/verify` successfully before `/api/liquidsoap/start` or `/api/air/start`. Do not go live when any prerequisite is missing.

Website sync:
```env
PUBLIC_SYNC_URL=https://radiotedu.com/api/public/snapshot
PUBLIC_SYNC_TOKEN=<same shared secret configured on website server>
PUBLIC_STREAM_URL=https://radiotedu.com/live.mp3
PUBLIC_SYNC_INTERVAL_SECONDS=10
```

Admin API protection:
```env
API_HOST=127.0.0.1
ADMIN_API_TOKEN=
```

An empty token is allowed only while the API is strictly loopback-only and blocked from remote access by the host firewall. If the API must bind beyond loopback, stop first: generate a strong out-of-repo token, securely provision the same value to the admin client's `radiotedu_admin_token` local-storage key on the trusted operator machine, restrict the firewall/proxy to trusted operator addresses, and verify unauthenticated mutations return `401` while authorized controls work. The current UI has no token-settings screen, so do not expose it remotely until that provisioning is completed and tested.

Important network task:
Find the correct IP address for the Broadcast Wall app / Icecast source target.
- Inspect the machine network interfaces.
- Determine which IP the Broadcast Wall app or Icecast server expects.
- Use that IP for `LIQUIDSOAP_HOST` / `ICECAST_HOST` if Icecast is not local.
- Confirm the mount is exactly `/ai`.
- Confirm the configured source password matches the Icecast server; do not print or commit it.
- Confirm the website server exposes the Icecast `/ai` mount through the HTTPS `PUBLIC_STREAM_URL`; do not send browsers to a plain-HTTP IP/port stream.
- Do not guess silently. Log the detected candidate IPs and choose the reachable one.
- If multiple candidates exist, test connectivity to the Icecast port and use the reachable one.

Install/verify in an isolated environment. `requirements.txt` contains open-ended bounds and is not a production lock; require an approved pinned, hash-verified Python lock that includes the test tools before live cutover. If it is absent, stop and report the blocker.
```bash
python -m venv .venv
# Activate .venv for this operating system before continuing.
python -m pip install --require-hashes -r <approved-python-lock-file>
npm ci
python scripts/check_ollama.py --install --start --pull
python scripts/scan_music.py
python -m pytest tests/backend -q
npm test
npm run build
```

Source runtime startup:
1. Run the live backend independently of the admin window under the repo's watchdog (or an equivalent Windows service/scheduled task):
   ```bash
   python scripts/run_station_forever.py --root <absolute-path-to-RadioTEDU>
   ```
2. Wait for `http://127.0.0.1:8000/api/status` to return `200` before calling any control endpoint.
3. Launch the source admin UI as a client of that supervised backend. On PowerShell:
   ```powershell
   $env:RADIOTEDU_MANAGE_BACKEND='0'
   npm run desktop:dev
   ```
   On Bash:
   ```bash
   RADIOTEDU_MANAGE_BACKEND=0 npm run desktop:dev
   ```
4. Verify the admin UI can read `/api/status`. Closing the admin window must not stop the supervised live backend.
5. Use plain `npm run desktop:dev` (which manages its own backend) only for setup/interactive testing, never as the sole owner of a 24/7 live broadcast.

Cutover and rollback:
- Stage the approved revision, isolated Python environment, Node dependencies, and config in a separate checkout while the known-good revision remains untouched.
- Run the full tests, `python scripts/run_broadcast_computer.py --check-only`, `python scripts/smoke_broadcast.py --json`, TTS test, Liquidsoap verification, website-sync check, and a non-air admin UI check before the maintenance window.
- Record the old service command, full rollback SHA, environment/config backup location, and rollback health checklist.
- Switch the supervised service only during an approved maintenance window. If backend health, audio output, Icecast mount, snapshot sync, or admin control fails, stop the new service, restore the previous checkout/environment/service command, restart it, and re-run the rollback health checklist before resuming air.

Broadcast workflow:
1. Start or verify Ollama.
2. Pull/verify `qwen3.5:4b`.
3. Scan `MUSIC_DIR=F:/Songs/Jazz`.
4. Confirm playable tracks > 0.
5. Render Liquidsoap config:
   `POST /api/liquidsoap/render`
6. Verify Liquidsoap/Icecast:
   `POST /api/liquidsoap/verify`
   This must confirm:
   - queue file is readable
   - script references queue
   - Icecast mount `/ai` is reachable/active when running
7. Start Icecast/Liquidsoap output:
   `POST /api/liquidsoap/start`
8. Start air:
   `POST /api/air/start`

Hard broadcast constraints:
- Exactly one channel: RadioTEDU.
- Programs are schedule blocks, not stations.
- Never invent tracks, artists, play history, listener counts, analytics, donation/support data, or financial features.
- Use real files from `F:/Songs/Jazz`.
- Maintain 5-8 prepared announcements.
- Do not block live playback waiting for the 4B model.
- Generate announcements 4-5 songs ahead.
- If AI is unavailable, try to start/fix/pull Ollama/Qwen instead of silently living in fallback.
- Fallback is dead-air prevention only.
- Weather/news/song-context announcements must be sourced. Do not invent facts.
- Snapshot push must never include local paths, secrets, logs, incidents, internal task details, or generated private file paths.

Admin app:
- Run the local admin dashboard.
- Use it to see health, prebuffer, TTS, Liquidsoap, website sync, fallback playlist, weekly strategy, and logs.
- Use Run Air / Stop Air / Skip / Rescan from the admin app.
- Use Verify Icecast Air before going live.
- Use Clip Latest Segment only for real generated clips.

Public sync:
- Every few seconds, push sanitized status to `https://radiotedu.com/api/public/snapshot`.
- Header: `X-RadioTEDU-Sync-Token: <shared secret>`.
- If website sync fails, keep local broadcast running and log locally only.

Final verification:
- `/api/status` shows music indexed.
- `/api/status` shows prebuffer ready >= 5.
- `/api/liquidsoap/verify` reports queue readable.
- Icecast `/ai` mount is reachable.
- `/api/air/start` starts without dead air.
- `https://radiotedu.com/ai` shows real now-playing after snapshot sync.
- No local file paths appear on `radiotedu.com/ai`.
- No fake or financial fields appear anywhere public.
