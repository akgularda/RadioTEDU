# RadioTEDU Terra Execution Pack

> **For agentic workers:** REQUIRED SUB-SKILL after user approval: use `superpowers:subagent-driven-development` for one work order at a time. A Terra worker receives exactly one work order, never a whole phase. The parent reviewer performs requirements review and code-quality review before the next work order.

**Status:** DRAFT — APPROVAL REQUIRED

**Purpose:** Make the RadioTEDU implementation executable by a lower-context/lower-quota model without architecture inference. This pack resolves conflicts in older plans, freezes thresholds and contracts, reduces work to atomic commits, and defines mandatory stop conditions.

**Execution authorization:** No. Planning files may be reviewed; no code, tests, builds, services, packages, models, or deployments may be changed until the user explicitly approves.

## 1. Authority Order

When documents disagree, use this order:

1. This Terra Execution Pack.
2. `2026-07-11-radiotedu-master-24x7.md`.
3. The six retained 2026-07-10 implementation plans.
4. Existing source behavior.

Never combine conflicting values. Record the higher-authority value in the work-order review.

### Superseded assumptions

- Any five-clip or five-item prebuffer is superseded by minute-based schedule coverage.
- Any strict EN/FR alternating cursor is superseded by deadline/deficit selection with bounded fairness.
- Any per-station or per-app public snapshot pusher is superseded by one process-level `PublicSyncService`.
- Any production Piper, SAPI, dummy, cloud, silent-audio, or fake-TTS fallback is prohibited.
- Any one-Icecast-host claim of surviving Icecast host failure is superseded by two independent streaming hosts.
- Any single Windows broadcast service is superseded by four independently supervised services.
- Any 24-hour soak is superseded by 72 hours, seven-day canary, and 30-day supervised production.
- `frontend/src/components/Dashboard.tsx` is not the public listener page. Use `frontend/src/components/PublicDashboard.tsx` and `frontend/src/App.tsx` for Phase 7.
- Runtime code belongs in `backend/runtime/`; `backend/stations/` remains profile/context code only.

## 2. Frozen Toolchain and Hosts

- Python: `3.12.10`.
- Node.js: `22.14.0`.
- npm: `10.9.2`, lockfile v3.
- Windows broadcast OS qualification: Windows 11 Pro x64 and Windows Server 2022.
- Linux qualification: Ubuntu Server 24.04 LTS x64.
- FFmpeg/ffprobe: release build records the exact qualified SHA/version; all required filters are capability-tested before packaging.
- Liquidsoap and Icecast: exact versions are recorded by Phase 0 in `config/deployment/toolchain.json`; missing autocue, blank detection, HLS/Icecast output, or required encoder support fails Phase 0.
- Broadcast PC minimum: 8 GB RAM, x64 CPU, SSD with both 25 GB and 20% free, wired Ethernet, NTP offset below 1 second, disabled sleep/hibernate, controlled updates, automatic power-on, 30–60 minute UPS.
- Each streaming host minimum: Ubuntu 24.04, 2 vCPU, 2 GB RAM, 20 GB SSD, 10 Mbps symmetric uplink. `stream-a` and `stream-b` must not share a VM, disk, Icecast process, fallback process, or power failure domain.

## 3. Frozen Runtime Topology

### Windows services

1. `RadioTEDU.SharedAI`: owns Ollama, Qwen, model leases, and no station database or playout process.
2. `RadioTEDU.Station.EN`: owns only EN context, DB, announcement store, scheduler, playback, Liquidsoap child, source credentials, PID, restart counter, and sanitized public-state producer.
3. `RadioTEDU.Station.FR`: identical FR-only ownership.
4. `RadioTEDU.PublicSync`: owns the shared outbound sync DB and sends sanitized state for both stations; it cannot control playout.

### Linux services on both streaming hosts

- `icecast2.service`.
- `radiotedu-fallback-en.service`.
- `radiotedu-fallback-fr.service`.
- The web API/frontend may share `stream-a` only if stream availability remains independent of the frontend/API process. `stream-b` remains a distinct host.

