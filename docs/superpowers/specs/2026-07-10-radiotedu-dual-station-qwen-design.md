# RadioTEDU Dual-Station Qwen Design

## Status

This is the approved design contract for expanding RadioTEDU into one English and one French station.
It freezes architecture, station identity, voice policy, isolation, public synchronization, migration,
delegated execution, and release gates before implementation begins.

The milestone uses one versioned codebase and two isolated station instances:

| Station ID | Display name | Language | Public route | Stream mount |
|---|---|---|---|---|
| `radiotedu-en` | RadioTEDU | English (`en`) | `/ai/en` | `/radiotedu-en` |
| `radiotedu-fr` | RadioTEDU Français | French (`fr-FR`) | `/ai/fr` | `/radiotedu-fr` |

The existing `/ai` route remains an English compatibility alias.

## Product Goal

Operate two autonomous university radio stations from the broadcasting computer while a separate
webserver publishes sanitized, station-scoped status and players. Both stations use only Qwen for
speech. Each has its own schedule, library, voices, queues, stream, security identity, and failure
state. A failure or configuration mistake in one station must not corrupt or impersonate the other.

## Scope

Included:
- A shared, validated Station Profile v1 contract.
- Four English and four French Qwen hosts.
- Qwen VoiceDesign commissioning and reusable cloned voice prompts.
- Station-isolated orchestration, storage, queues, caches, audio, streams, logs, and secrets.
- Fair access to shared Ollama and Qwen model services.
- Independent Liquidsoap and Icecast runtime boundaries.
- Signed Public Snapshot v2 ingestion and station-specific public pages.
- Compatibility migration from the current single English station.
- Installable broadcast-computer and webserver release packages.
- Operational health, degraded modes, backups, alerts, and recovery evidence.

Excluded:
- More than two stations.
- Non-Qwen speech engines or synthetic speech fallbacks.
- User accounts, payments, advertisements, native mobile applications, and automatic social posting.
- Voice imitation of students, staff, celebrities, or other identifiable real people.
- Automatic translation of English scripts into French for broadcast.

## System Boundaries

The build computer develops, tests, and packages the application. It is not an on-air dependency.

The broadcasting computer owns:
- Music and metadata.
- Ollama, Qwen TTS, programming agents, schedules, queues, and databases.
- Audio finishing, Liquidsoap, Icecast, supervision, and snapshot delivery.
- Private operator controls, credentials, logs, backups, and incident history.

The webserver owns:
- HTTPS snapshot ingestion and signature verification.
- The latest sanitized status per station.
- `/ai`, `/ai/en`, and `/ai/fr` public pages.
- Public artwork, schedules, playback metadata, and stream URLs.

The webserver never reaches into the broadcasting computer, music library, database, logs, or admin
API. The broadcasting computer pushes sanitized state outward. A webserver outage cannot stop audio.

## Station Profile v1

Every station starts from an immutable, schema-validated profile. Runtime overrides may come only from
the documented deployment configuration. Unknown keys, missing required keys, duplicate identifiers,
invalid paths, shared secret references, and invalid locale values fail startup.

Required profile fields:
```yaml
profile_version: 1
station_id: radiotedu-en
display_name: RadioTEDU
language: en
locale: en-US
timezone: Europe/Istanbul
public:
  route: /ai/en
  compatibility_routes: [/ai]
  snapshot_endpoint: /api/public/stations/radiotedu-en/snapshot
  status_endpoint: /api/public/stations/radiotedu-en/status
  stream_url: https://radiotedu.com:8001/radiotedu-en
audio:
  stream_mount: /radiotedu-en
  loudness_lufs: -16
  true_peak_dbtp: -1
  minimum_qwen_buffer: 5
runtime:
  data_root: data/stations/radiotedu-en
  database: data/stations/radiotedu-en/radio.db
  music_root: media/stations/radiotedu-en/music
  announcement_root: data/stations/radiotedu-en/announcements
  cache_root: data/stations/radiotedu-en/qwen-cache
  log_root: data/stations/radiotedu-en/logs
voice_pack: radiotedu-en-voices-v1
snapshot_secret_ref: RADIOTEDU_EN_SNAPSHOT_SECRET
```

The French profile uses these fixed substitutions:
- `station_id`: `radiotedu-fr`
- `display_name`: `RadioTEDU Français`
- `language`: `fr`
- `locale`: `fr-FR`
- Public route: `/ai/fr`
- No compatibility route.
- Stream mount: `/radiotedu-fr`
- All runtime paths under `data/stations/radiotedu-fr` or `media/stations/radiotedu-fr`.
- Voice pack: `radiotedu-fr-voices-v1`.
- Secret reference: `RADIOTEDU_FR_SNAPSHOT_SECRET`.

