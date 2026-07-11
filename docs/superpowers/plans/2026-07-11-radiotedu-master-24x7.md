# RadioTEDU Bilingual Autonomous Radio Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** DRAFT — APPROVAL REQUIRED. No implementation task in this document may start until the user explicitly approves this master plan.

**Terra execution authority:** After approval, lower-context workers must use `docs/superpowers/plans/2026-07-11-radiotedu-terra-execution-pack.md`. That document freezes every value left as a range here, resolves conflicts in the six retained plans, defines one-commit work orders, and is authoritative whenever older plan text disagrees.

**Goal:** Deliver two English/French RadioTEDU internet stations that generate Qwen-only AI presentation several hours ahead, sound like professionally processed radio, publish AndonFM-style live metadata and cover art, and continue broadcasting safely through AI, website, network, application, and single-source failures.

**Architecture:** The Windows broadcasting computer runs two isolated station runtimes, one low-RAM shared AI resource arbiter, disk-backed announcement queues, local music/imaging libraries, and independent Liquidsoap outputs. A single outbound-only Public Sync Service publishes signed station snapshots to the Linux webserver, while the webserver stores public state, serves the `/ai` listener experience, and provides an independent fallback audio source. AI enriches the station but never sits in the hard real-time audio path.

**Tech Stack:** Python 3.11+, FastAPI, SQLite on the broadcasting computer, PostgreSQL or existing durable web database on the webserver, Liquidsoap, Icecast, FFmpeg/ffprobe, Qwen3-TTS only, Ollama-compatible local LLM, React/TypeScript/Vite, SSE with polling fallback, Windows services, Linux systemd services.

## Global Constraints

- English and French are separate station identities, databases, queues, schedules, stream mounts, public snapshots, and failure domains.
- Qwen TTS is the only speech engine used in production; Piper, SAPI, dummy, or cloud TTS may not become on-air fallbacks.
- The 8 GB broadcasting computer runs one heavy AI model workload at a time through a shared resource arbiter.
- Each station has 3–4 locked host identities including at least one woman; morning delivery is energetic, daytime delivery warm, and night delivery calm.
- Track announcements are produced ahead of airtime and persisted to disk; news, weather, and time-sensitive copy use short freshness windows.
- Target ready-audio horizon is 3 hours per station, healthy is 2 hours, low is 60 minutes, emergency is 20–30 minutes, and maximum retained future horizon is 4 hours.
- English and French jobs are scheduled fairly by deadline and remaining ready minutes, not by strict EN/FR alternation.
- Jingles may be selected from `C:/Users/akgul/Downloads/jingle/generated_jingles` during the build, but release packages must contain curated copies and must not depend on the Downloads directory at runtime.
- Program promos, station IDs, sonic logos, beds, and emergency imaging are commissioned once, versioned, packaged, and reused.
- AI failure must remove optional speech, never music; no synthesis request may block Liquidsoap or the encoder.
- Website or public-sync failure must never affect audio generation, playout, encoding, or failover.
- The website receives only sanitized public snapshots over outbound HTTPS; it never connects to the broadcasting computer or its databases.
- The public listener experience is RadioTEDU-branded and AndonFM-inspired, not a visual copy.
- Output targets remain station-configurable. The current stream reference is `-16 LUFS` integrated and `-1 dBTP`, subject to measured listening qualification before release.
- Aggressive clipping, destructive per-file normalization, excessive stereo widening, bass enhancement, and one-size-fits-all crossfades are excluded from the initial release.
- Existing user changes and the untracked `release/` directory in the main worktree are out of scope and must be preserved.

---

## System Boundaries

### Broadcasting computer

- Owns music and imaging assets, schedule execution, public-safe live state, announcement generation, disk queues, Liquidsoap processes, encoders, local health checks, and outbound snapshot delivery.
- Runs one independent station process for `radiotedu-en` and one for `radiotedu-fr`.
- Runs one shared AI resource arbiter and one Public Sync Service for both stations.
- Exposes no inbound public port.

### Webserver

- Receives signed Snapshot v2 documents.
- Stores the latest public state and recent-play history per station.
- Serves the `/ai` application, cover assets, schedules, SSE events, and polling endpoints.
- Checks Icecast stream availability independently of broadcast-computer claims.
- Hosts or controls a fallback AutoDJ/source that remains independent of the Windows computer.

### Streaming server