### Public listener endpoint

- The public player receives one stable URL per station from a health-aware edge/reverse-proxy layer.
- Both EN and FR primary Liquidsoap processes publish to both streaming hosts.
- Each host has local EN and FR fallback mounts and assets.
- A host outage must move new/reconnecting listeners to the surviving host. Existing-client behavior is recorded per player/codec during qualification.

## 4. Frozen Queue and Freshness Policy

### Separate horizons

- `music_ready_minutes`: continuous future scheduled airtime backed by validated local music/imaging files.
- `speech_ready_minutes`: continuous future scheduled airtime for which every planned dynamic speech item is `audio_ready`.
- `normal_ready_minutes = min(music_ready_minutes, speech_ready_minutes)`.
- A skipped, failed, expired, or merely planned speech job does not count toward `speech_ready_minutes`.
- Static imaging counts only when the referenced versioned asset exists and passes checksum/audio validation.

### Thresholds

| Level | Normal-ready coverage | Required action |
|---|---:|---|
| target | 180–240 minutes | Normal generation; never plan beyond 240 minutes |
| healthy | 120–179.99 minutes | Normal generation |
| low | 60–119.99 minutes | Suspend optional long-form copy; prioritize deficient station |
| emergency | 30–59.99 minutes | Suspend news extras, promos, and nonessential enrichment; generate track links only |
| critical | 10–29.99 minutes | Stop new LLM enrichment; synthesize already-approved short links only |
| continuity-only | below 10 minutes | Stop dynamic speech; broadcast validated music plus static imaging |

- Cold start: both stations require `music_ready_minutes >= 240`, `speech_ready_minutes >= 60`, two validated emergency IDs, and reachable primary plus fallback streams.
- After launch: fill speech toward 180 minutes while music coverage remains at least 240 minutes.
- Recovery from music-only to speech requires 60 continuous speech-ready minutes and three successful real Qwen probes.
- Downward transitions are immediate. Upward transitions require five consecutive one-minute samples above the next boundary.

### Time-sensitive content

- News job creation: airtime minus 15 minutes; deadline airtime minus 5 minutes; expires airtime plus 5 minutes.
- Weather job creation: airtime minus 10 minutes; deadline airtime minus 3 minutes; expires airtime plus 10 minutes.
- Exact clock/time statements are JIT-only, created within 60 seconds of airtime, and never cached across airtimes.
- Expired content is marked `expired`, logged, omitted, and never regenerated for the old airtime.

### Bilingual dispatch

Select a runnable job using this exact order:

1. If one station has received no heavy-model turn in the previous two completed heavy jobs, select that station unless another runnable job has less than 90 seconds of deadline slack.
2. Select smallest deadline slack.
3. Select largest deficit `180 - speech_ready_minutes`.
4. Select oldest `last_model_turn_at`.
5. Select lower numeric priority.
6. Stable tie-breaker: `radiotedu-en` before `radiotedu-fr`, then `job_id` lexical.

No runnable station may wait more than two completed heavy jobs unless the 90-second deadline exception is active. Record the chosen rule and inputs in the job event table.

## 5. Frozen Voices and Imaging

- Exactly four host identities per language, eight total.
- Each language has at least two women and at least one man; the fourth identity is selected during commissioning but remains fixed afterward.
- Host identity never changes with daypart. Delivery controls change: morning energetic, daytime warm, night calm.
- Qwen 1.7B VoiceDesign is used on the build computer for commissioning. The broadcast PC uses the smallest Qwen-only configuration that passes the voice/audio/memory gate with approved references.
- Existing imaging source: `C:/Users/akgul/Downloads/jingle/generated_jingles`.
- Expected source inventory: 42 MP3 files, six aliases, 36 unique existing renders. An inventory mismatch stops import and requires plan review.
- Missing French Pop/Rock imaging is commissioned only after the eight voices pass voice qualification.
- Release media root inside artifacts: `media/imaging/{station_id}/`.
- Installed media root: `C:/ProgramData/RadioTEDU/media/imaging/{station_id}/`.
- Persist release-relative paths only. Absolute source/build paths are forbidden in station databases, manifests, snapshots, logs, and diagnostics.
- Every active program receives three reusable promo masters in its language: morning, daytime, and night. A promo is regenerated only when its copy, language, host, daypart profile, or mastering version changes.
- Minimum station imaging inventory before release: four sonic-logo variants, twelve short IDs, twelve full jingles, four sweepers, four stagers, two emergency IDs, one news bed, one weather bed, and three promos for every active program.

