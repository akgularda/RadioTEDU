# RadioTEDU Next TODOs

This is the next implementation backlog for turning the current MVP into a real broadcast-computer product plus a safe public website.

## P0 - Make The Admin Panel A Real Desktop Program

- [x] Convert the Electron shell into a real local operator app, not only a `127.0.0.1:5173` wrapper.
- [x] Start the FastAPI backend from Electron when it is not already running.
- [ ] Serve the built React admin UI from the desktop app or start the local frontend intentionally in dev mode.
- [ ] Show a clear local setup screen when backend startup fails.
- [x] Stop child processes cleanly when the desktop app exits.
- [x] Add desktop app logs for backend/frontend startup failures.
- [x] Add tests that verify `desktop/main.cjs` manages backend process lifecycle or documents external-process mode explicitly.

Acceptance:
- Double-clicking the admin app opens a usable RadioTEDU operator panel.
- The user does not need to manually start backend/frontend first.
- Closing the app does not leave orphaned backend/frontend child processes.

## P0 - One Broadcast Computer Runner

- [x] Add one command for the broadcast machine, for example `scripts/run_broadcast_computer.py`.
- [ ] Start or verify backend.
- [ ] Start or verify the autonomous orchestrator.
- [x] Start or verify the public snapshot pusher when configured.
- [x] Render/check Liquidsoap config.
- [x] Check Icecast reachability and mount state.
- [x] Check Ollama and configured Qwen model readiness.
- [ ] Check TTS command readiness.
- [ ] Check music library readiness.
- [ ] Keep running with local-only logs and backoff.

Acceptance:
- The broadcast computer can be started with one script.
- Website sync failures never stop the broadcast loop.
- Missing dependencies are reported explicitly.

## P0 - Wire Snapshot Pusher Into Runtime

- [x] Start `PublicSnapshotPusher` automatically on backend startup when `PUBLIC_SYNC_URL` and `PUBLIC_SYNC_TOKEN` are configured.
- [x] Stop the pusher cleanly on backend shutdown.
- [ ] Keep `scripts/push_public_snapshot.py` as a manual/debug tool.
- [x] Add exponential backoff for repeated website sync failures.
- [ ] Add admin status fields:
  - [x] last snapshot push time
  - [x] last snapshot push result
  - [x] consecutive failures
  - [x] configured/not configured
- [x] Add tests that verify no pusher starts without token/url.
- [ ] Add tests that verify snapshot push failure does not stop broadcast.

Acceptance:
- Broadcast backend pushes sanitized public state every 5-10 seconds when configured.
- Public website eventually shows offline/waiting when snapshots expire.
- No local paths, secrets, logs, or internal task data are pushed.

## P0 - Complete Real Liquidsoap/Icecast Air Path

- [x] Make the agent write a real Liquidsoap queue file.
- [x] Queue sequence must include prebuffered announcement clips plus real tracks.
- [ ] Use real file paths only locally; never expose them to public snapshot/API.
- [ ] Verify Liquidsoap can read the queue file.
- [ ] Verify Icecast mount `/ai` becomes reachable.
- [ ] Add health fields:
  - [x] liquidsoap installed
  - [x] liquidsoap running
  - [x] queue file exists
  - [x] queue length
  - [x] Icecast reachable
  - [x] mount active
- [ ] Add a smoke test script for local stream readiness.

Acceptance:
- Clicking `Run Air` starts real stream output when Liquidsoap/Icecast are configured.
- If Liquidsoap/Icecast are missing, `Run Air` refuses fake live state and shows exact setup steps.
- The public stream URL plays the same output.

## P0 - Harden Announcement Prebuffer

- [ ] Treat `MIN_READY_ANNOUNCEMENTS=5` as a true air-readiness gate.
- [ ] Keep 5-8 ready announcement clips during live operation.
- [ ] Generate announcements 4-5 songs ahead.
- [ ] Do not block playback while waiting for the LLM.
- [ ] If AI is missing, try to start/check/pull configured Ollama/Qwen before falling back.
- [ ] Keep deterministic fallback only as a dead-air prevention path.
- [ ] Add admin visibility:
  - ready count
  - required count
  - queue age
  - failed generation count
  - next announcement type

Acceptance:
- Broadcast does not start until at least 5 announcements are ready, unless the user explicitly overrides in a local-only admin action.
- Live playback continues even if one generation attempt fails.

## P1 - Finish Qwen TTS Voice Routing

- [ ] Document a working `QWEN_TTS_COMMAND` example.
- [ ] Pass program voice/personality into the TTS command.
- [ ] Support female/male voice mapping per program host.
- [ ] Show TTS provider health in admin panel.
- [ ] Show last TTS error locally only.
- [ ] Add a one-click local TTS test from the admin app.
- [ ] Add cleanup policy for generated clips.

Acceptance:
- Each program can use its own voice/personality.
- Failed TTS is visible locally and does not silently become fake speech.

## P1 - Public `/ai` Safety And Simplicity

- [ ] Keep public `/ai` as a listener page, not an operator console.
- [ ] Remove or hide overly detailed operational internals from public UI.
- [ ] Keep one RadioTEDU card only.
- [ ] Show:
  - cover/logo
  - stream play button
  - now playing
  - current program
  - schedule/progress
  - top songs
  - top genres
  - real listener/session metrics
  - offline/waiting state