Shared defaults may define algorithms and operational limits. Profiles must override every identity,
path, endpoint, mount, voice pack, locale, and secret. A resolved profile is read-only after startup.

Profile validation invariants:
- Station IDs match `^[a-z0-9][a-z0-9-]{2,31}$`.
- Public routes, mounts, writable roots, databases, caches, and secret references are unique.
- Resolved writable paths stay beneath the configured station root.
- A profile cannot reference another station ID in a path, endpoint, cache key, or credential.
- Language and locale agree.
- Only `Europe/Istanbul` is used for schedules in this milestone.
- The Qwen buffer floor cannot be lower than five.
- Loudness and peak limits are fixed at `-16 LUFS` and `-1 dBTP`.

## Qwen-Only Voice System

Qwen is the sole speech engine. SAPI, Piper, cloud TTS, dummy speech, and silent substitute clips are
prohibited in production and qualification tests.

Each host is created with Qwen VoiceDesign. Three candidates are generated per role. Reviewers approve
one reference recording and exact transcript, then create a reusable Qwen cloned-voice prompt. The
approved model checksum, design instruction, reference audio, reference transcript, pronunciation
dictionary, and style anchors form a signed, versioned voice pack.

All voices share this identity:

> Warm, intelligent, and human. Speak as a thoughtful university radio host addressing one listener.
> Use natural phrasing, restrained emotion, and a subtle smile. Never sound promotional, theatrical,
> robotic, excessively polished, whispered, or like an imitation of a known broadcaster.

### English voice pack

| Host | Gender | Daypart | Delivery | Target pace |
|---|---|---|---|---|
| Maya | Woman | Morning | Bright, confident, optimistic energy without shouting | 150–160 wpm |
| Elliot | Man | Daytime | Curious, intelligent, approachable conversation | 135–145 wpm |
| Selin | Woman | Night | Velvety, intimate, calm, and spacious | 110–122 wpm |
| Theo | Man | Weekend | Relaxed, eclectic, and lightly playful | 128–140 wpm |

English uses neutral international pronunciation. It avoids exaggerated American announcer delivery,
formal public-broadcaster imitation, influencer excitement, whispering, and ASMR.

### French voice pack

| Host | Gender | Daypart | Delivery | Target pace |
|---|---|---|---|---|
| Camille | Woman | Morning | Warm, bright, energetic, and clear | 145–155 wpm |
| Mathieu | Man | Daytime | Grounded, intelligent, and conversational | 130–140 wpm |
| Élodie | Woman | Night | Reassuring, calm, intimate, and unhurried | 105–118 wpm |
| Jules | Man | Weekend | Relaxed, curious, and lightly playful | 120–135 wpm |

French uses contemporary `fr-FR`, consistent `vous` address, natural liaison, and native phrasing. It
avoids caricatured regional accents, advertising delivery, literal English syntax, and formal state-
broadcaster imitation. French scripts are authored directly in French from verified facts. Native
French reviewers approve voice identity, diction, phrasing, names, numbers, dates, and cultural tone.

### Delivery policy

The content generator returns broadcast text plus one allowed delivery label:
- `station_id`
- `track_intro`
- `track_outro`
- `weather`
- `news`
- `listener_reply`
- `program_open`
- `program_close`

A deterministic policy maps station, program, daypart, and label to an approved host and locked style
anchor. Listener input and generated copy cannot supply voice instructions or select arbitrary voices.
Every synthesis request includes station ID, language, voice-pack version, host, style, normalized text,
model checksum, and request ID.

### Audio finishing

Each clip passes through:
1. Language-specific text and pronunciation normalization.
2. Qwen synthesis with the approved cloned-voice prompt.
3. Decoding, WAV integrity, duration, sample-rate, clipping, and non-silence checks.
4. Leading and trailing silence trimming without cutting phonemes.
5. Loudness normalization to approximately `-16 LUFS`.
6. True-peak limiting to approximately `-1 dBTP`.
7. Station-scoped cache insertion and announcement-queue insertion.

Cache identity includes station ID, language, voice pack, host, style, normalized text, model checksum,
and finishing-policy version. No cache lookup may omit station ID.

## Qwen Runtime and Failure Behavior

The Qwen service is persistent, localhost-only, model-pinned, and warmed with a real synthesis at startup.
Health means successful valid audio generation, not merely a process, port, command, or loaded model.

Each station maintains at least five prepared Qwen announcements. A fair scheduler reserves capacity for
both stations, limits concurrent high-quality generation, and prevents one queue from starving the other.
Per-station queue depth, oldest wait, synthesis latency, failures, cache hit rate, and buffer depth are
observable. Shared Ollama access follows the same fairness principle.

If Qwen fails:
1. Retry the failed request once under the same idempotency key.
2. Use an appropriate already-generated Qwen clip only when policy permits.
3. Mark TTS degraded for the affected station and alert the operator.
4. Continue uninterrupted music-only playback.
5. Never switch engines, generate silence as speech, or claim an unsynthesized announcement aired.
6. Restore speech only after real synthesis health passes and the five-clip buffer is rebuilt.