## 6. Frozen Professional Audio Policy

- Stream target: `-16 LUFS` integrated over a 30-minute station aircheck, accepted tolerance `±1 LU`.
- True peak: never above `-1 dBTP`.
- No sample clipping and no qualification transition with decoded peak above the ceiling.
- Processor order: input level control, gentle wideband AGC, restrained multiband dynamics, final true-peak limiter, encoder.
- No hard clipper, stereo widener, bass enhancer, exciter, or destructive source-file normalization in v1.
- Silence detection: below `-60 dBFS` for 1.0 continuous second enters degraded-primary; 1.5 seconds activates fallback. More than 2.0 listener-visible seconds fails qualification.
- Talk-over requires `intro_confidence >= 0.85` and at least 3.0 seconds of usable instrumental intro.
- Speech target end is 0.5 seconds before `intro_end_seconds`, clamped to 0.3–0.7 seconds before the boundary.
- If timing cannot fit, use sequential speech; never time-stretch speech or speak over vocals.
- Airchecks: 64 kbps stereo AAC, station-scoped, 14-day rolling retention, with hourly analysis and daily summary.

### Default segue presets

- Classical music-to-music: sequential or 0.2–1.0 second equal-power fade; never beat matched.
- Jazz: 1.0–2.5 second smart segue.
- Pop: 2.0–4.0 second smart crossfade when cue/level analysis validates overlap.
- Rock: 1.0–3.0 second controlled crossfade.
- Full jingle/spoken item: sequential unless an explicit imaging mix decision exists.
- Short sonic logo/sweeper: explicit category transition only; never inherit music defaults.

## 7. Frozen Programming Policy

- All clocks use timezone `Europe/Istanbul` and versioned effective dates.
- Same title: seven days. It is never automatically relaxed.
- Same artist: 90 minutes.
- Same album: 120 minutes.
- Same imaging variant: 90 minutes, except declared emergency mode.
- Energy bands: low, medium, high. Never schedule more than three consecutive items from one band outside Classical long-form programs.
- A rolling 60-minute window must include at least two host identities when speech inventory allows it.
- Hard-boundary backtiming tolerance: `±2 seconds`.
- Fillers must be validated instrumental/imaging assets no longer than 90 seconds.
- Constraint relaxation order: album separation, energy repetition, host balance, artist separation. Title separation and station/language boundaries are never relaxed.
- Every relaxation produces a durable `constraint_relaxations` row and appears in diagnostics.
- Persist track identity using stable `audio_asset_id` and release-relative path. Do not use an absolute `file_path` as identity.

## 8. Frozen Runtime and Failover Policy

### Station mode

- `STARTING -> LIVE`: cold-start queue gate passes and both remote primary outputs decode audio.
- `LIVE -> MUSIC_ONLY`: Qwen probe fails, arbiter is unavailable, or normal-ready coverage drops below 10 minutes.
- `MUSIC_ONLY -> RECOVERING`: three consecutive real Qwen probes pass.
- `RECOVERING -> LIVE`: speech-ready coverage reaches 60 minutes and remains above it for five one-minute samples.
- Any recovery failure returns to `MUSIC_ONLY`.
- Controlled service stop is the only normal transition to `STOPPED`.

### Stream failover

- Primary probe cadence: 1 second in production; 250 ms evidence sampling during qualification.
- First failed probe or 1.0-second silence: `DEGRADED_PRIMARY`.
- Second failed probe or 1.5-second silence: disconnect primary source and use local host fallback.
- Fallback to recovering: station process, local audio, credentials, queue, and both remote targets remain healthy for 60 seconds.
- Primary restoration: decoded primary audio must remain valid for 30 seconds before fallback release.
- Recovery failure immediately returns to fallback.