- Receives separate EN and FR primary mounts.
- Switches to station-specific fallback sources when primary audio is unavailable or silent.
- Does not depend on the public website frontend.

---

## Existing Detailed Plans Retained

1. `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-foundation.md`
2. `docs/superpowers/plans/2026-07-10-radiotedu-qwen-voice-platform.md`
3. `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-broadcast-runtime.md`
4. `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-public-web.md`
5. `docs/superpowers/plans/2026-07-10-radiotedu-public-page-redesign.md`
6. `docs/superpowers/plans/2026-07-10-radiotedu-release-operations-qualification.md`

This master plan defines the order, adds requirements approved after those documents were written, and supersedes conflicting buffer, fallback, public-sync ownership, and qualification assumptions.

---

## Phase 0: Approval and Baseline Freeze

**Deliverable:** A reproducible baseline with no ambiguous runtime ownership and a signed-off master architecture.

**Files:**
- Review: all six retained plans listed above
- Review: `backend/app.py`
- Review: `backend/orchestrator.py`
- Review: `backend/public_dashboard.py`
- Review: `scripts/run_broadcast_computer.py`
- Review: `backend/liquidsoap.py`
- Record evidence under: `artifacts/qualification/baseline/`

- [ ] Obtain explicit user approval for this document.
- [ ] Record branch, commit, Python/Node/FFmpeg/Liquidsoap versions, installed models, and clean-worktree evidence.
- [ ] Re-run the current Python and frontend suites and store concise machine-readable results.
- [ ] Resolve the Task 6 review findings before new feature work: one `PublicSnapshotPusher` owner only, and no database/directory/cover generation during module import.
- [ ] Complete the existing Foundation Task 7 negative-isolation gate.
- [ ] Commit only the baseline fixes and evidence manifest; do not mix feature work into this phase.

**Gate:** Existing behavior passes, English/French isolation tests pass, imports are side-effect free, and exactly one public-sync owner is documented.

---

## Phase 1: Audio Catalog Analysis and Curated Imaging Library

**Deliverable:** Every playable audio asset is validated and described by broadcast metadata; curated RadioTEDU imaging is packaged independently of the source Downloads folder.

**Files:**
- Create: `backend/audio/__init__.py`
- Create: `backend/audio/models.py`
- Create: `backend/audio/catalog_analyzer.py`
- Create: `backend/audio/imaging_library.py`
- Create: `scripts/analyze_audio_catalog.py`
- Create: `scripts/import_radio_imaging.py`
- Create: `tests/backend/test_audio_catalog.py`
- Create: `tests/backend/test_imaging_library.py`
- Modify: `backend/music_library.py`
- Modify: `backend/database.py`
- Modify: `backend/stations/models.py`
- Modify: `config/stations/radiotedu-en.json`
- Modify: `config/stations/radiotedu-fr.json`

**Interfaces:**
- Produce `AudioAnalysis` with duration, integrated LUFS, true peak dBTP, leading/trailing silence, cue-in, cue-out, optional BPM, sample rate, channels, codec, checksum, and validation status.
- Produce `ImagingAsset` with station, language, category, genre, daypart, host identity, duration class, reuse interval, path, checksum, and active version.
- Consume FFmpeg/ffprobe output without mutating original music files.

- [ ] Add failing tests for corrupt files, missing streams, silence boundaries, checksum stability, and deterministic catalog updates.
- [ ] Implement offline ffprobe/FFmpeg analysis and SQLite persistence.
- [ ] Import the 42 current generated MP3s, detect the six aliases, and preserve 36 unique rendered variants without duplicate rotation weight.
- [ ] Define categories: sonic logo, short ID, full jingle, sweeper, stager, program open, program close, news bed, weather bed, emergency ID.
- [ ] Commission missing short 1–2 second sonic logos, 3–5 second IDs, and French Pop/Rock coverage through the existing Qwen VoiceDesign + FFmpeg imaging method.
- [ ] Generate reusable EN/FR program-promo variants for morning, daytime, and night; version by copy, language, voice, style, and audio checksum.
- [ ] Package curated assets under station-scoped release media paths and prove runtime independence from `C:/Users/akgul/Downloads/jingle`.
- [ ] Run audio validation and imaging rotation tests.

**Gate:** No unvalidated file can enter a station queue; all packaged imaging has a checksum, public-safe identifier, correct language, valid duration, and measured audio properties.

---

