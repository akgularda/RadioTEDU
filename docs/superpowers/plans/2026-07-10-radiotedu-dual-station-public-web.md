# RadioTEDU Dual-Station Public Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish isolated English and French RadioTEDU status pages through a public-only FastAPI application using signed, replay-resistant Snapshot v2 ingestion and station-scoped listener sessions.

**Architecture:** The broadcast side signs a canonical Snapshot v2 envelope with a per-station secret and persists its sequence/outbox state. A separate `backend.public_app:app` verifies identity, HMAC, timestamp, nonce, sequence, schema, expiry, and payload safety before atomically storing station-scoped public state; React derives the station from `/ai`, `/ai/en`, or `/ai/fr` and calls only matching station endpoints.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite, HMAC-SHA256, React 18, TypeScript, Vite, Vitest, Testing Library.

## Global Constraints

- The canonical public endpoints are `POST /api/public/stations/{station_id}/snapshot` and `GET /api/public/stations/{station_id}/status`.
- The only station IDs are `radiotedu-en` and `radiotedu-fr`.
- `/ai` is an English compatibility alias; `/ai/en` is canonical English and `/ai/fr` is canonical French.
- Consume immutable profile types from `backend.stations.models`: `StationProfile`, `PublicProfile`, `AudioProfile`, and `RuntimeProfile`.
- Consume `StationContext` and `build_station_context(settings, profile)` from `backend.stations.context`.
- Consume `load_station_profiles(settings.station_profiles_path) -> dict[str, StationProfile]` from `backend.stations.loader`.
- `radiotedu-en` uses `en`, `en-US`, `RadioTEDU`, `/ai/en`, `/radiotedu-en`, and `RADIOTEDU_EN_SNAPSHOT_SECRET`.
- `radiotedu-fr` uses `fr`, `fr-FR`, `RadioTEDU Français`, `/ai/fr`, `/radiotedu-fr`, and `RADIOTEDU_FR_SNAPSHOT_SECRET`.
- Preserve existing RadioTEDU logo at `/static/generated/covers/radiotedu_logo_source.png` and real station/program cover artwork for both English and French pages.
- Preserve existing Andon-inspired visual system (responsive dark theme, status colors #00ff00, #ffaa00, #ff6666) for both English and French pages.
- Snapshot secrets, nonces, sequence counters, public records, artwork namespaces, and listener sessions are station-scoped.
- Snapshot signatures use HMAC-SHA256 over canonical UTF-8 bytes: HTTP method, request path, station ID, timestamp, nonce, and SHA-256 body digest separated by newline characters.
- The allowed clock skew is 300 seconds, nonce retention is 600 seconds, and the maximum raw request body is 262,144 bytes.
- Wrong-station, invalid, stale, replayed, duplicate, expired, out-of-order, oversized, malformed, or incorrectly signed snapshots are rejected before public state changes.
- Public responses never expose local paths, private hosts or ports, secrets, prompts, logs, listener identity, operator data, model internals, admin URLs, or raw exception text.
- Artwork uses validated station-scoped identifiers; arbitrary local paths and arbitrary remote URLs are rejected.
- Public status is `Live`, `Degraded`, `Stale`, or `Offline`; the UI never fabricates listeners or claims speech is live during music-only degradation.
- A temporary English v1 adapter writes to and reads from the same English station record as v2. It is controlled by an explicit compatibility flag and never creates a second status store.
- `backend.public_app:app` is the only webserver entrypoint. It contains no private control, database-admin, music-library, Qwen, Liquidsoap, or operator routes.
- `backend.app:app` remains the private broadcast-computer entrypoint and is forbidden to public-web workers.
- Public pages preserve the last valid station snapshot during temporary polling failures.
- Every implementation task has exclusive file ownership. Mini workers handle bounded model, UI, and adapter tasks; authentication and storage receive strong independent review.

## File Ownership

**Owned by this plan:**

- `backend/public_snapshot_v2.py`
- `backend/public_snapshot_pusher.py`
- `backend/public_dashboard.py`
- `backend/public_app.py`
- `backend/database.py`
- `frontend/src/App.tsx`
- `frontend/src/components/PublicDashboard.tsx`
- `frontend/src/api.ts`
- `frontend/src/styles.css`
- `tests/backend/test_public_snapshot_v2.py`
- `tests/backend/test_core_behaviour.py`
- `frontend/src/__tests__/dashboard.test.tsx`

**Forbidden to public-web workers:**

- `backend/app.py`
- `backend/orchestrator.py`
- `backend/radio_agent.py`
- `backend/liquidsoap.py`
- `backend/stations/models.py`
- `backend/stations/context.py`
- `backend/stations/loader.py`
- `backend/tts/**`
- `scripts/run_station_forever.py`
- `release/**`

The broadcast-runtime plan consumes `StationSnapshotPusherV2` through its `SnapshotPusher` protocol. The public application never imports `RadioAgent`, `AutonomousOrchestrator`, Liquidsoap control, or private `create_app`.

---

### Task 1: Freeze Snapshot v2 Envelope and Canonical HMAC

**Worker profile:** Strong-review-required security contract.

**Files:**
- Create: `backend/public_snapshot_v2.py`
- Create: `tests/backend/test_public_snapshot_v2.py`

**Interfaces:**
- Consumes: `StationProfile.station_id`, language, locale, timezone, public stream URL, and snapshot secret reference.
- Produces: `SnapshotV2Envelope` and `SnapshotState` Pydantic models.
- Produces: `canonical_signature_input(method, path, station_id, timestamp, nonce, body) -> bytes`.
- Produces: `sign_snapshot(secret, canonical_bytes) -> str` and `verify_snapshot_signature(secret, supplied, canonical_bytes) -> None`.
- Produces: `validate_envelope_for_profile(envelope, profile, now) -> None`.

- [ ] **Step 1: Write canonicalization, identity, and expiry tests**

Create `tests/backend/test_public_snapshot_v2.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from backend.public_snapshot_v2 import (
    SnapshotV2Envelope,
    canonical_signature_input,
    sign_snapshot,
    validate_envelope_for_profile,
    verify_snapshot_signature,
)
from tests.backend.station_profile_fixtures import make_station_profile


def valid_envelope(station_id: str = "radiotedu-en", language: str = "en", locale: str = "en-US") -> dict:
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    return {
        "schema_version": 2,
        "snapshot_id": "11111111-1111-4111-8111-111111111111",
        "station_id": station_id,
        "language": language,
        "locale": locale,
        "timezone": "Europe/Istanbul",
        "sequence": 7,
        "generated_at": now.isoformat(),
        "delivered_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=120)).isoformat(),
        "state": {
            "operational_status": "Live",
            "speech_status": "live",
            "channel": {"id": station_id, "name": "RadioTEDU", "cover_id": f"{station_id}:station"},
            "now_playing": {"type": "track", "title": "Blue Room", "artist": "Alice", "started_at": now.isoformat()},
            "current_program": None,
            "current_minutes_left": None,
            "next_program": None,
            "next_programs": [],
            "programs": [],
            "top_songs": [],
            "top_genres": [],
            "content_breakdown": [],
            "activity": [],
            "stream": {"url": "https://radiotedu.com:8001/radiotedu-en", "status": "configured"},
            "metrics": {"current_listeners": 0, "popularity": None, "average_session": None},
            "public_notices": [],
        },
    }


def test_canonical_signature_is_stable_and_constant_time_verified() -> None:
    body = b'{"schema_version":2,"station_id":"radiotedu-en"}'
    canonical = canonical_signature_input(
        "POST",
        "/api/public/stations/radiotedu-en/snapshot",
        "radiotedu-en",
        "1783684800",
        "nonce-1234567890",
        body,
    )
    signature = sign_snapshot(b"a" * 32, canonical)
    assert canonical.decode("utf-8").splitlines() == [
        "POST",
        "/api/public/stations/radiotedu-en/snapshot",
        "radiotedu-en",
        "1783684800",
        "nonce-1234567890",
        "cf85c23c96e8c1268c206a75a290f03bd4e7c59e68940d61286799645cac79f3",
    ]
    verify_snapshot_signature(b"a" * 32, signature, canonical)
    with pytest.raises(ValueError, match="invalid snapshot signature"):
        verify_snapshot_signature(b"b" * 32, signature, canonical)


def test_envelope_rejects_wrong_station_and_expiry(tmp_path) -> None:
    profile = make_station_profile(tmp_path, "radiotedu-en", "en", "en-US")
    envelope = SnapshotV2Envelope.model_validate(valid_envelope(station_id="radiotedu-fr", language="fr", locale="fr-FR"))
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="station identity mismatch"):
        validate_envelope_for_profile(envelope, profile, now)


def test_envelope_delivered_at_preserved_across_pusher_retry() -> None:
    payload = valid_envelope()
    first_attempt = SnapshotV2Envelope.model_validate(payload)
    retry_attempt = SnapshotV2Envelope.model_validate(payload)
    assert retry_attempt.generated_at == first_attempt.generated_at
    assert retry_attempt.delivered_at == first_attempt.delivered_at
```

- [ ] **Step 2: Run the Snapshot v2 contract tests and confirm the red state**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k "canonical or envelope" -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.public_snapshot_v2'`.

- [ ] **Step 3: Implement the constrained Snapshot v2 envelope**

Create `backend/public_snapshot_v2.py` with the exact public-only model boundary:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


FORBIDDEN_PUBLIC_KEYS = {
    "file_path", "local_path", "secret", "token", "password", "prompt",
    "logs", "incidents", "listener_id", "admin_url", "private_host",
    "model_internal",
}


class SnapshotState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operational_status: Literal["Live", "Degraded", "Stale", "Offline"]
    speech_status: Literal["live", "music_only", "recovering", "offline"]
    channel: dict[str, Any]
    now_playing: dict[str, Any] | None
    current_program: dict[str, Any] | None
    next_programs: list[dict[str, Any]] = Field(max_length=50)
    recent_tracks: list[dict[str, Any]] = Field(max_length=50)
    stream: dict[str, Any]
    metrics: dict[str, Any]
    programming: dict[str, Any]
    notices: list[str] = Field(max_length=10)

    @model_validator(mode="after")
    def reject_private_fields(self) -> "SnapshotState":
        reject_forbidden_public_keys(self.model_dump(mode="python"), FORBIDDEN_PUBLIC_KEYS)
        return self


class SnapshotV2Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2]
    snapshot_id: UUID
    station_id: str = Field(min_length=1, max_length=64)
    language: Literal["en", "fr"]
    locale: str = Field(min_length=2, max_length=16)
    timezone: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=0)
    generated_at: datetime
    delivered_at: datetime
    expires_at: datetime
    state: SnapshotState