### Restart policy

- Per-station delays: 2, 4, 8, 16, 30 seconds.
- Maximum five starts in ten minutes; then suppress that station's restarts, lock its verified fallback, and alert.
- A 30-minute successful station run clears its restart window.
- Shared-AI restart exhaustion leaves both stations in music-only mode.
- Listener continuity limit is 2 seconds; primary process recovery target is 120 seconds, but fallback must protect listeners within 1.5 seconds.

## 9. Frozen Snapshot v2 Contract

### Canonical signature bytes

Join with one LF and no trailing LF:

```text
METHOD_UPPER
REQUEST_PATH
STATION_ID
UNIX_TIMESTAMP
NONCE
SHA256_EXACT_BODY_BYTES
```

Headers:

```text
X-RadioTEDU-Timestamp: decimal Unix seconds
X-RadioTEDU-Nonce: exactly 32 lowercase hexadecimal characters
X-RadioTEDU-Signature: sha256=<64 lowercase hexadecimal characters>
Content-Type: application/json
```

Golden fixture:

```text
method=POST
path=/api/public/stations/radiotedu-en/snapshot
station=radiotedu-en
timestamp=1783684800
nonce=0123456789abcdef0123456789abcdef
secret=32 UTF-8 bytes containing lowercase "a"
body={"schema_version":2,"station_id":"radiotedu-en"}
body_sha256=cf85c23c96e8c1268c206a75a290f03bd4e7c59e68940d61286799645cac79f3
signature=sha256=8125ada219237a6e8ee6ab9d26ed2099d324d534dcee30273a45970f5b7af9d1
```

### Limits and validation order

- Snapshot/recent-play JSON maximum: 262,144 bytes.
- Cover maximum: 5 MiB; JPEG, PNG, or WebP only.
- Timestamp skew: ±30 seconds.
- Snapshot/plays authenticated rate: 30 per station per minute.
- Covers: 60 per station per hour.
- Snapshot lifetime: maximum 60 seconds.
- Models use `extra="forbid"`; positive sequences only.
- Validate: body size, station path, headers/skew, secret, exact-byte HMAC, rate limit, JSON/schema/path identity, nonce transaction, ordering transaction.
- Higher sequence stores. Identical same-sequence/snapshot/body is idempotent. Lower or conflicting equal sequence returns 409 and cannot alter latest state.
- Nonce/audit consumption survives authenticated ordering rejection.

### Endpoints

- `POST /api/public/stations/{station_id}/snapshot`.
- `POST /api/public/stations/{station_id}/plays` with at most 50 events.
- `PUT /api/public/stations/{station_id}/covers/{cover_id}` where `cover_id = "sha256_" + sha256(body)`.
- `GET /api/public/stations/{station_id}/status`.
- `GET /api/public/stations/{station_id}/events` using SSE.
- `GET /api/public/covers/{cover_id}`.
- Station-scoped session start/heartbeat/end.
- `/ai` aliases English; `/ai/en` and `/ai/fr` are explicit.

### Freshness and SSE

- Age at or below 20 seconds: live.
- Above 20 through 60 seconds: delayed/stale.
- Above 60 seconds or absent: offline.
- SSE retry: 10 seconds; keepalive comment every 15 seconds.
- Client fetches status on open. Poll every 10 seconds only while EventSource is unavailable. Stop polling when SSE recovers.
- Progress is browser-derived from start plus duration and stops presenting as live after 60 seconds.

## 10. Database Migration Contract

- Add `schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)` before feature tables.
- Every migration is numbered, transactional, idempotently detected, and checksum-verified.
- Partial migration, duplicate version/name, checksum drift, incompatible column, or cross-station path stops startup.
- Use SQLite migrations for station/shared-sync databases. The public web adapter uses the webserver database dialect but preserves the logical schema.

### Required new logical tables