A station cannot begin an attended live session without its minimum Qwen buffer. An already-live station
continues music-only while recovery occurs. Fixed station IDs and recovery messages are pre-generated by
Qwen and versioned in each voice pack.

## Station Isolation

The two stations share code and may share read-only model services. They do not share mutable station
state. Isolation applies to:
- SQLite databases and migrations.
- Music roots, metadata indexes, histories, schedules, and editorial memory.
- Announcement queues, temporary files, Qwen caches, and emergency playlists.
- Liquidsoap processes, sockets, control interfaces, and runtime files.
- Icecast instances, ports, mounts, source credentials, and listener metrics.
- Logs, incident records, backups, artwork namespaces, and snapshot sequence state.
- Snapshot secrets, nonces, signing identities, and public-status records.

Two Icecast instances on separate local ports are the default. A single external reverse proxy may expose
both canonical mounts. Supervisors restart station processes independently. Stopping, corrupting, or
filling one station queue must leave the other stream and control plane operational.

All database access, filesystem resolution, cache access, metrics, logs, snapshot handling, and stream
control require an explicit validated station context. Missing or mismatched context fails closed.

## Public Snapshot v2

Canonical endpoints:
```text
POST /api/public/stations/{station_id}/snapshot
GET  /api/public/stations/{station_id}/status
```

Every snapshot contains:
- `schema_version: 2`
- Globally unique `snapshot_id`.
- `station_id`, language, locale, and timezone.
- Strictly increasing station-scoped `sequence`.
- `generated_at`, `expires_at`, and delivery timestamp.
- Sanitized state: operational status, current program, now playing, recent tracks, schedule, artwork IDs,
  stream URL, public metrics, and public notices.

Snapshots never contain local paths, private hosts or ports, secrets, prompts, logs, listener identifiers,
operator data, model internals, admin URLs, or raw exception text. Artwork is referenced by validated
station-scoped identifiers, never arbitrary paths or URLs.

### HMAC authentication

Each station has a separate high-entropy secret. The sender signs a canonical byte representation of:

```text
HTTP method + request path + station ID + timestamp + nonce + SHA-256(body)
```

The webserver verifies path identity, station identity, timestamp skew, body hash, constant-time HMAC,
nonce uniqueness, sequence monotonicity, schema, expiry, and payload limits before storing anything.
Nonces are retained through the replay window. Duplicate, expired, replayed, wrong-station, out-of-order,
oversized, malformed, or incorrectly signed snapshots are rejected and audited without storing secrets.

The pusher persists the next sequence, queues the latest unsent snapshot during outages, retries with
bounded exponential backoff and jitter, and never rewrites event time as delivery time. Recovery sends the
newest valid state without duplicating historical snapshots.

Public pages poll their station status and preserve the last valid snapshot during temporary failures.
They report `Live`, `Degraded`, `Stale`, or `Offline` from timestamps and verified runtime state. They never
fabricate listener counts or imply speech is live during music-only degradation.

## Compatibility and Migration

Migration is incremental and preserves the current English station:

1. Freeze Station Profile v1, Snapshot v2, voice-pack, and station-context contracts.
2. Inventory current global paths, settings, database state, endpoints, and process assumptions.
3. Introduce the profile loader and run the existing behavior as `radiotedu-en`.
4. Add station context to storage, queues, caches, logs, artwork, and public-state generation.
5. Copy English state into its station root, verify checksums and row counts, then switch atomically.
6. Commission and sign `radiotedu-en-voices-v1` and `radiotedu-fr-voices-v1`.
7. Add the French profile, independent storage, programming rules, and audio runtime.
8. Introduce Snapshot v2 endpoints and pushers while retaining current English status through an adapter.
9. Publish `/ai/en`, `/ai/fr`, and the `/ai` English alias.
10. Qualify both stations simultaneously, build signed packages, and promote after canary evidence.

Migrations are restartable and backed up before mutation. The old English database remains read-only until
row counts, histories, schedules, artwork, and public status are verified. Rollback returns English to the
previous runtime without attempting to merge French state into it.

## Delegated Agent Execution

The lead agent orchestrates only: freezes contracts, issues bounded task cards, resolves interface changes,
reviews evidence, and integrates after gates pass. Implementation is delegated, primarily to Mini-class
agents, with stronger reasoning agents assigned to architecture, migrations, security, concurrency, and
final audits. At most three implementation agents work simultaneously.

OpenCode may act as an independent external worker or reviewer for architecture, migrations, security,
and cross-checking Mini-agent output. It never bypasses frozen contracts, file-ownership leases, required
tests, independent evidence, or the lead agent's merge gates.