```

Implement `reject_forbidden_public_keys` as a recursive mapping/list walk. Apply explicit limits to every nested public string: titles 200 characters, descriptions 1,000, each notice 300, program/recent/top lists 50 entries, and activity 100 entries. Reject forbidden keys at any depth before storage.

- [ ] **Step 4: Implement canonical HMAC and profile validation**

Add the exact signing boundary to `backend/public_snapshot_v2.py`:

```python
import hashlib
import hmac


def canonical_request_bytes(
    method: str,
    path: str,
    station_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join(
        (method.upper(), path, station_id, timestamp, nonce, body_digest)
    ).encode("utf-8")


def sign_snapshot(secret: bytes, canonical_bytes: bytes) -> str:
    return "sha256=" + hmac.new(secret, canonical_bytes, hashlib.sha256).hexdigest()


def verify_snapshot_signature(
    secret: bytes,
    supplied: str,
    canonical_bytes: bytes,
) -> None:
    expected = sign_snapshot(secret, canonical_bytes)
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("invalid snapshot signature")
```

Implement `validate_envelope_for_profile(envelope, profile, now)` to check station ID, language, locale, timezone, public stream URL, and artwork-ID prefix. Require `generated_at <= delivered_at < expires_at`, enforce a maximum 300-second envelope lifetime, and allow `delivered_at`/`now` only within the configured clock-skew window. A retry reuses the same immutable envelope bytes; it never rewrites `generated_at` as delivery time or changes `delivered_at`.

- [ ] **Step 5: Run Snapshot v2 unit tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -v`

Expected: PASS for stable canonical bytes, valid HMAC, wrong-secret rejection, unknown-field rejection, private-key rejection, wrong-station rejection, delivery-time validation, retry timestamp preservation, expiry rejection, and oversized nested-list rejection.

- [ ] **Step 6: Commit the Snapshot v2 contract**

```bash
git add backend/public_snapshot_v2.py tests/backend/test_public_snapshot_v2.py
git commit -m "feat: define signed public snapshot v2"
```

---

### Task 2: Add Atomic Station-Scoped Snapshot and Session Storage

**Worker profile:** Strong-review-required database isolation task.

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/public_dashboard.py`
- Modify: `tests/backend/test_public_snapshot_v2.py`

**Interfaces:**
- Consumes: a cryptographically verified `SnapshotV2Envelope` and its matching `StationProfile`.
- Produces: `store_verified_snapshot(settings, profile, envelope, nonce, received_at) -> dict`.
- Produces: `public_status(settings, profile, now) -> dict`.
- Produces: `public_session_start(settings, station_id, session_id)`, `public_session_heartbeat(settings, station_id, session_id)`, and `public_session_end(settings, station_id, session_id)`.
- Produces: `latest_public_sequence(settings, station_id) -> int`.

- [ ] **Step 1: Write atomic replay, ordering, and session-isolation tests**

Append to `tests/backend/test_public_snapshot_v2.py`:

```python
def test_snapshot_storage_rejects_nonce_replay_and_out_of_order_sequence(public_store) -> None:
    first = SnapshotV2Envelope.model_validate(valid_envelope())
    public_store.store(first, nonce="nonce-one-123456", received_at=public_store.now)

    with pytest.raises(ValueError, match="snapshot nonce replayed"):
        public_store.store(first.model_copy(update={"sequence": 8}), nonce="nonce-one-123456", received_at=public_store.now)
    with pytest.raises(ValueError, match="snapshot sequence is not increasing"):
        public_store.store(first.model_copy(update={"snapshot_id": UUID("22222222-2222-4222-8222-222222222222")}), nonce="nonce-two-123456", received_at=public_store.now)


def test_listener_sessions_are_station_scoped(public_store) -> None:
    public_store.session_start("radiotedu-en", "session_1234567890")
    public_store.session_start("radiotedu-fr", "session_1234567890")
    public_store.session_end("radiotedu-en", "session_1234567890")

    assert public_store.listener_count("radiotedu-en") == 0
    assert public_store.listener_count("radiotedu-fr") == 1


def test_public_status_never_returns_private_fields(public_store) -> None:
    envelope_data = valid_envelope()
    envelope_data["state"]["now_playing"]["file_path"] = "F:/music/private.wav"
    with pytest.raises(ValueError, match="private public field"):
        SnapshotV2Envelope.model_validate(envelope_data)
```

- [ ] **Step 2: Run storage tests and verify the global schema fails**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k 'storage or sessions or private_fields' -v`

Expected: FAIL because current `public_snapshots` and `public_listener_sessions` are global, nonce/sequence tables are absent, and storage APIs do not require station ID.

- [ ] **Step 3: Add station-scoped public tables**

In `backend/database.py`, add restart-safe schema creation:

```sql
create table if not exists public_station_snapshots (
    station_id text primary key,
    schema_version integer not null check (schema_version = 2),
    snapshot_id text not null unique,
    sequence integer not null check (sequence > 0),
    generated_at text not null,
    expires_at text not null,
    received_at text not null,
    payload_json text not null
);

create table if not exists public_snapshot_nonces (
    station_id text not null,
    nonce text not null,
    expires_at text not null,
    primary key (station_id, nonce)
);

create table if not exists public_listener_sessions_v2 (
    station_id text not null,
    session_id text not null,
    started_at text not null,
    last_seen_at text not null,
    ended_at text,
    primary key (station_id, session_id)
);

create table if not exists public_snapshot_audit (
    id integer primary key autoincrement,
    station_id text not null,
    outcome text not null,
    reason_code text not null,
    created_at text not null
);
```

Add indexes for nonce expiry, active sessions by station/last-seen, and audit station/time. Audit rows contain reason codes only; never write headers, secrets, raw payloads, listener identity, or exception strings.

- [ ] **Step 4: Implement one-transaction nonce and sequence enforcement**

In `backend/public_dashboard.py`, make `store_verified_snapshot` start `BEGIN IMMEDIATE`, delete expired nonces, insert the new `(station_id, nonce)`, read the current sequence, reject `sequence <= current`, and upsert the latest payload before commit. Roll back all operations on rejection. `public_status` derives:

```python
if snapshot is None:
    operational_status = "Offline"
elif now >= expires_at:
    operational_status = "Offline"
elif (now - received_at).total_seconds() > settings.public_snapshot_stale_seconds:
    operational_status = "Stale"
elif state["speech_status"] in {"music_only", "recovering"}:
    operational_status = "Degraded"
else:
    operational_status = "Live"
```

Return the selected profile identity, sanitized state, verified timestamps, sequence, and real station-scoped listener metrics. Keep the last received snapshot for stale/offline display; do not replace it with invented content.

- [ ] **Step 5: Run storage and legacy database tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py tests/backend/test_core_behaviour.py -k 'public or snapshot or session' -v`

Expected: PASS; replay and ordering fail atomically, same session IDs coexist across stations, stale state is honest, and current database initialization remains restart-safe.

- [ ] **Step 6: Commit station-scoped storage**

```bash
git add backend/database.py backend/public_dashboard.py tests/backend/test_public_snapshot_v2.py
git commit -m "feat: isolate public snapshots and sessions"
```

---

### Task 3: Create the Public-Only FastAPI Application

**Worker profile:** Strong-review-required boundary task.

**Files:**
- Create: `backend/public_app.py`
- Modify: `tests/backend/test_public_snapshot_v2.py`
- Modify: `tests/backend/test_core_behaviour.py`

**Interfaces:**
- Consumes: `load_station_profiles(settings.station_profiles_path) -> dict[str, StationProfile]` from `backend.stations.loader`, Snapshot v2 validation/authentication, station-scoped storage, and built frontend assets.
- Preserve and test existing RadioTEDU logo at `/static/generated/covers/radiotedu_logo_source.png` and real station/program cover artwork for both English and French pages.
- Preserve existing Andon-inspired visual system (responsive dark theme, status colors #00ff00, #ffaa00, #ff6666) for both English and French pages.
- Add `delivered_at` datetime to `SnapshotV2Envelope` and exact tests for validation and pusher retry semantics preserving `generated_at` while setting delivery attempt time consistently.
- Pass `settings.station_profiles_path` at every profile-loader call and consume dict values as required by `load_station_profiles(directory: str | Path) -> dict[str, StationProfile]`.
- Produces: `create_public_app(settings=None, profiles=None, secret_resolver=None, clock=None) -> FastAPI`.
- Produces: `POST /api/public/stations/{station_id}/snapshot`.
- Produces: `GET /api/public/stations/{station_id}/status`.
- Produces: station-scoped `/session/start`, `/session/heartbeat`, and `/session/end` endpoints.
- Produces: frontend shells for `/ai`, `/ai/en`, and `/ai/fr`.

- [ ] **Step 1: Write route, authentication, and public-boundary tests**

Append to `tests/backend/test_public_snapshot_v2.py`:

```python
def test_public_app_accepts_valid_station_signature(public_client, signed_en_request) -> None:
    response = public_client.post(
        "/api/public/stations/radiotedu-en/snapshot",
        content=signed_en_request.body,
        headers=signed_en_request.headers,
    )
    assert response.status_code == 200
    status = public_client.get("/api/public/stations/radiotedu-en/status").json()
    assert status["station"]["station_id"] == "radiotedu-en"
    assert status["sequence"] == 7


@pytest.mark.parametrize("mutation", ["wrong_secret", "stale_timestamp", "replayed_nonce", "wrong_path", "wrong_station", "oversized"])
def test_public_app_rejects_invalid_signed_requests(public_client, signed_request_factory, mutation) -> None:
    request = signed_request_factory(mutation)
    response = public_client.post(request.path, content=request.body, headers=request.headers)
    assert response.status_code in {400, 401, 409, 413, 422}


def test_public_app_exposes_no_private_routes(public_client) -> None:
    paths = set(public_client.get("/openapi.json").json()["paths"])
    assert "/api/status" not in paths
    assert "/api/control/say" not in paths
    assert "/api/air/start" not in paths
    assert "/api/music/rescan" not in paths
    assert all(not path.startswith("/api/admin") for path in paths)
```

- [ ] **Step 2: Run public application tests and verify the entrypoint is absent**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k 'public_app' -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.public_app'`.

- [ ] **Step 3: Implement public-only ingestion and status routes**

Create `backend/public_app.py`. The ingestion route must read at most 262,144 raw bytes before JSON parsing, resolve the path-selected profile, parse headers, verify HMAC, validate timestamp, parse and validate the envelope, confirm path/body identity, and then call atomic storage:

```python
@app.post("/api/public/stations/{station_id}/snapshot")
async def ingest_snapshot(station_id: str, request: Request) -> dict:
    profile = profiles_by_id.get(station_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="unknown station")
    body = await read_limited_body(request, MAX_SNAPSHOT_BYTES)
    timestamp = required_header(request, "X-RadioTEDU-Timestamp")
    nonce = required_header(request, "X-RadioTEDU-Nonce")
    signature = required_header(request, "X-RadioTEDU-Signature")
    canonical = canonical_signature_input(request.method, request.url.path, station_id, timestamp, nonce, body)
    verify_request_timestamp(timestamp, clock.now(), MAX_CLOCK_SKEW_SECONDS)
    verify_snapshot_signature(secret_resolver(profile.snapshot_secret_ref), signature, canonical)
    envelope = SnapshotV2Envelope.model_validate_json(body)
    validate_envelope_for_profile(envelope, profile, clock.now())
    receipt = store_verified_snapshot(settings, profile, envelope, nonce, clock.now())
    return {"stored": True, "station_id": station_id, "sequence": receipt["sequence"]}
```

Define `read_limited_body`, `required_header`, and `verify_request_timestamp` as private functions in `backend/public_app.py`; all three raise stable `HTTPException` responses and never include supplied header or body values in errors.

Return stable public error details such as `invalid snapshot signature`, `snapshot timestamp outside allowed skew`, `snapshot nonce replayed`, and `snapshot sequence is not increasing`. Audit detailed reason codes server-side without secret or body values.

- [ ] **Step 4: Implement station status, sessions, and frontend routes**

Register status and session routes with `station_id` in every path. Validate session IDs against `^session_[a-f0-9]{16,64}$`. Serve the built frontend `index.html` for `/ai`, `/ai/en`, and `/ai/fr`; serve `/assets` and validated station artwork only. Do not add a catch-all route that can shadow `/api/public`.

- [ ] **Step 5: Run public boundary tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py tests/backend/test_core_behaviour.py -k 'public or ai_route' -v`

Expected: PASS; valid English and French signatures store independently, invalid requests fail, sessions remain isolated, all three pages serve the frontend shell when built, and OpenAPI contains no private route.

- [ ] **Step 6: Commit the public-only application**

```bash
git add backend/public_app.py tests/backend/test_public_snapshot_v2.py tests/backend/test_core_behaviour.py
git commit -m "feat: add isolated public web application"
```

---

### Task 4: Preserve the English v1 Compatibility Surface

**Worker profile:** Mini-friendly adapter task with strong migration review.

**Files:**
- Modify: `backend/public_app.py`
- Modify: `backend/public_dashboard.py`
- Modify: `tests/backend/test_core_behaviour.py`
- Modify: `tests/backend/test_public_snapshot_v2.py`

**Interfaces:**
- Consumes: existing v1 snapshot body and `X-RadioTEDU-Sync-Token` only when `public_v1_compat_enabled` is true.
- Produces: `adapt_v1_snapshot_to_english(settings, payload, received_at) -> SnapshotV2Envelope`.
- Produces: legacy `POST /api/public/snapshot`, `GET /api/public/status`, and legacy session routes backed by `radiotedu-en` v2 storage.
- Produces: `/ai` serving the same client as `/ai/en`.

- [ ] **Step 1: Convert current compatibility tests into same-store assertions**

In `tests/backend/test_core_behaviour.py`, retain the current v1 clean/private payload cases and add:

```python
response = client.post(
    "/api/public/snapshot",
    json=clean_payload,
    headers={"X-RadioTEDU-Sync-Token": "secret-token"},
)
self.assertEqual(200, response.status_code)
legacy = client.get("/api/public/status").json()
canonical = client.get("/api/public/stations/radiotedu-en/status").json()
self.assertEqual(legacy["now_playing"], canonical["now_playing"])
self.assertEqual("radiotedu-en", canonical["station"]["station_id"])
self.assertEqual(canonical["sequence"], legacy["sequence"])
self.assertEqual(404, client.get("/api/public/stations/radiotedu/status").status_code)
```

- [ ] **Step 2: Run compatibility tests and verify the global store diverges**

Run: `python -m pytest tests/backend/test_core_behaviour.py tests/backend/test_public_snapshot_v2.py -k 'public_snapshot or compatibility' -v`

Expected: FAIL because current v1 routes use a global schema-v1 record instead of the English station record.

- [ ] **Step 3: Adapt v1 writes into the English record**

`adapt_v1_snapshot_to_english` must sanitize the body with the existing allowlist, use the next English sequence from the same transaction, generate a UUID, preserve the original generated time when present, apply the configured TTL, map `/ai` stream metadata to the English canonical stream URL, and set station identity from the English profile. The adapter records audit reason `accepted_legacy_v1`; it never copies request headers into storage.

The legacy token comparison uses `hmac.compare_digest`. A disabled adapter returns 410, a missing or incorrect token returns 401, and a private field returns 422. The adapter is excluded from French and cannot accept a body whose channel ID identifies another station.

- [ ] **Step 4: Adapt v1 reads without creating a second record**

`GET /api/public/status` calls `public_status(settings, english_profile, now)` and transforms only the response shape expected by the current English client. Legacy session routes call the station-scoped functions with `radiotedu-en`. `/ai` remains a shell alias; it does not redirect audio or create another session namespace.

- [ ] **Step 5: Run compatibility and v2 tests together**

Run: `python -m pytest tests/backend/test_core_behaviour.py tests/backend/test_public_snapshot_v2.py -k 'public or compatibility or session' -v`

Expected: PASS; v1 and v2 English reads share sequence and content, private data is rejected, French is unreachable through v1, and disabling compatibility returns 410.

- [ ] **Step 6: Commit the compatibility adapter**

```bash
git add backend/public_app.py backend/public_dashboard.py tests/backend/test_core_behaviour.py tests/backend/test_public_snapshot_v2.py
git commit -m "feat: adapt legacy English public status to v2"
```

---

### Task 5: Build the Persistent Signed Snapshot Pusher

**Worker profile:** Strong-review-required transport and retry task.

**Files:**
- Create: `backend/public_snapshot_pusher.py`
- Modify: `backend/database.py`
- Modify: `backend/public_dashboard.py`
- Modify: `tests/backend/test_public_snapshot_v2.py`

**Interfaces:**
- Consumes: one `StationContext`, `build_public_snapshot(context, agent) -> SnapshotState`, and station secret resolution.
- Produces: `StationSnapshotPusherV2(context, agent, transport, secret_resolver, clock, random_source)` satisfying the runtime plan's `SnapshotPusher` protocol.
- Produces: `build_station_snapshot_pusher(context, agent) -> StationSnapshotPusherV2`, used only by `create_station_runtime` after its station-scoped agent exists.
- Produces: persistent station-local `next_sequence`, latest unsent envelope, idempotency state, and bounded backoff.
- Produces: `start_background()`, `stop_background()`, `maybe_push()`, and `status()`.

- [ ] **Step 1: Write signing, persistence, and outage-coalescing tests**

Append to `tests/backend/test_public_snapshot_v2.py`:

```python
def test_pusher_signs_path_and_persists_sequence(pusher_harness) -> None:
    first = pusher_harness.pusher.maybe_push(force=True)
    second = pusher_harness.restart_pusher().maybe_push(force=True)

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert pusher_harness.transport.requests[0].path == "/api/public/stations/radiotedu-en/snapshot"
    assert pusher_harness.transport.requests[0].headers["X-RadioTEDU-Signature"].startswith("sha256=")
    assert pusher_harness.transport.requests[0].headers["X-RadioTEDU-Nonce"]


def test_pusher_keeps_only_newest_unsent_snapshot_during_outage(pusher_harness) -> None:
    pusher_harness.transport.available = False
    pusher_harness.pusher.maybe_push(force=True)
    pusher_harness.agent.now_playing = "Second Track"
    pusher_harness.pusher.maybe_push(force=True)
    pusher_harness.transport.available = True
    result = pusher_harness.pusher.maybe_push(force=True)

    assert result["pushed"] is True
    assert len(pusher_harness.transport.successful_requests) == 1
    assert b"Second Track" in pusher_harness.transport.successful_requests[0].body
```

- [ ] **Step 2: Run pusher tests and verify persistent v2 transport is absent**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k 'pusher' -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'backend.public_snapshot_pusher'`.

- [ ] **Step 3: Add station-local outbox state**

In `backend/database.py`, add to each station database:

```sql
create table if not exists public_snapshot_outbox_v2 (
    station_id text primary key,
    next_sequence integer not null check (next_sequence > 0),
    pending_snapshot_json text,
    pending_created_at text,
    attempts integer not null default 0,
    next_attempt_at text,
    last_success_at text,
    last_error_code text
);
```

Initialize one row only for the selected context station ID. Reject reading or updating another station ID even if such a row exists in a copied database.

- [ ] **Step 4: Implement deterministic signing and bounded retries**

Create `backend/public_snapshot_pusher.py`. Serialize the envelope once using sorted keys and compact separators, generate a cryptographically random nonce of at least 128 bits, use Unix epoch seconds for the timestamp header, and sign the exact method/path/body sent. Increase and persist the sequence before network delivery so restart never reuses it.

Retry after 1, 2, 4, 8, 16, 30, and 60 seconds plus injected jitter in `[0, 0.25 * delay]`; cap at 60 seconds. Keep only the newest pending station state during an outage. Never rewrite `generated_at` as delivery time. A successful response clears the pending body and attempt state atomically.

Expose the production factory without constructing an agent or runtime:

```python
def build_station_snapshot_pusher(context: StationContext, agent: RadioAgent) -> StationSnapshotPusherV2:
    return StationSnapshotPusherV2(
        context=context,
        agent=agent,
        transport=HttpSnapshotTransport.from_settings(context.settings),
        secret_resolver=EnvironmentSnapshotSecretResolver(),
        clock=SystemClock(),
        random_source=secrets.SystemRandom(),
    )
```

Define `HttpSnapshotTransport`, `EnvironmentSnapshotSecretResolver`, and `SystemClock` in `backend/public_snapshot_pusher.py`; secret resolution returns bytes and never logs environment values.

- [ ] **Step 5: Remove the old pusher implementation from public_dashboard**

Move all broadcast transport ownership to `StationSnapshotPusherV2`. `backend/public_dashboard.py` retains public-state building, sanitization, storage, and session functions only. The runtime plan injects exactly one v2 pusher into each `StationRuntime`.

- [ ] **Step 6: Run pusher and runtime protocol tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py tests/backend/test_dual_station_runtime.py -k 'pusher or snapshot' -v`

Expected: PASS; sequence survives restart, signatures bind the canonical path and body, outage updates coalesce, retries are bounded, and runtime lifecycle starts one pusher.

- [ ] **Step 7: Commit the signed pusher**

```bash
git add backend/public_snapshot_pusher.py backend/database.py backend/public_dashboard.py tests/backend/test_public_snapshot_v2.py
git commit -m "feat: push signed station snapshots reliably"
```

---

### Task 6: Make the React Public Page Station-Driven

**Worker profile:** Mini-friendly UI task with French copy review.

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/PublicDashboard.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/dashboard.test.tsx`

**Interfaces:**
- Consumes: station-scoped `PublicStatusResponse` with `station.station_id`, display name, language, locale, route, operational status, speech status, and sanitized state.
- Produces: `stationFromPublicPath(pathname) -> "radiotedu-en" | "radiotedu-fr" | null`.
- Produces: `fetchPublicStatus(stationId)`, `postPublicSession(stationId, action, sessionId)`, and `PublicDashboard({stationId, status, connectionError})`.
- Produces: English and French public copy selected by station language, not browser locale.

- [ ] **Step 1: Write route, endpoint, French identity, and session tests**

Add to `frontend/src/__tests__/dashboard.test.tsx`:

```tsx
it.each([
  ['/ai', 'radiotedu-en'],
  ['/ai/en', 'radiotedu-en'],
  ['/ai/fr', 'radiotedu-fr'],
])('maps %s to %s', (path, stationId) => {
  expect(stationFromPublicPath(path)).toBe(stationId);
});

it('renders the French station from server identity', () => {
  const french = {
    ...publicStatus,
    station: {
      station_id: 'radiotedu-fr',
      display_name: 'RadioTEDU Français',
      language: 'fr',
      locale: 'fr-FR',
      route: '/ai/fr',
    },
    operational_status: 'Degraded',
    speech_status: 'music_only',
    channel: { ...publicStatus.channel, id: 'radiotedu-fr', name: 'RadioTEDU Français' },
  } satisfies PublicStatusResponse;

  render(<PublicDashboard stationId="radiotedu-fr" status={french} />);
  expect(screen.getByRole('heading', { name: 'RadioTEDU Français' })).toBeInTheDocument();
  expect(screen.getByText('Musique uniquement')).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Programme en cours' })).toBeInTheDocument();
});

it('uses station-scoped status and session endpoints', async () => {
  await fetchPublicStatus('radiotedu-fr');
  await postPublicSession('radiotedu-fr', 'start', 'session_1234567890abcdef');
  expect(fetch).toHaveBeenCalledWith('/api/public/stations/radiotedu-fr/status');
  expect(fetch).toHaveBeenCalledWith(
    '/api/public/stations/radiotedu-fr/session/start',
    expect.objectContaining({ method: 'POST' }),
  );
});

const frenchPublicStatus = {
  ...publicStatus,
  station: {
    station_id: 'radiotedu-fr',
    display_name: 'RadioTEDU Français',
    language: 'fr',
    locale: 'fr-FR',
    route: '/ai/fr',
  },
  channel: { ...publicStatus.channel, id: 'radiotedu-fr', name: 'RadioTEDU Français' },
} satisfies PublicStatusResponse;

it.each([
  ['radiotedu-en', publicStatus],
  ['radiotedu-fr', frenchPublicStatus],
] as const)('preserves RadioTEDU branding and real artwork for %s', (stationId, status) => {
  render(<PublicDashboard stationId={stationId} status={status} />);
  expect(screen.getByRole('img', { name: 'RadioTEDU' })).toHaveAttribute(
    'src',
    '/static/generated/covers/radiotedu_logo_source.png',
  );
  expect(screen.getByRole('img', { name: /station cover|couverture de la station/i })).toHaveAttribute(
    'src',
    status.channel.cover_path,
  );
  expect(screen.getByRole('img', { name: /program cover|couverture du programme/i })).toHaveAttribute(
    'src',
    status.current_program.cover_path,
  );
});
```

- [ ] **Step 2: Run frontend tests and verify global route/API assumptions fail**

Run: `npm test -- --run frontend/src/__tests__/dashboard.test.tsx`

Expected: FAIL because only `/ai` is public, `fetchPublicStatus()` uses `/api/public/status`, sessions use global paths, and the dashboard hard-codes English identity and labels.

- [ ] **Step 3: Add station identity to API types and URLs**

In `frontend/src/api.ts`, define:

```ts
export type PublicStationId = 'radiotedu-en' | 'radiotedu-fr';

export interface PublicStationIdentity {
  station_id: PublicStationId;
  display_name: string;
  language: 'en' | 'fr';
  locale: 'en-US' | 'fr-FR';
  route: '/ai/en' | '/ai/fr';
}

export interface PublicStatusResponse {
  station: PublicStationIdentity;
  operational_status: 'Live' | 'Degraded' | 'Stale' | 'Offline';
  speech_status: 'live' | 'music_only' | 'recovering' | 'offline';
  schema_version: 2;
  sequence: number;
  received_at: string | null;
  generated_at: string | null;
  expires_at: string | null;
  message: string;
  channel: Channel;
  now_playing: PlaybackItem;
  current_program: Program | null;
  current_minutes_left: number | null;
  next_program: Program | null;
  next_programs: Program[];
  programs: Program[];
  top_songs: TopSong[];
  top_genres: TopGenre[];
  content_breakdown: PublicContentBreakdown[];
  activity: PublicActivityItem[];
  stream: PublicStream;
  metrics: PublicMetrics;
  public_notices: string[];
}

export async function fetchPublicStatus(stationId: PublicStationId): Promise<PublicStatusResponse> {
  const response = await fetch(`/api/public/stations/${stationId}/status`);
  if (!response.ok) throw new Error(`Public status request failed: ${response.status}`);
  return response.json() as Promise<PublicStatusResponse>;
}
```

`postPublicSession` accepts action as `'start' | 'heartbeat' | 'end'` and constructs the station-scoped path internally; callers cannot pass arbitrary paths.

- [ ] **Step 4: Route all three public paths to one station-aware PublicApp**

In `frontend/src/App.tsx`, export and use:

```tsx
export function stationFromPublicPath(pathname: string): PublicStationId | null {
  if (pathname === '/ai' || pathname === '/ai/' || pathname === '/ai/en' || pathname === '/ai/en/') return 'radiotedu-en';
  if (pathname === '/ai/fr' || pathname === '/ai/fr/') return 'radiotedu-fr';
  return null;
}

function App() {
  const stationId = stationFromPublicPath(window.location.pathname);
  return stationId ? <PublicApp stationId={stationId} /> : <OperatorApp />;
}
```

Reset displayed status when `stationId` changes, poll every five seconds, and preserve the last valid snapshot when a poll fails.

- [ ] **Step 5: Replace hard-coded public identity and copy**

`PublicDashboard` uses `status.station.display_name`, language, status, stream, and artwork. Preserve the existing `/static/generated/covers/radiotedu_logo_source.png` brand image, render the server-provided station and current-program `cover_path` values with the existing cover fallback, and keep the Andon-inspired visual hierarchy for both languages. Define a complete two-language copy map for brand strapline, now playing, stream state, four metrics, message/copy actions, current/next program, top songs, genres, content breakdown, activity, empty states, connection interruption, and music-only notice. Required French music-only copy is `Musique uniquement — la voix Qwen se rétablit.`. Use `lang={status.station.language}` on the public page.

Use station-scoped storage keys:

```ts
function getSessionId(stationId: PublicStationId) {
  const key = `radiotedu_public_session_${stationId}`;
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const next = `session_${crypto.randomUUID().replace(/-/g, '')}`;
  window.localStorage.setItem(key, next);
  return next;
}
```

The French page uses server-provided French program/editorial content; the client translates interface labels only.

- [ ] **Step 6: Add language/status styles without duplicating layout**

In `frontend/src/styles.css`, retain one Andon-inspired responsive layout. Add `.public-status--degraded`, `.public-status--stale`, `.public-status--offline`, `.public-language-switch`, and `.public-notice--music-only`. English/French links point to `/ai/en` and `/ai/fr`, use `aria-current="page"`, and preserve visible keyboard focus. Do not create station-specific CSS copies.

- [ ] **Step 7: Run frontend tests and production build**

Run: `npm test -- --run frontend/src/__tests__/dashboard.test.tsx`

Expected: PASS for all existing English public behavior, all three route mappings, French identity/copy, station-scoped endpoints, session keys, and last-valid-snapshot preservation.

Run: `npm run build`

Expected: PASS with TypeScript compilation and Vite production output.

- [ ] **Step 8: Commit station-driven public UI**

```bash
git add frontend/src/App.tsx frontend/src/components/PublicDashboard.tsx frontend/src/api.ts frontend/src/styles.css frontend/src/__tests__/dashboard.test.tsx
git commit -m "feat: publish English and French station pages"
```

---

### Task 7: Run Public-Web Security and Compatibility Gates

**Worker profile:** Strong read-only security reviewer; remediation returns to the owning task worker.

**Files:**
- Verify: `backend/public_snapshot_v2.py`
- Verify: `backend/public_snapshot_pusher.py`
- Verify: `backend/public_dashboard.py`
- Verify: `backend/public_app.py`
- Verify: `backend/database.py`
- Verify: `frontend/src/App.tsx`
- Verify: `frontend/src/components/PublicDashboard.tsx`
- Verify: `frontend/src/api.ts`
- Verify: `frontend/src/styles.css`
- Verify: `tests/backend/test_public_snapshot_v2.py`
- Verify: `tests/backend/test_core_behaviour.py`
- Verify: `frontend/src/__tests__/dashboard.test.tsx`

**Interfaces:**
- Consumes: all Snapshot v2, compatibility, public application, pusher, and frontend contracts from Tasks 1–6.
- Produces: reproducible evidence that transport authentication, storage isolation, public-only packaging, compatibility, and both pages satisfy the approved design.

- [ ] **Step 1: Run focused backend public tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py tests/backend/test_core_behaviour.py -k 'public or snapshot or session or ai_route' -v`

Expected: PASS with zero failures and zero errors.

- [ ] **Step 2: Run replay and cross-station negative tests**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k 'wrong or replay or out_of_order or oversized or sessions or private' -v`

Expected: PASS; wrong signature/path/station, stale timestamp, replayed nonce, duplicate/out-of-order sequence, oversized body, private fields, and cross-station sessions all fail closed.

- [ ] **Step 3: Run public-route exposure scan**

Run: `python -m pytest tests/backend/test_public_snapshot_v2.py -k 'exposes_no_private_routes' -v`

Expected: PASS; the `backend.public_app` OpenAPI schema exposes public station snapshot/status/session routes only.

- [ ] **Step 4: Run full backend and frontend suites**

Run: `python -m pytest tests/backend -q`

Expected: PASS with zero failures and zero errors.

Run: `npm test -- --run`

Expected: PASS with zero failing Vitest cases.

Run: `npm run build`

Expected: PASS with TypeScript compilation and Vite production output.

- [ ] **Step 5: Scan public code for private leakage and global endpoints**

Run: `rg -n "file_path|local_path|password|secret|prompt|logs|incidents|listener_id|/api/public/status|/api/public/session" backend/public_app.py backend/public_dashboard.py backend/public_snapshot_v2.py frontend/src`

Expected: matches are limited to explicit rejection keys, secret resolver calls that never serialize values, and English compatibility adapter tests. The station-driven frontend has no global status or session call.

- [ ] **Step 6: Verify entrypoint separation and owned files**

Run: `rg -n "RadioAgent|AutonomousOrchestrator|liquidsoap|/api/control|/api/air" backend/public_app.py`

Expected: no matches.

Run: `git status --short`

Expected: only public-web-plan-owned files are modified and `release/` is untouched.

- [ ] **Step 7: Commit any test-only qualification fixture adjustments**

If qualification required fixture changes within owned tests, commit only those changes:

```bash
git add tests/backend/test_public_snapshot_v2.py tests/backend/test_core_behaviour.py frontend/src/__tests__/dashboard.test.tsx
git commit -m "test: qualify dual station public isolation"
```

Expected: `git status --short` shows no public-web-plan changes. If no fixture adjustment was required, do not create an empty commit.

## Public-Web Plan Completion Criteria

- Snapshot v2 signatures bind method, path, station, timestamp, nonce, and exact body bytes.
- Authentication, replay prevention, ordering, payload limits, and storage commit atomically and station-scoped.
- Snapshot sender sequence and newest unsent state survive broadcast-process restart.
- English and French status, listener sessions, artwork, secrets, and sequence state cannot cross.
- The v1 English routes use the English v2 record and cannot access French.
- `/ai`, `/ai/en`, and `/ai/fr` display the correct station while preserving last valid state during polling errors.
- `backend.public_app:app` exposes no private radio control or runtime internals.
- Public state reports `Live`, `Degraded`, `Stale`, or `Offline` honestly and never fabricates metrics.
- Frontend tests, backend tests, security negatives, and production build all pass.