- `audio_assets`, `imaging_assets`, `imaging_aliases`.
- `announcement_jobs`, `announcement_job_events`.
- `station_clocks`, `clock_positions`, `scheduled_items`, `constraint_relaxations`.
- `playout_events`, `aircheck_reports`.
- Shared sync DB: `public_sync_station_state`, `public_sync_outbox`, `public_cover_cache`.
- Web DB: `public_station_snapshots`, `public_snapshot_nonces`, `public_recent_plays`, `public_covers`, `public_stream_health`, `public_snapshot_audit`, station-scoped listener sessions.

Exact columns and indexes are copied into the owning work order from this pack's Appendix A. Workers may not rename or merge tables.

## 11. Terra Worker Protocol

Every work order uses this sequence:

1. Read this pack, the named retained-plan task, and only the listed source/test files.
2. Run the prerequisite command. If it fails, stop and report; do not repair unrelated failures.
3. Run `git status --short`. Record pre-existing changes. Never stage them.
4. Write only the named failing tests.
5. Run the exact focused red command. It must fail for the expected missing behavior, not syntax/import/environment unrelated to the task.
6. Implement the smallest change within the allowed-file list.
7. Run the focused green command.
8. Run the listed regression command.
9. Inspect `git diff --check` and the allowed-file diff.
10. Request requirements review. Fix only confirmed in-scope findings.
11. Request code-quality review. Fix only confirmed in-scope findings.
12. Re-run focused and regression commands.
13. Commit exactly the allowed files with the exact message.
14. Report commit, tests, evidence, remaining risks, and stop. Do not start the next work order.

### Universal stop conditions

Stop without committing if any of these occurs:

- Required file/interface from an earlier work order is absent or differs.
- A test fails outside the work order and the failure was not present at prerequisite time.
- Implementation requires an unlisted production file.
- A migration risks user data or cannot roll back transactionally.
- EN reads/writes FR state or vice versa.
- Non-Qwen speech becomes reachable.
- AI/web failure can block music playout.
- Private paths, tokens, prompts, incidents, or secrets enter public output/logs.
- Measured RAM exceeds the approved qualification limit.
- Audio exceeds the true-peak ceiling, contains invalid format, or produces listener silence over 2 seconds.
- A service/host ownership boundary would change.
- A task would stage pre-existing user changes or planning files unintentionally.

## 12. Atomic Work-Order Index

The parent gives Terra one row at a time. `Plan source` is mandatory reading; only the referenced task/section is loaded.