## Phase 2: Persistent Rolling-Horizon Content and Announcement Pipeline

**Deliverable:** A restart-safe job system continuously maintains 3 hours of ready track presentation for both stations while keeping time-sensitive content fresh.

**Files:**
- Create: `backend/announcements/__init__.py`
- Create: `backend/announcements/models.py`
- Create: `backend/announcements/store.py`
- Create: `backend/announcements/planner.py`
- Create: `backend/announcements/freshness.py`
- Create: `backend/announcements/dispatcher.py`
- Create: `backend/announcements/readiness.py`
- Create: `tests/backend/test_announcement_store.py`
- Create: `tests/backend/test_horizon_planner.py`
- Create: `tests/backend/test_freshness_policy.py`
- Create: `tests/backend/test_bilingual_dispatcher.py`
- Modify: `backend/database.py`
- Modify: `backend/scheduler.py`
- Modify: `backend/orchestrator.py`
- Modify: `backend/radio_agent.py`
- Modify: `backend/stations/context.py`

**Interfaces:**
- Produce `AnnouncementJob(station_id, language, kind, planned_airtime, deadline, freshness_class, priority, text_state, audio_state, attempts, text_hash, audio_path, audio_checksum)`.
- Produce `HorizonStatus(station_id, ready_minutes, planned_minutes, failed_minutes, level, can_start)`.
- The dispatcher selects the station with the most urgent deadline-adjusted deficit and guarantees bounded fairness without strict alternation.
- Static imaging jobs bypass LLM/TTS and resolve directly from the imaging library.

- [ ] Add failing state-machine tests for planned, text-ready, synthesizing, audio-ready, consumed, expired, skipped, failed, and quarantined jobs.
- [ ] Add atomic SQLite transitions and crash-safe job leasing.
- [ ] Plan track announcements up to four hours ahead from the deterministic music log.
- [ ] Set cold-start launch readiness to at least 60 minutes of dynamic ready audio per station plus a validated emergency music/imaging pool; continue filling toward the 3-hour target after launch.
- [ ] Generate news 10–20 minutes before airtime and weather 5–15 minutes before airtime; expire stale jobs rather than airing old copy.
- [ ] Keep clock/time statements out of long-horizon audio and render them just in time or omit them.
- [ ] Implement low, emergency, and critical modes that progressively suspend optional features and preserve music continuity.
- [ ] Persist all completed audio and job state across application and machine restarts.
- [ ] Prove that a broken English job cannot block French generation and vice versa.

**Gate:** After forced restart, both station horizons reconstruct exactly; missing or expired speech is skipped; music continues; the dispatcher recovers both stations to target without starvation.

---

## Phase 3: Qwen-Only Bilingual Voice Platform and 8 GB Resource Arbitration

**Deliverable:** One persistent, supervised Qwen service produces deterministic bilingual voices without exhausting the 8 GB computer or introducing non-Qwen fallbacks.

**Primary detailed plan:** `docs/superpowers/plans/2026-07-10-radiotedu-qwen-voice-platform.md`

**Additional files/changes required by this master plan:**
- Create: `backend/resources/__init__.py`
- Create: `backend/resources/model_arbiter.py`
- Create: `tests/backend/test_model_arbiter.py`
- Modify: `backend/tts/qwen_tts.py`
- Modify: `backend/tts/factory.py`
- Modify: `scripts/qwen_tts_command.py`
- Modify: `backend/llm.py`
- Modify: `backend/announcements/dispatcher.py`

**Interfaces:**
- Produce `ModelLease(kind, owner, acquired_at, deadline)` for mutually exclusive heavy LLM/TTS work.
- Qwen requests include station, language, host identity, daypart delivery profile, text, deadline, and deterministic cache key.
- Voice commissioning uses the 1.7B VoiceDesign workflow on the build computer; the production computer uses approved references with the lowest qualified Qwen runtime footprint.

- [ ] Complete voice contracts for 3–4 EN hosts and 3–4 FR hosts, including at least one woman per station.
- [ ] Encode energetic morning, warm daytime, and calm night delivery rules without changing host identity.
- [ ] Remove production routing to Piper, SAPI, dummy, or cloud TTS.
- [ ] Serialize heavy Ollama and Qwen phases when measured memory pressure requires it.
- [ ] Add hard timeout, bounded retry, model-process recycle, output duration/format validation, and quarantine.
- [ ] Use content-addressed audio caching so identical approved promos and copy are never synthesized twice.
- [ ] Qualify voice intelligibility, station-name pronunciation, English/French language purity, loudness, noise, and clipping.