- [ ] Hide:
  - admin controls
  - logs
  - incidents
  - local paths
  - secrets
  - financial/support/money fields
- [ ] Add tests for forbidden public text/fields.

Acceptance:
- Public UI feels like an Andon-style radio page, not a dashboard/debug console.
- Expired snapshots show an honest waiting/offline state.

## P1 - Stronger Public Snapshot Contract

- [ ] Define a strict Pydantic model for public snapshots instead of accepting arbitrary dicts.
- [ ] Reject unexpected private fields at the API boundary.
- [ ] Add schema tests for:
  - local paths
  - secrets/tokens
  - logs
  - incidents
  - file paths
  - financial words
- [ ] Version the snapshot payload.
- [ ] Add backwards-compatible handling for older broadcast clients.

Acceptance:
- `POST /api/public/snapshot` cannot store private/admin fields even if a bad client sends them.

## P1 - Website Server Runbook

- [ ] Add `docs/WEBSITE_SERVER_RUNBOOK.md`.
- [ ] Cover `.env` setup for website server.
- [ ] Cover FastAPI + Vite build deployment.
- [ ] Cover reverse proxy for `/api/public/*`.
- [ ] Cover public `/ai` routing.
- [ ] Cover stream URL/proxy choice.
- [ ] Cover token rotation.
- [ ] Cover offline snapshot behavior.

Acceptance:
- A fresh website server Codex can deploy `radiotedu.com/ai` from the runbook without guessing.

## P1 - Broadcast Computer Runbook

- [ ] Add `docs/BROADCAST_COMPUTER_RUNBOOK.md`.
- [ ] Cover `.env` setup for `F:/Songs/Jazz`.
- [ ] Cover Ollama/Qwen model setup.
- [ ] Cover Qwen TTS command setup.
- [ ] Cover Liquidsoap/Icecast install and checks.
- [ ] Cover desktop admin app start.
- [ ] Cover `Run Air` readiness checks.
- [ ] Cover website snapshot sync.
- [ ] Cover common failure states.

Acceptance:
- A fresh broadcast computer Codex can set up the local station from the runbook without guessing.

## P2 - Prod Smoke Tests

- [ ] Add `scripts/smoke_broadcast.py`.
- [ ] Verify:
  - music library has real playable tracks
  - database opens
  - Ollama reachable
  - configured model installed
  - TTS command works
  - Liquidsoap found when enabled
  - Icecast reachable when enabled
  - public snapshot endpoint accepts correct token
  - public snapshot rejects wrong token
- [ ] Add `scripts/smoke_public_server.py`.
- [ ] Verify:
  - `/api/public/status` reachable
  - `/ai` build route available
  - session start/heartbeat/end works
  - expired snapshot goes offline

Acceptance:
- Before going live, one command gives a plain pass/fail checklist.

## P2 - Admin UX Polish

- [ ] Make the admin app feel like broadcast software, not a website.
- [ ] Use a compact operational layout.
- [ ] Add clear status lights:
  - Air
  - Stream
  - AI
  - TTS
  - Music
  - Prebuffer
  - Website sync
- [ ] Add an explicit “local only” label for admin-only data.
- [ ] Add keyboard-safe controls for Run/Stop/Skip.
- [ ] Add confirmation for destructive or disruptive actions.

Acceptance:
- Operator can understand whether the station is actually ready in under 10 seconds.

## P2 - Long-Run Reliability

- [ ] Add a watchdog for stuck playback.
- [ ] Add a watchdog for stale announcement buffer.
- [ ] Add a watchdog for Liquidsoap process exit.
- [ ] Add a watchdog for Icecast mount going down.
- [ ] Add bounded log retention.
- [ ] Add generated clip retention cleanup.
- [ ] Add database vacuum/maintenance task.

Acceptance:
- The station can run unattended for many hours without unbounded disk growth or silent failure.

## P2 - Better News/Weather/Context Segments

- [ ] Keep RSS/news source-only.
- [ ] Add feed freshness checks.
- [ ] Add per-feed allowlist in config.
- [ ] Add “do not read if stale” behavior.
- [ ] Add weather announcement templates.
- [ ] Add song context announcements only when sourced context exists.
- [ ] Add admin visibility into last fetched source time.

Acceptance:
- The AI host can mention news/weather/song context without inventing facts.

## P3 - Future Nice-To-Haves

- [ ] Multi-day strategy view for programs while keeping exactly one channel.
- [ ] Manual schedule editor with validation.
- [ ] “Emergency fallback playlist” from real indexed tracks only.
- [ ] Public share card for now playing.
- [ ] Optional remote admin auth for trusted operators.
- [ ] Optional mobile-friendly local operator view.
- [ ] Optional recording/clipping of latest real segment.

## Non-Negotiables

- [ ] Exactly one channel: RadioTEDU.
- [ ] No demo/fake songs, artists, listeners, stats, analytics, donations, or financial UI.
- [ ] Public website must never receive local paths, secrets, logs, or internal task details.
- [ ] Broadcast computer owns music, AI, TTS, playback, Liquidsoap/Icecast, and snapshot push.
- [ ] Website server receives sanitized snapshots and tracks real public sessions only.