| ID | Deliverable | Allowed production scope | Focused test | Commit |
|---|---|---|---|---|
| T00 | baseline fixes: one sync owner, side-effect-free imports | `backend/app.py`, `backend/orchestrator.py`, `backend/public_dashboard.py`, affected existing tests | current foundation/core selectors | `fix: freeze side-effect-free runtime ownership` |
| T01 | foundation negative-isolation gate | retained foundation Task 7 files only | station profile/isolation suites | `test: prove station foundation isolation` |
| T02 | numbered migration runner | `backend/database.py`, `backend/migrations/**` | `tests/backend/test_database_migrations.py` | `feat: add transactional schema migrations` |
| T03 | audio analysis contracts and ffprobe analyzer | `backend/audio/models.py`, `catalog_analyzer.py` | `test_audio_catalog.py` | `feat: analyze broadcast audio assets` |
| T04 | catalog persistence and scan integration | analyzer script, music library, station profiles | `test_audio_catalog.py` | `feat: persist validated music catalog` |
| T05 | imaging import/deduplication | imaging library/import script | `test_imaging_library.py` | `feat: curate station imaging library` |
| T06 | package existing imaging | release-relative manifests/assets and imaging tests | imaging qualification selectors | `test: qualify packaged bilingual imaging` |
| T07 | announcement job models/store | `backend/announcements/models.py`, `store.py`, migration | `test_announcement_store.py` | `feat: persist announcement job state machine` |
| T08 | freshness policy | `backend/announcements/freshness.py` | `test_freshness_policy.py` | `feat: enforce broadcast content freshness` |
| T09 | horizon planner/readiness | planner, readiness, scheduler/context changes | `test_horizon_planner.py` | `feat: maintain rolling announcement horizons` |
| T10 | bilingual dispatcher | dispatcher, orchestrator/radio-agent integration | `test_bilingual_dispatcher.py` | `feat: dispatch bilingual jobs fairly` |
| T11 | Qwen contracts/voice policy | retained Qwen Tasks 1–2 | retained focused suites | retained exact commits |
| T12 | persistent Qwen service/client | retained Qwen Tasks 3–4 | service/client suites | retained exact commits |
| T13 | Qwen cache/audio finishing | retained Qwen Tasks 5–6 | cache/audio suites | retained exact commits |
| T14 | shared model arbiter | `backend/resources/**`, arbiter launcher and integrations | `test_model_arbiter.py` | `feat: arbitrate shared AI memory` |
| T15 | commission eight voices and missing imaging/promos | retained Qwen Task 8 plus manifests | voice qualification suites | `feat: commission bilingual station voices` |
| T16 | replace five-clip integration with minute horizons | retained Qwen Tasks 7/9 as overridden | horizon/Qwen/runtime selectors | `feat: integrate Qwen with rolling horizons` |
| T17 | segue contracts/policy | `backend/audio/segue_policy.py` | `test_segue_policy.py` | `feat: define genre-sensitive segues` |
| T18 | processing profiles and Liquidsoap render | processing profile, station profiles, `backend/liquidsoap.py` | `test_processing_profiles.py` | `feat: render professional station processing` |
| T19 | cue/silence/talk-over playout | playback, music library, Liquidsoap | segue/core runtime selectors | `feat: apply measured playout transitions` |
| T20 | aircheck persistence/analyzer | aircheck, DB migration, tests | `test_aircheck_analysis.py` | `feat: analyze rotating station airchecks` |
| T21 | versioned clocks | programming clocks, scheduler, DB migration | `test_program_clocks.py` | `feat: define versioned station clocks` |
| T22 | separation and imaging rotation | programming separation/rotation | music/imaging tests | `feat: enforce station rotation policy` |
| T23 | backtiming and seven-day log gate | backtiming, fixtures, scheduling tests | Phase 5 suite | `test: qualify deterministic station logs` |
| T24 | deployment contracts | station/deployment configs and validation tests | deployment boundary selectors | `config: freeze dual-station deployment boundaries` |
| T25 | canonical station runtime | `backend/runtime/station_runtime.py`, app/orchestrator | `test_dual_station_runtime.py` | `refactor: centralize isolated station runtime lifecycle` |
| T26 | station Liquidsoap isolation | Liquidsoap template/render/tests | runtime Liquidsoap selectors | `feat: isolate station Liquidsoap sources` |
| T27 | supervisor/failover state machines | runtime supervisor/failover, Icecast check | state-machine suites | `feat: add bounded station recovery and failover` |
| T28 | station launchers | broadcast/station scripts | launcher selectors | `feat: launch independent station processes` |
| T29 | dual-host fallback artifact | `packaging/streaming/**`, tests | streaming packaging suites | `ops: add independent server fallback sources` |
| T30 | four Windows services | `packaging/broadcast/**`, installer/tests | broadcast installer suites | `ops: install independent broadcast services` |
| T31 | Snapshot v2 contracts/signing | `backend/public_sync/models.py`, signing, fixtures | signing suite | `feat: freeze public snapshot v2 contract` |
| T32 | signed ordered web ingestion | public app/dashboard/database | ordering suite | `feat: ingest ordered signed public snapshots` |
| T33 | one persistent sync service/outbox | public-sync outbox/service, remove old owners | outbox suite | `feat: add one persistent public sync service` |
| T34 | runtime-to-sync event bridge | supervisor/runtime/public-sync integration | ownership/isolation selectors | `feat: connect station runtimes to public sync` |
| T35 | covers and recent plays | public-sync covers, web storage/tests | cover/recent-play suites | `feat: publish cached covers and recent plays` |
| T36 | independent stream health and SSE | stream health, public events/app | health/SSE suites | `feat: stream truthful public status events` |
| T37 | bilingual public UI | `App.tsx`, `api.ts`, `PublicDashboard.tsx`, styles/tests | dashboard tests/build | `feat: deliver bilingual live listener experience` |
| T38 | deterministic three-role releases | release builder/layout/tests | release suites | `build: package role-separated radio infrastructure` |
| T39 | role-aware backup/restore | operations backup/restore/CLI/tests | operations suites | `ops: add verified role-aware backup and restore` |
| T40 | runbooks and redacted diagnostics | operations docs/diagnostics/tests | diagnostics suites | `docs: define autonomous broadcast recovery` |
| T41 | deterministic fault harness | qualification policy/scripts/tests | qualification unit suites | `test: add deterministic broadcast fault drills` |
| T42 | 72-hour soak | evidence only; no source changes | soak verifier | `test: record 72-hour resilience soak` if evidence policy permits |
| T43 | seven-day canary | evidence only | canary verifier | no source commit; signed evidence artifact |
| T44 | 30-day supervised production | evidence only | production verifier | no source commit; signed release decision |