**Gate:** Qwen can be killed and restarted without interrupting music; repeated requests are cache hits; measured peak memory stays inside the production computer's safe budget.

---

## Phase 4: Professional Playout, Segue, Voice Tracking, and Output Processing

**Deliverable:** RadioTEDU sounds intentionally programmed rather than like sequential files, while maintaining transparent and measurable output processing.

**Files:**
- Create: `backend/audio/segue_policy.py`
- Create: `backend/audio/processing_profile.py`
- Create: `backend/audio/aircheck.py`
- Create: `tests/backend/test_segue_policy.py`
- Create: `tests/backend/test_processing_profiles.py`
- Create: `tests/backend/test_aircheck_analysis.py`
- Modify: `backend/liquidsoap.py`
- Modify: `backend/playback.py`
- Modify: `backend/music_library.py`
- Modify: `backend/stations/models.py`
- Modify: both station JSON profiles
- Add generated station-scoped Liquidsoap configuration under the runtime state directory, not source control

**Interfaces:**
- `SeguePolicy.choose(previous, current, next) -> SegueDecision` returns sequential, hard cut, fade, smart crossfade, talk-over, or imaging transition plus durations and gain curves.
- `ProcessingProfile` contains loudness target, true-peak ceiling, AGC/compression/limiter settings, silence thresholds, and genre/daypart overrides.
- `AircheckAnalyzer` reports dead air, clipping, loudness deviation, transition overlap, and expected-versus-actual playout.

- [ ] Add failing policy tests proving Classical, Jazz, Pop, Rock, speech, and imaging receive different transition treatment.
- [ ] Enable Liquidsoap autocue metadata, cue-in/out use, silence trimming, and smart crossfade for music-to-music transitions.
- [ ] Keep full jingles and spoken items sequential or explicitly mixed; never apply a blind long crossfade to every asset.
- [ ] Add talk-over on validated instrumental intros, with ducking and a hard rule that speech ends 300–700 ms before the stored vocal/intro boundary.
- [ ] Fall back to a normal sequential announcement when no trustworthy intro boundary exists.
- [ ] Add a conservative stream processor: input level control, gentle AGC, restrained multiband dynamics, and final true-peak limiting.
- [ ] Tune EN and FR station processing independently through measured presets; avoid clipping and audible pumping.
- [ ] Record rotating low-bitrate airchecks and analyze them without exposing private paths to the public API.
- [ ] Add silence detection that removes a silent source and invokes music/fallback rather than waiting indefinitely.

**Gate:** Measured output respects the approved loudness/true-peak envelope, no transition clips, genre-sensitive segues pass listening review, and speech never continues into vocals in the qualification set.

---

## Phase 5: Professional Music Scheduling, Imaging Rotation, and Hard Timing

**Deliverable:** Each station follows intentional clocks, rotation/separation rules, energy arcs, and imaging frequency limits.

**Files:**
- Create: `backend/programming/__init__.py`
- Create: `backend/programming/clocks.py`
- Create: `backend/programming/separation.py`
- Create: `backend/programming/imaging_rotation.py`
- Create: `backend/programming/backtiming.py`
- Create: `tests/backend/test_program_clocks.py`
- Create: `tests/backend/test_music_separation.py`
- Create: `tests/backend/test_imaging_rotation.py`
- Modify: `backend/scheduler.py`
- Modify: `backend/orchestrator.py`
- Modify: `backend/database.py`

**Interfaces:**
- `StationClock` defines category positions and hard/soft time boundaries.
- `SeparationPolicy` enforces title, artist, album, imaging-variant, voice, and energy constraints.
- `Backtimer` selects safe music/imaging combinations to reach top-of-hour boundaries without truncating speech.

- [ ] Add title, artist, album, and imaging reuse separation tests.
- [ ] Add new/recurrent/gold or equivalent configurable music categories without hard-coding a commercial format.
- [ ] Add daypart energy curves and voice-gender/identity balance.
- [ ] Rotate short IDs frequently, full jingles sparingly, and prevent the same imaging variant within 60–90 minutes unless emergency inventory requires it.
- [ ] Add top-of-hour IDs, program open/close, news/weather positions, and deterministic backtiming.
- [ ] Keep beat/key matching optional and limited to qualified Pop/Rock transitions; do not force DJ-style mixing on Classical/Jazz.