Every task card specifies owned files, forbidden files, frozen interfaces, dependencies, tests, negative
tests, evidence, and commit boundaries. Agents cannot change public contracts or shared schemas without a
lead-approved contract revision. Shared files have one owner per wave. Independent read-only reviewers do
not approve their own implementation.

Execution waves:
1. Architecture contract, repository inventory, dependency map, and ownership matrix.
2. Station Profile v1, station context, Snapshot v2, and Qwen service interfaces.
3. Profile validation, storage migration, state isolation, and compatibility tests.
4. Qwen scheduler, audio validation, cache isolation, and parallel voice commissioning.
5. English/French programming policy, pronunciation dictionaries, and factual grounding.
6. Independent Liquidsoap/Icecast templates, supervisors, silence detection, and emergency music.
7. Snapshot signing, ingestion, replay protection, pusher recovery, and public routes.
8. Broadcast and webserver packaging, installers, backups, diagnostics, and runbooks.
9. Security, isolation, voice, French editorial, accessibility, failure, and soak audits.
10. Bounded remediation, clean-machine installation, signed release, and monitored canary.

Each wave begins only when its dependencies are green. Failed gates produce a bounded remediation card,
not an informal cross-cutting edit.

## Risks and Mitigations

| Risk | Required mitigation |
|---|---|
| Shared GPU causes starvation | Reserved fair queues, station quotas, buffer telemetry, load test |
| Voice identity drifts | Pinned Qwen checksum, signed references, locked prompts, blind recognition tests |
| French sounds translated or unnatural | French-first generation, pronunciation lexicon, native review |
| Cross-station data leakage | Mandatory context, unique roots/secrets, negative isolation tests |
| One stream failure affects both | Separate Liquidsoap and Icecast processes, ports, credentials, supervisors |
| Qwen outage creates dead air | Five-clip buffers, pre-generated IDs, music-only continuity, alerts |
| Snapshot spoofing or replay | Per-station HMAC, nonce store, timestamp window, monotonic sequence |
| Migration damages English history | Backup, checksum/row verification, atomic switch, tested rollback |
| Public UI overstates health | Timestamp-derived state, honest degraded labels, no fabricated metrics |
| Dual runtime exceeds hardware | Concurrent soak measurements; add Qwen worker/GPU rather than reduce quality |

## Acceptance Gates

Contract and compatibility:
- Both profiles validate deterministically and invalid profiles fail before side effects.
- Existing English schedules, history, artwork, public behavior, and `/ai` compatibility remain intact.
- Clean rollback restores the former English runtime from verified backup.

Isolation and security:
- Cross-station database, filesystem, cache, queue, log, secret, artwork, stream, and snapshot access fails.
- Stopping either station leaves the other audio stream and public status operational.
- Wrong-station, invalid, stale, replayed, duplicate, oversized, and out-of-order snapshots are rejected.
- No public response exposes paths, credentials, private endpoints, prompts, logs, or listener identity.

Voice and editorial quality:
- All eight hosts pass at least 60 representative scripts covering every delivery label.
- Human warmth, naturalness, clarity, identity, and program fit average at least 4/5.
- At least 90% of blind clips are assigned to the correct host.
- Native French reviewers approve diction, phrasing, liaison, names, dates, numbers, and cultural tone.
- English and French pronunciation dictionaries pass all station terms and difficult music metadata.
- No generated announcement contains an unverified factual claim or mismatched track introduction.

Audio and resilience:
- A 500-clip synthesis test per language produces no silent, corrupt, clipped, or invalid output.
- Loudness and peak measurements stay within the approved finishing tolerances.
- Both stations maintain five prepared announcements under simultaneous peak generation.
- Killing Qwen keeps both stations playing music, marks degradation, alerts operators, and restores speech
  only after real synthesis health and full buffers return.
- Killing either Liquidsoap or Icecast runtime does not interrupt the other station.
- Both streams complete a simultaneous 24-hour qualification soak without dead air.

Operations and release:
- Broadcast and webserver packages install on clean target machines without the source repository.
- Services start after reboot, rotate logs, expose actionable health, and restore queues safely.
- Backup and restore drills recover both station databases, profiles, schedules, and voice-pack metadata.
- Diagnostic exports exclude secrets and private listener data.
- Signed artifacts record code revision, dependency lock, model checksums, voice-pack versions, and schema.
- A seven-day monitored canary completes with no unresolved severity-one or severity-two defect.

## Completion Definition

The milestone is complete when one signed software release operates two isolated stations from the
broadcasting computer: English at `/ai` and `/ai/en`, French at `/ai/fr`, each with four approved Qwen
hosts, independent programming and streams, station-scoped signed public status, and demonstrated
music-only continuity under Qwen failure. Neither station can read, mutate, queue, cache, stream, sign,
or report as the other.