## 13. Exact Phase Gates

### Foundation

```powershell
py -3.12 -m pytest tests/backend/test_station_profiles.py tests/backend/test_station_isolation.py -q
```

Expected: exit 0; all tests pass; no shared DB/media/announcement/cache/log roots.

### Audio, queue, AI

```powershell
py -3.12 -m pytest tests/backend/test_audio_catalog.py tests/backend/test_imaging_library.py tests/backend/test_announcement_store.py tests/backend/test_freshness_policy.py tests/backend/test_horizon_planner.py tests/backend/test_bilingual_dispatcher.py tests/backend/test_model_arbiter.py -q
```

Expected: exit 0; no model download in unit tests; no source audio mutation; no cross-station lease/job access.

### Professional playout/programming

```powershell
py -3.12 -m pytest tests/backend/test_segue_policy.py tests/backend/test_processing_profiles.py tests/backend/test_aircheck_analysis.py tests/backend/test_program_clocks.py tests/backend/test_music_separation.py tests/backend/test_imaging_rotation.py -q
```

Expected: exit 0; all deterministic fixtures pass.

### Runtime/failover

```powershell
py -3.12 -m pytest tests/backend/test_dual_station_runtime.py tests/backend/test_runtime_supervisor_state_machine.py tests/backend/test_failover_state_machine.py -v
```

Expected: exit 0; EN/FR process, DB, mount, credential, queue, PID, and restart isolation proven.

### Public sync/web

```powershell
py -3.12 -m pytest tests/backend/test_snapshot_v2_signing.py tests/backend/test_snapshot_v2_ordering.py tests/backend/test_public_sync_outbox.py tests/backend/test_public_cover_cache.py tests/backend/test_public_recent_plays.py tests/backend/test_public_stream_health.py tests/backend/test_public_sse.py -q
npm test -- --run frontend/src/__tests__/dashboard.test.tsx
npm run build
```

Expected: all commands exit 0; no browser request targets the broadcasting computer.

### Release/operations

```powershell
py -3.12 -m pytest tests/release tests/operations tests/qualification -q
```

Expected: exit 0; no artifact, signature, secret scan, install, restore, or policy failures.

### Qualification

```powershell
py -3.12 scripts/run_release_qualification.py soak --duration-seconds 259200 --health-interval-seconds 15 --audio-probe-interval-ms 250 --output artifacts/evidence/soak.jsonl
```

Expected: duration at least 259200 seconds, valid evidence chain, maximum listener silence at most 2.0 seconds, no leakage, no stale time-sensitive content, and no unresolved severity-1/2 incidents.

Canary duration is 604800 seconds. Production qualification duration is 2592000 seconds. Any candidate, config, service-unit, processing-preset, voice-reference, or asset-manifest digest change restarts the active gate from zero.

## 14. Terra Work-Order Prompt Template