**Gate:** A seven-day generated log satisfies all separation and clock rules or produces explicit, explainable constraint relaxations without dead air.

---

## Phase 6: Dual-Station Runtime, Independent Supervision, and True 24/7 Failover

**Deliverable:** EN and FR remain on air independently through AI, application, source, and Windows-computer failures.

**Primary detailed plan:** `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-broadcast-runtime.md`

**Additional files/changes required by this master plan:**
- Create: `backend/runtime/station_runtime.py`
- Create: `backend/runtime/supervisor.py`
- Create: `backend/runtime/failover.py`
- Create: `tests/backend/test_failover_state_machine.py`
- Modify: `scripts/run_station_forever.py`
- Modify: `scripts/run_broadcast_computer.py`
- Modify: `scripts/check_icecast.py`
- Modify: `scripts/smoke_broadcast.py`

**Interfaces:**
- `StationRuntime` owns one station context, database, scheduler, announcement pipeline, playback controller, Liquidsoap process, and public state producer.
- `Supervisor` owns process lifecycle and health but not business state.
- `FailoverState` moves through primary, degraded-primary, fallback, recovering, and primary-restored with hysteresis.

- [ ] Run one OS process per station and prove process/DB/mount/queue isolation.
- [ ] Keep the shared model arbiter out of either station's failure domain.
- [ ] Configure service auto-start, bounded restart, restart-loop suppression, and BIOS/power recovery instructions.
- [ ] Configure independent server-side fallback AutoDJ/source per station using packaged music and imaging.
- [ ] Detect actual output silence and remote Icecast mount health, not merely internal `playing` state.
- [ ] Switch to fallback without overlapping primary and fallback sources; restore primary only after a stable health window.
- [ ] Require wired network, SSD free-space thresholds, NTP, disabled sleep, controlled Windows updates, and a 30–60 minute UPS in the operations checklist.

**Gate:** Killing EN does not disturb FR; killing Qwen removes speech but not music; rebooting Windows activates server fallback and returns to primary automatically after safe recovery.

---

## Phase 7: Snapshot v2, Public Sync, Covers, and AndonFM-Style Listener Experience

**Deliverable:** The website shows truthful live cover art, track/program/host/progress/next information for both stations without exposing or depending on the broadcast computer.

**Primary detailed plans:**
- `docs/superpowers/plans/2026-07-10-radiotedu-dual-station-public-web.md`
- `docs/superpowers/plans/2026-07-10-radiotedu-public-page-redesign.md`

**Additional files/changes required by this master plan:**
- Create: `backend/public_sync/__init__.py`
- Create: `backend/public_sync/models.py`
- Create: `backend/public_sync/outbox.py`
- Create: `backend/public_sync/service.py`
- Create: `backend/public_sync/signing.py`
- Create: `tests/backend/test_public_sync_outbox.py`
- Create: `tests/backend/test_snapshot_v2_signing.py`
- Create: `tests/backend/test_snapshot_v2_ordering.py`
- Modify: `backend/public_dashboard.py`
- Modify: `backend/app.py`
- Modify: `scripts/push_public_snapshot.py`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/Dashboard.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Snapshot v2 carries schema version, station ID, monotonically increasing sequence, generated-at timestamp, on-air state, current item, current program, next item, public stream state, and public cover IDs.
- The single `PublicSyncService` sends an immediate snapshot on track/program/state changes plus a 10-second heartbeat.
- The website rejects invalid signatures, expired timestamps, replayed sequence numbers, unknown stations, and private fields.

- [ ] Replace the static-token-only design with per-station HMAC signatures, timestamp, nonce/sequence validation, and rate limits.
- [ ] Add a persistent local outbox with exponential backoff and jitter; compact obsolete snapshots to the newest state.
- [ ] Upload/cache cover assets once and send public cover IDs or URLs, never binary art in every heartbeat.
- [ ] Store recent-play events separately from latest-state snapshots.
- [ ] Publish updates to browsers through SSE and retain 10-second polling as a fallback.
- [ ] Calculate progress locally from `started_at` and `duration_seconds`; do not send per-second updates.
- [ ] Mark status delayed after 20 seconds without a heartbeat and unavailable after 60 seconds; never claim the last song is still live indefinitely.
- [ ] Verify Icecast reachability server-side and display discrepancies between reported and observed stream health.
- [ ] Deliver EN/FR switcher, large cover art, LIVE state, track/artist, program/host, progress, next item, recently played, schedules, and truthful offline/degraded states.