The parent fills every bracket before dispatch. Terra must reject an incomplete prompt.

```text
You are implementing RadioTEDU work order [ID]: [TITLE].

Approval: user has approved execution; Phase [N-1] gate commit is [HASH].
Workspace: F:\RTAI\RadioTEDU\.worktrees\dual-station-radiotedu
Branch: feature/dual-station-radiotedu

Read completely:
1. docs/superpowers/plans/2026-07-11-radiotedu-terra-execution-pack.md sections [SECTIONS]
2. docs/superpowers/plans/[RETAINED_PLAN].md Task [TASK]
3. Only these existing source/test files: [FILES]

Allowed production files: [FILES]
Allowed test/fixture files: [FILES]
Forbidden: all other files, dependency/version changes, architectural changes, non-Qwen TTS, staging pre-existing changes.

Frozen interfaces consumed: [SIGNATURES]
Frozen interfaces produced: [SIGNATURES]
Prerequisite command: [COMMAND]
Expected prerequisite: exit 0, [DETAIL]
Focused red command: [COMMAND]
Expected red reason: [DETAIL]
Focused green command: [COMMAND]
Expected green: exit 0, [COUNT/NAMES]
Regression command: [COMMAND]
Expected regression: exit 0
Exact commit message: [MESSAGE]
Task-specific stop conditions: [CONDITIONS]

Follow TDD. Do not start another work order. Return:
- changed paths
- red evidence
- green/regression evidence
- commit hash
- requirement checklist
- risks or STOP reason
```

## Appendix A: Canonical Tables and Indexes

### Audio/imaging

- `audio_assets`: stable asset ID, station, asset type, release-relative path, SHA-256, size, duration, LUFS, dBTP, leading/trailing silence, cue-in/out, intro end/confidence, BPM, sample rate, channels, codec, validation state/errors, analyzer version, source mtime, analyzed time. Unique station/relative path; indexes station/status/type and checksum.
- `imaging_assets`: fields from the frozen ImagingAsset contract. Unique station/public ID/version; indexes station/active/category/daypart and station/checksum.
- `imaging_aliases`: station, alias relative path, imaging asset ID; primary key station/alias.

### Announcement jobs

- `announcement_jobs`: frozen AnnouncementJob fields; unique station/planner key; indexes station/state/deadline, station/airtime, state/lease expiry, station/kind/expiry.
- `announcement_job_events`: ID, job ID, from/to state, actor, reason, occurred time, metadata JSON; index job/time.

### Programming/playout

- `station_clocks`: clock ID, station, name, timezone, version, effective range, active, checksum.
- `clock_positions`: position ID, clock ID, ordinal, offset, item kind/category, boundary kind, maximum lateness, rules JSON; unique clock/ordinal.
- `scheduled_items`: item ID, station/date/airtime, clock/position, asset type, track/imaging/job IDs, duration, state, rule trace, created time.
- `constraint_relaxations`: ID, scheduled item, rule, original/relaxed values, reason, time.
- `playout_events`: expected item, actual item, station, start/end, transition decision, levels, result, time.
- `aircheck_reports`: station/window, file relative path/checksum, LUFS, dBTP, silence/clipping/transition counts, result, analyzer version.

### Shared public sync

- `public_sync_station_state`: station primary key, next snapshot/play sequences, last fingerprint/heartbeat/update.
- `public_sync_outbox`: ID, station, kind, logical key, sequence, method/path/content type/body, attempts/next attempt/create time/error; unique station/kind/logical key; due index.
- `public_cover_cache`: cover ID, station, SHA-256, type/size, release-relative source, source mtime, uploaded time/error; unique station/SHA.

### Web public state

- `public_station_snapshots`, `public_snapshot_nonces`, `public_recent_plays`, `public_covers`, `public_stream_health`, `public_snapshot_audit`, and station-scoped listener sessions use the exact columns/indexes in the Phase 7 retained plan as overridden by this pack.

## Approval Record

- User approval of Terra pack: pending
- Execution authorized: no
- First executable work order after approval: T00 only