**Gate:** Website outage does not affect broadcast; broadcast-computer outage produces an accurate stale/offline state; replayed or out-of-order snapshots cannot overwrite newer state.

---

## Phase 8: Security, Packaging, Backup, and Operations

**Deliverable:** Clean Windows and Linux machines can install, supervise, update, diagnose, back up, and restore their role-specific RadioTEDU components.

**Primary detailed plan:** `docs/superpowers/plans/2026-07-10-radiotedu-release-operations-qualification.md`

- [ ] Build separate signed broadcast and webserver artifacts with deterministic manifests, checksums, and SBOMs.
- [ ] Exclude model weights, secrets, private media paths, raw internal logs, and unrelated role components from each artifact.
- [ ] Install broadcast services with least privilege and explicit recovery actions.
- [ ] Install web API/frontend/fallback services under systemd with least privilege.
- [ ] Back up station databases, schedules, configuration, imaging manifests, and public-server state; do not back up reproducible cache objects unnecessarily.
- [ ] Test atomic restore on clean machines before release approval.
- [ ] Export redacted diagnostics containing versions, health, horizons, failure states, and checksums without secrets or personal paths.
- [ ] Document manual on-air override, graceful maintenance, fallback lock, emergency music-only mode, and rollback.

**Gate:** Both packages pass clean-machine installation, service restart, backup/restore, secret scan, and rollback tests.

---

## Phase 9: Qualification and Release Gates

**Deliverable:** Evidence that RadioTEDU is safe to call a 24/7 autonomous broadcast system rather than an automated demo.

- [ ] Run unit, integration, frontend, type/build, security, and packaging suites from clean environments.
- [ ] Run fault injection: stop LLM, stop Qwen, kill one station, kill both stations, corrupt audio, lock one DB, fill disk threshold, interrupt public sync, interrupt Icecast, disconnect network, reboot Windows, and restore power.
- [ ] Require no dead air longer than 2 seconds at the listener-visible output during recoverable single failures.
- [ ] Require automatic service recovery within 60–120 seconds when primary recovery is possible.
- [ ] Require music continuity during all AI failures.
- [ ] Require zero stale news/weather items and zero cross-station data/voice/cover leakage.
- [ ] Run a 72-hour laboratory soak with continuous aircheck analysis.
- [ ] Run a 7-day canary with alerts and daily evidence review.
- [ ] Run a 30-day supervised production qualification before declaring full unattended status.
- [ ] Archive metrics, airchecks, incidents, recovery times, horizon history, and final sign-off.

**Final release criteria:**

- Both primary streams and both independent fallbacks are verified externally.
- AI can remain unavailable for at least one hour without silence.
- Restart preserves queues and resumes generation without duplicate or stale airplay.
- EN and FR failures remain isolated.
- Output loudness, true peak, transitions, speech timing, and codec behavior pass measured and listening review.
- Public status is signed, ordered, current, truthful, and sanitized.
- Operators can install, recover, override, back up, restore, and roll back from written procedures.

---

## Execution Order and Agent Gates

1. Phase 0 must finish before any new implementation.
2. Phase 1 and the non-Qwen portions of Phase 2 may proceed in parallel after Phase 0.
3. Phase 3 consumes Phase 2 contracts and Phase 1 audio validation.
4. Phase 4 consumes Phase 1 analysis and Phase 3 speech assets.
5. Phase 5 consumes Phase 1 catalog data and Phase 4 transition contracts.
6. Phase 6 consumes Phases 2–5 and cannot be accepted on mocks alone.
7. Phase 7 may build against frozen Snapshot v2 fixtures after Phase 2, then integrate with Phase 6.
8. Phase 8 begins after stable runtime and web boundaries exist.
9. Phase 9 is the only path to a 24/7 production declaration.

Each independently reviewable task follows TDD, receives a requirements-compliance review and a code-quality review, and lands as an atomic commit. Agents may not broaden scope, change approved thresholds, add non-Qwen speech, or bypass a failed gate.

---

## Approval Record

- User approval: pending
- Approved scope changes: none yet
- Execution authorized: no
- Implementation agents authorized: no until explicit approval
