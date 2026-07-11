# RadioTEDU Release, Operations, and Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce signed, deterministic, role-separated RadioTEDU release artifacts that install on a clean Windows broadcasting computer and a clean Linux webserver, preserve and diagnose station state safely, and earn release approval through independent security, isolation, voice, audio, soak, and canary evidence.

**Architecture:** The build computer creates two unsigned payloads from one pinned source revision: a Windows broadcast bundle and a Linux webserver bundle. Each bundle is assembled from an explicit allowlist, contains a machine-readable release manifest and SPDX JSON SBOM, is independently qualified, and is signed only after every immutable-payload gate passes. Runtime operations are role-specific: WinSW supervises the broadcast stack with DPAPI-protected secrets, systemd supervises the public server with a root-owned mode-`0600` environment file, and shared backup/restore/diagnostic CLIs operate on explicit station roots without crossing station boundaries.

**Tech Stack:** Python 3.12.10, Node.js 22.14.0, npm lockfile v3, pytest, React/Vite, PowerShell 7, WinSW, systemd, SQLite online backup API, SPDX 2.3 JSON, SHA-256, OpenSSL Ed25519 signatures, GitHub Actions, ffmpeg/ffprobe, Liquidsoap, Icecast.

## Global Constraints

The following lines are copied verbatim from the approved design contract and govern every task:

- The build computer develops, tests, and packages the application. It is not an on-air dependency.
- The webserver never reaches into the broadcasting computer, music library, database, logs, or admin API.
- The broadcasting computer pushes sanitized state outward. A webserver outage cannot stop audio.
- Qwen is the sole speech engine.
- SAPI, Piper, cloud TTS, dummy speech, and silent substitute clips are prohibited in production and qualification tests.
- The Qwen service is persistent, localhost-only, model-pinned, and warmed with a real synthesis at startup.
- Health means successful valid audio generation, not merely a process, port, command, or loaded model.
- Each station maintains at least five prepared Qwen announcements.
- The two stations share code and may share read-only model services.
- They do not share mutable station state.
- The webserver verifies path identity, station identity, timestamp skew, body hash, constant-time HMAC, nonce uniqueness, sequence monotonicity, schema, expiry, and payload limits before storing anything.
- Nonces are retained through the replay window.
- Migrations are restartable and backed up before mutation.
- The existing `/ai` route remains an English compatibility alias.
- At most three implementation agents work simultaneously.
- Independent read-only reviewers do not approve their own implementation.
- Each wave begins only when its dependencies are green.
- Failed gates produce a bounded remediation card, not an informal cross-cutting edit.

---

## Repository Evidence and Plan Boundary

The current repository has `requirements.txt` with six broad `>=` ranges and no Python lock, hash lock, Python version file, or build metadata. Root `package-lock.json` is lockfile v3, while `package.json` drives Vite, Vitest, Electron, and an NSIS build whose `files` list currently contains only `dist/**`, `desktop/**`, and `package.json`. `desktop/main.cjs` starts the backend with the system Python and repository root, so the Electron output is not a self-contained broadcast release.

Existing operational entry points are `scripts/run_station_forever.py` (`ProcessSpec`, `build_process_specs()`, `backend_is_healthy()`, `supervise()`), `scripts/run_broadcast_computer.py` (`broadcast_readiness()` and restart backoff), `scripts/smoke_broadcast.py`, `scripts/smoke_public_server.py`, and `scripts/install_windows_task.ps1`. Existing handoff scripts clone the source repository and runbooks require manual `.env` editing; this plan replaces those release-time assumptions without modifying the source-only development workflow.

`release/` is an untracked local Electron output and is forbidden to every task. All generated evidence and artifacts go beneath ignored `artifacts/`. This plan owns release engineering and operational qualification only; station profiles, Qwen runtime, Snapshot v2, web routes, and dual-station orchestration are consumed as frozen upstream interfaces.

## Frozen Release Interfaces

`scripts/build_release.py` exposes:

```python
def build_release(
    role: Literal["broadcast", "webserver"],
    version: str,
    revision: str,
    source_date_epoch: int,
    output_dir: Path,
) -> ReleaseBuild:
    """Build one deterministic unsigned role payload and its detached metadata."""

def verify_release(artifact: Path, manifest_path: Path) -> None:
    """Fail unless artifact bytes, allowlist, checksums, SBOM, and role policy agree."""
```

`backend.operations.cli:main` exposes these stable commands:

```text
python -m backend.operations.cli backup --station-id STATION --station-root PATH --output PATH
python -m backend.operations.cli restore --archive PATH --station-root PATH --verify-only
python -m backend.operations.cli restore --archive PATH --station-root PATH --replace
python -m backend.operations.cli diagnostics --role ROLE --root PATH --output PATH
```

The Windows broadcast service invokes `python -m scripts.run_broadcast_computer --profiles-dir config/stations --station radiotedu-en --station radiotedu-fr` from its bundled virtual environment. The Linux web service invokes the public-only ASGI entry point owned by Plan 4; the packaging manifest names it as `backend.public_app:app` and the release build must fail if that symbol is absent.

## Execution Ownership Matrix

| Task | Depends on | Preferred worker | Review requirement |
|---|---|---|---|
| 1. Toolchain and locks | None | Mini-class | Strong dependency/reproducibility review |
| 2. Deterministic role builder | 1 and upstream role entry points | Strong reasoning | OpenCode reproducibility cross-check |
| 3. Manifest, SBOM, checksums, signing | 2 | Strong reasoning | Independent security review |
| 4. Windows broadcast installer | 1–3 and broadcast runtime | Mini-class | Windows operations reviewer |
| 5. Linux webserver installer | 1–3 and public runtime | Mini-class | Linux/security reviewer |
| 6. Backup and restore | station profile/storage contract | Strong migration reviewer | Destructive-path independent review |
| 7. Diagnostics | 6 | Mini-class | Privacy/security reviewer |
| 8. Clean-machine qualification | 4–7 | Mini-class | Independent installer reviewer |
| 9. Security and isolation audits | 2, 4, 5, 7 | Strong security reviewer | OpenCode read-only cross-check |
| 10. Voice and audio audits | Qwen/voice/audio waves | Mini harness worker | Human English and native-French review |
| 11. Soak and canary | 8–10 | Mini harness worker | Strong resilience review |
| 12. Release workflow and governance | 1–11 | Orchestrator-owned integration | Independent final audit |

### Task 1: Pin Python and Node Toolchains

**Dependencies:** None.

**Owned files:** `pyproject.toml`, `requirements.txt`, `requirements.lock`, `.python-version`, `.nvmrc`, `package.json`, `package-lock.json`, `tests/release/test_dependency_locks.py`.

**Forbidden files:** `release/**`, runtime source under `backend/**`, installer files under `packaging/**`, and all station data.

**Interfaces:**
- Consumes: current six Python runtime dependencies and npm lockfile v3.
- Produces: Python `3.12.10`, Node `22.14.0`, npm `10.9.2`, PEP 621 metadata, and a hash-complete `requirements.lock` accepted by `pip install --require-hashes`.

- [ ] **Step 1: Write the failing dependency-lock tests**

Create `tests/release/test_dependency_locks.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_toolchain_versions_are_exact() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12.10"
    assert (ROOT / ".nvmrc").read_text(encoding="utf-8").strip() == "22.14.0"
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["packageManager"] == "npm@10.9.2"
    assert package["engines"] == {"node": "22.14.0", "npm": "10.9.2"}


def test_python_lock_is_exact_and_hash_complete() -> None:
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    requirement_lines = [
        line for line in lock.splitlines()
        if line and not line.startswith(("#", " ", "\\"))
    ]
    assert requirement_lines
    assert all("==" in line for line in requirement_lines)
    assert "--hash=sha256:" in lock
    assert not re.search(r"(?m)^[a-zA-Z0-9_.-]+\\s*(>=|~=|\\^)", lock)


def test_node_lock_matches_root_manifest() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["lockfileVersion"] == 3
    assert lock["packages"][""]["version"] == package["version"]
    assert lock["packages"][""]["engines"] == package["engines"]
```

- [ ] **Step 2: Run the tests and observe the missing lock/version failure**

Run: `python -m pytest tests/release/test_dependency_locks.py -v`

Expected: FAIL because `.python-version`, `.nvmrc`, `pyproject.toml`, and `requirements.lock` do not exist and `package.json` has no exact engines.

- [ ] **Step 3: Add build metadata and exact toolchain declarations**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools==80.9.0", "wheel==0.45.1"]
build-backend = "setuptools.build_meta"

[project]
name = "radiotedu"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.32.0",
  "pydantic>=2.9.0",
  "mutagen>=1.47.0",
  "pillow>=10.4.0",
  "httpx>=0.27.0",
]

[project.optional-dependencies]
release = [
  "pip-tools==7.5.0",
  "pytest==8.4.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `.python-version` containing `3.12.10` and `.nvmrc` containing `22.14.0`. Add the following exact keys to `package.json` without changing existing dependency ranges:

```json
{
  "packageManager": "npm@10.9.2",
  "engines": {
    "node": "22.14.0",
    "npm": "10.9.2"
  }
}
```

Generate and verify the complete Python lock:

```powershell
py -3.12 -m pip install "pip-tools==7.5.0"
py -3.12 -m piptools compile --extra release --generate-hashes --resolver=backtracking --strip-extras --output-file=requirements.lock pyproject.toml
py -3.12 -m pip install --dry-run --require-hashes --only-binary=:all: -r requirements.lock
npm install --package-lock-only --ignore-scripts
```

The generated `requirements.lock` is committed in full. Do not hand-edit resolver output.

- [ ] **Step 4: Run lock and baseline tests**

Run:

```powershell
py -3.12 -m pytest tests/release/test_dependency_locks.py -v
npm ci --ignore-scripts
npm test
py -3.12 -m pytest tests/backend -q
```

Expected: three lock tests PASS, frontend tests PASS, and the existing backend suite PASS.

- [ ] **Step 5: Commit the lock boundary**

```bash
git add pyproject.toml requirements.txt requirements.lock .python-version .nvmrc package.json package-lock.json tests/release/test_dependency_locks.py
git commit -m "build: pin release toolchains and dependencies"
```

### Task 2: Build Deterministic Role-Separated Payloads

**Dependencies:** Task 1; frozen `backend.public_app:app` and dual-station broadcast runtime must exist.

**Owned files:** `packaging/release-layout.json`, `packaging/broadcast/manifest.json`, `packaging/webserver/manifest.json`, `scripts/build_release.py`, `tests/release/test_release_builder.py`, `.gitignore`.

**Forbidden files:** `release/**`, `desktop/**`, generated station data, secrets, voice reference audio, and files owned by Tasks 3–12.

**Interfaces:**
- Consumes: `requirements.lock`, `package-lock.json`, built `dist/**`, revision, version, and `SOURCE_DATE_EPOCH`.
- Produces: `ReleaseBuild(role, artifact, manifest, sbom, sha256)` and unsigned `radiotedu-broadcast-VERSION-windows-x64.zip` / `radiotedu-webserver-VERSION-linux-x64.tar.gz`.

- [ ] **Step 1: Write failing allowlist and reproducibility tests**

Create `tests/release/test_release_builder.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_release import build_release, list_archive_paths

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("role", ["broadcast", "webserver"])
def test_same_inputs_produce_identical_unsigned_payload(role: str, tmp_path: Path) -> None:
    first = build_release(role, "1.0.0", "a" * 40, 1_750_000_000, tmp_path / "one")
    second = build_release(role, "1.0.0", "a" * 40, 1_750_000_000, tmp_path / "two")
    assert hashlib.sha256(first.artifact.read_bytes()).digest() == hashlib.sha256(
        second.artifact.read_bytes()
    ).digest()


def test_webserver_payload_excludes_private_broadcast_state(tmp_path: Path) -> None:
    build = build_release("webserver", "1.0.0", "b" * 40, 1_750_000_000, tmp_path)
    paths = set(list_archive_paths(build.artifact))
    forbidden = {
        ".env",
        "data/radiotedu.db",
        "scripts/run_broadcast_computer.py",
        "scripts/qwen_tts_command.py",
        "scripts/run_liquidsoap.ps1",
        "backend/static/generated/tts",
        "backend/app.py",
        "backend/liquidsoap.py",
        "backend/music_library.py",
        "backend/ollama_setup.py",
        "backend/orchestrator.py",
        "backend/playback.py",
        "backend/radio_agent.py",
        "backend/tts",
    }
    assert not any(path == item or path.startswith(item + "/") for path in paths for item in forbidden)
    assert "backend/public_app.py" in paths
    assert "dist/index.html" in paths


def test_broadcast_payload_has_no_build_or_local_output(tmp_path: Path) -> None:
    build = build_release("broadcast", "1.0.0", "c" * 40, 1_750_000_000, tmp_path)
    paths = set(list_archive_paths(build.artifact))
    assert not any(path.startswith(("release/", "artifacts/", ".git/", "node_modules/")) for path in paths)
    assert "scripts/run_broadcast_computer.py" in paths
    assert any(path.startswith("config/stations/") for path in paths)
    assert "backend/radio_agent.py" in paths
    assert "backend/orchestrator.py" in paths
    assert "backend/music_library.py" in paths
    assert "backend/tts/qwen_tts.py" in paths
    manifest = json.loads(build.manifest.read_text(encoding="utf-8"))
    assert manifest["role"] == "broadcast"
```

- [ ] **Step 2: Run the release-builder tests and verify RED**

Run: `python -m pytest tests/release/test_release_builder.py -v`

Expected: collection ERROR with `ModuleNotFoundError: No module named 'scripts.build_release'`.

- [ ] **Step 3: Define exact role manifests**

Create `packaging/release-layout.json`:

```json
{
  "schema_version": 1,
  "timestamp_epoch_env": "SOURCE_DATE_EPOCH",
  "roles": {
    "broadcast": "packaging/broadcast/manifest.json",
    "webserver": "packaging/webserver/manifest.json"
  },
  "always_exclude": [
    ".env",
    ".git",
    ".github",
    ".pytest_cache",
    ".superpowers",
    ".venv",
    ".worktrees",
    "artifacts",
    "data",
    "logs",
    "node_modules",
    "release",
    "__pycache__"
  ]
}
```

Create `packaging/broadcast/manifest.json`:

```json
{
  "schema_version": 1,
  "role": "broadcast",
  "platform": "windows-x64",
  "entrypoint": "python -m scripts.run_broadcast_computer --profiles-dir config/stations --station radiotedu-en --station radiotedu-fr",
  "include": [
    "backend/**/*.py",
    "backend/static/**/*",
    "config/stations/**/*",
    "scripts/*.py",
    "packaging/broadcast/**/*",
    "requirements.lock",
    "pyproject.toml"
  ],
  "exclude": [
    "backend/static/generated/tts/**/*",
    "backend/static/generated/clips/**/*",
    "scripts/smoke_public_server.py"
  ]
}
```

Create `packaging/webserver/manifest.json`:

```json
{
  "schema_version": 1,
  "role": "webserver",
  "platform": "linux-x64",
  "entrypoint": "uvicorn backend.public_app:app --host 127.0.0.1 --port 8000",
  "include": [
    "backend/__init__.py",
    "backend/config.py",
    "backend/database.py",
    "backend/public_app.py",
    "backend/public_dashboard.py",
    "backend/static/**/*",
    "dist/**/*",
    "packaging/webserver/**/*",
    "requirements.lock",
    "pyproject.toml"
  ],
  "exclude": [
    "backend/app.py",
    "backend/liquidsoap.py",
    "backend/music_library.py",
    "backend/ollama_setup.py",
    "backend/orchestrator.py",
    "backend/playback.py",
    "backend/radio_agent.py",
    "backend/tts/**/*",
    "backend/static/generated/tts/**/*",
    "backend/static/generated/clips/**/*",
    "backend/static/generated/voice-packs/**/*"
  ]
}
```

Add `artifacts/` to `.gitignore`. Do not add or clean `release/`.

- [ ] **Step 4: Implement the deterministic builder**

Create `scripts/build_release.py` with these complete public structures and deterministic archive rules:

```python
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "packaging" / "release-layout.json"


@dataclass(frozen=True)
class ReleaseBuild:
    role: str
    artifact: Path
    manifest: Path
    sbom: Path
    sha256: str


def _load_role(role: str) -> dict:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    if role not in layout["roles"]:
        raise ValueError(f"unsupported release role: {role}")
    return json.loads((ROOT / layout["roles"][role]).read_text(encoding="utf-8"))


def _matches(path: Path, patterns: list[str]) -> bool:
    relative = PurePosixPath(path.relative_to(ROOT).as_posix())
    return any(relative.match(pattern) for pattern in patterns)


def collect_files(role: str) -> list[Path]:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    spec = _load_role(role)
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in layout["always_exclude"] for part in relative.parts):
            continue
        if _matches(path, spec["include"]) and not _matches(path, spec["exclude"]):
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def _zip(files: list[Path], destination: Path, epoch: int) -> None:
    timestamp = __import__("datetime").datetime.fromtimestamp(
        max(epoch, 315532800), tz=__import__("datetime").timezone.utc
    ).timetuple()[:6]
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            info = zipfile.ZipInfo(source.relative_to(ROOT).as_posix(), timestamp)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _tar_gz(files: list[Path], destination: Path, epoch: int) -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for source in files:
            info = archive.gettarinfo(str(source), source.relative_to(ROOT).as_posix())
            info.mtime = epoch
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mode = 0o644
            with source.open("rb") as handle:
                archive.addfile(info, handle)
    with destination.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=epoch, compresslevel=9) as zipped:
            zipped.write(raw.getvalue())


def list_archive_paths(artifact: Path) -> list[str]:
    if artifact.suffix == ".zip":
        with zipfile.ZipFile(artifact) as archive:
            return archive.namelist()
    with tarfile.open(artifact, "r:gz") as archive:
        return archive.getnames()


def build_release(
    role: Literal["broadcast", "webserver"],
    version: str,
    revision: str,
    source_date_epoch: int,
    output_dir: Path,
) -> ReleaseBuild:
    spec = _load_role(role)
    files = collect_files(role)
    if not files:
        raise RuntimeError(f"release role {role} selected no files")
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"radiotedu-{role}-{version}-{spec['platform']}"
    artifact = output_dir / (stem + (".zip" if role == "broadcast" else ".tar.gz"))
    (_zip if role == "broadcast" else _tar_gz)(files, artifact, source_date_epoch)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = output_dir / f"{stem}.manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "role": role,
        "version": version,
        "revision": revision,
        "source_date_epoch": source_date_epoch,
        "platform": spec["platform"],
        "entrypoint": spec["entrypoint"],
        "artifact": artifact.name,
        "sha256": digest,
        "files": [path.relative_to(ROOT).as_posix() for path in files],
    }, sort_keys=True, indent=2) + "\\n", encoding="utf-8")
    sbom = output_dir / f"{stem}.spdx.json"
    return ReleaseBuild(role, artifact, manifest, sbom, digest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("broadcast", "webserver"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_release(args.role, args.version, args.revision, args.source_date_epoch, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run deterministic-builder tests**

Run: `python -m pytest tests/release/test_release_builder.py -v`

Expected: four parametrized/role-policy cases PASS and repeated builds have byte-identical SHA-256 values.

- [ ] **Step 6: Commit role separation**

```bash
git add .gitignore packaging/release-layout.json packaging/broadcast/manifest.json packaging/webserver/manifest.json scripts/build_release.py tests/release/test_release_builder.py
git commit -m "build: add deterministic role-separated release payloads"
```

### Task 3: Generate Release Manifest, SPDX SBOM, Checksums, and Signatures

**Dependencies:** Tasks 1–2.

**Owned files:** `scripts/release_metadata.py`, `tests/release/test_release_metadata.py`, and the metadata calls inside `scripts/build_release.py`.

**Forbidden files:** `release/**`, private keys, installer/service files, GitHub workflow, runtime code, and human qualification evidence.

**Interfaces:**
- Consumes: role payload, `requirements.lock`, `package-lock.json`, model checksums, voice-pack versions, schema versions, and OpenSSL Ed25519 key path.
- Produces: canonical `*.manifest.json`, `*.spdx.json`, `*.sha256`, `*.sig`, `verify_signature()`, and CLI `sign-directory --input PATH --output PATH --private-key-env NAME`; unsigned payload bytes never change during signing.

- [ ] **Step 1: Write failing metadata and tamper tests**

Create `tests/release/test_release_metadata.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.release_metadata import build_spdx, canonical_json, verify_bundle


def test_canonical_json_is_stable() -> None:
    assert canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}\\n'


def test_spdx_records_python_node_models_voices_and_schema(tmp_path: Path) -> None:
    document = build_spdx(
        name="radiotedu-broadcast-1.0.0",
        namespace="https://radiotedu.com/spdx/1.0.0/broadcast",
        requirements="fastapi==0.116.1 --hash=sha256:" + "a" * 64,
        package_lock={"packages": {"": {"version": "1.0.0"}}},
        models={"qwen3-tts": "b" * 64},
        voices={"radiotedu-en-voices-v1": "c" * 64},
        schemas={"station_profile": 1, "public_snapshot": 2},
    )
    assert document["spdxVersion"] == "SPDX-2.3"
    assert document["documentNamespace"].endswith("/broadcast")
    assert {item["name"] for item in document["packages"]} >= {
        "fastapi", "qwen3-tts", "radiotedu-en-voices-v1"
    }


def test_verifier_rejects_changed_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "payload.zip"
    artifact.write_bytes(b"approved")
    manifest = tmp_path / "payload.manifest.json"
    manifest.write_text(json.dumps({"artifact": artifact.name, "sha256": hashlib.sha256(b"approved").hexdigest()}))
    artifact.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact sha256 mismatch"):
        verify_bundle(artifact, manifest)
```

- [ ] **Step 2: Run metadata tests and verify RED**

Run: `python -m pytest tests/release/test_release_metadata.py -v`

Expected: collection ERROR because `scripts.release_metadata` does not exist.

- [ ] **Step 3: Implement canonical metadata**

Create `scripts/release_metadata.py`:

```python
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\\n").encode()


def _python_packages(requirements: str) -> list[dict]:
    packages = []
    for line in requirements.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\\s\\\\]+)", line)
        if match:
            packages.append({
                "SPDXID": "SPDXRef-Python-" + re.sub(r"[^A-Za-z0-9.-]", "-", match.group(1)),
                "name": match.group(1),
                "versionInfo": match.group(2),
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
            })
    return packages


def build_spdx(
    name: str,
    namespace: str,
    requirements: str,
    package_lock: dict,
    models: dict[str, str],
    voices: dict[str, str],
    schemas: dict[str, int],
) -> dict:
    packages = _python_packages(requirements)
    for package_name, checksum in sorted({**models, **voices}.items()):
        packages.append({
            "SPDXID": "SPDXRef-Asset-" + re.sub(r"[^A-Za-z0-9.-]", "-", package_name),
            "name": package_name,
            "versionInfo": checksum,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "checksums": [{"algorithm": "SHA256", "checksumValue": checksum}],
        })
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": name,
        "documentNamespace": namespace,
        "creationInfo": {"creators": ["Tool: RadioTEDU-release_metadata"], "created": "1970-01-01T00:00:00Z"},
        "packages": packages,
        "annotations": [{
            "annotationType": "OTHER",
            "annotator": "Tool: RadioTEDU-release_metadata",
            "annotationDate": "1970-01-01T00:00:00Z",
            "comment": json.dumps({"schemas": schemas, "node_root": package_lock["packages"][""]}, sort_keys=True),
        }],
    }


def write_checksum(artifact: Path) -> Path:
    output = artifact.with_name(artifact.name + ".sha256")
    output.write_text(f"{hashlib.sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}\\n", encoding="ascii")
    return output


def sign_file(path: Path, private_key: Path) -> Path:
    signature = path.with_name(path.name + ".sig")
    subprocess.run(
        ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(private_key), "-in", str(path), "-out", str(signature)],
        check=True,
    )
    return signature


def verify_signature(path: Path, signature: Path, public_key: Path) -> None:
    subprocess.run(
        ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(public_key), "-in", str(path), "-sigfile", str(signature)],
        check=True,
    )


def verify_bundle(artifact: Path, manifest: Path) -> None:
    value = json.loads(manifest.read_text(encoding="utf-8"))
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if value["artifact"] != artifact.name or value["sha256"] != actual:
        raise ValueError("artifact sha256 mismatch")
```

Add `sign_directory(input_dir: Path, output_dir: Path, private_key: Path) -> list[Path]`. It copies only manifests, SBOMs, checksums, and payloads to a new output directory; verifies every manifest/payload pair; writes one SHA-256 file per copied file; signs each manifest, SBOM, checksum, and qualification index; and returns the sorted output paths. Its argparse `sign-directory` command reads a base64-encoded PKCS#8 Ed25519 key from the named environment variable, writes it to a mode-`0600` temporary file, invokes `sign_directory()`, clears the environment variable, and deletes the temporary key in `finally`.

Update `build_release()` to call `build_spdx()`, write the canonical manifest, create `*.sha256`, and call `verify_bundle()` before returning. Add CLI options `--models-lock`, `--voices-lock`, and `--schemas-lock`; each must be a committed JSON mapping and missing metadata must fail the build.

- [ ] **Step 4: Run metadata, builder, and tamper tests**

Run: `python -m pytest tests/release/test_release_metadata.py tests/release/test_release_builder.py -v`

Expected: all tests PASS; changing one payload byte yields `artifact sha256 mismatch`.

- [ ] **Step 5: Commit immutable release metadata**

```bash
git add scripts/build_release.py scripts/release_metadata.py tests/release/test_release_metadata.py
git commit -m "build: add signed release metadata and SPDX SBOM"
```

### Task 4: Install and Supervise the Windows Broadcast Bundle

**Dependencies:** Tasks 1–3 and the completed dual-station broadcast runtime.

**Owned files:** `packaging/broadcast/RadioTEDU.BroadcastService.xml`, `packaging/broadcast/service.ps1`, `packaging/broadcast/first_run.ps1`, `packaging/broadcast/install.ps1`, `packaging/broadcast/uninstall.ps1`, `tests/release/test_broadcast_installer.py`.

**Forbidden files:** `release/**`, webserver packaging, registry-wide policy, source `.env`, actual secrets, music, station databases, and Task 1–3 metadata interfaces.

**Interfaces:**
- Consumes: extracted bundle root, bundled Python 3.12 virtual environment, injected verified `RadioTEDU.BroadcastService.exe` WinSW binary, `requirements.lock`, and `scripts.run_broadcast_computer`.
- Produces: service `RadioTEDU.Broadcast`, DPAPI LocalMachine secret blob `C:\ProgramData\RadioTEDU\secrets\broadcast.json.dpapi`, protected ACLs, logs, and reboot persistence.

- [ ] **Step 1: Write failing installer contract tests**

Create `tests/release/test_broadcast_installer.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "packaging" / "broadcast"


def test_winsw_service_runs_qwen_only_broadcast_wrapper() -> None:
    xml = (PKG / "RadioTEDU.BroadcastService.xml").read_text(encoding="utf-8")
    assert "<id>RadioTEDU.Broadcast</id>" in xml
    assert "service.ps1" in xml
    assert "<onfailure action=\"restart\" delay=\"10 sec\"/>" in xml
    assert "stoptimeout>60 sec</stoptimeout" in xml


def test_first_run_uses_machine_dpapi_and_restrictive_acl() -> None:
    script = (PKG / "first_run.ps1").read_text(encoding="utf-8")
    assert "DataProtectionScope]::LocalMachine" in script
    assert "SetAccessRuleProtection($true, $false)" in script
    assert "PUBLIC_SYNC_TOKEN" in script
    assert "QWEN_TTS" not in script


def test_installer_never_clones_or_reads_repo_env() -> None:
    combined = "\\n".join(path.read_text(encoding="utf-8") for path in PKG.glob("*.ps1"))
    assert "git clone" not in combined.lower()
    assert ".env" not in combined
    assert "--require-hashes" in combined
```

- [ ] **Step 2: Run installer tests and verify RED**

Run: `python -m pytest tests/release/test_broadcast_installer.py -v`

Expected: FAIL because the WinSW XML and installer scripts do not exist.

- [ ] **Step 3: Add the WinSW service definition**

Create `packaging/broadcast/RadioTEDU.BroadcastService.xml`:

```xml
<service>
  <id>RadioTEDU.Broadcast</id>
  <name>RadioTEDU Broadcast</name>
  <description>Dual-station RadioTEDU broadcast supervisor</description>
  <executable>powershell.exe</executable>
  <arguments>-NoLogo -NoProfile -NonInteractive -ExecutionPolicy AllSigned -File "%BASE%\service.ps1"</arguments>
  <workingdirectory>%BASE%</workingdirectory>
  <logpath>C:\ProgramData\RadioTEDU\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10485760</sizeThreshold>
    <keepFiles>10</keepFiles>
  </log>
  <onfailure action="restart" delay="10 sec"/>
  <onfailure action="restart" delay="30 sec"/>
  <resetfailure>1 hour</resetfailure>
  <stoptimeout>60 sec</stoptimeout>
  <startmode>Automatic</startmode>
</service>
```

- [ ] **Step 4: Add exact secret bootstrap and service wrapper**

`first_run.ps1` accepts mandatory `-PublicSyncToken`, `-EnglishIcecastPassword`, and `-FrenchIcecastPassword` secure strings, serializes only those values, protects `$PlainBytes` with `[System.Security.Cryptography.ProtectedData]::Protect($PlainBytes, $null, [System.Security.Cryptography.DataProtectionScope]::LocalMachine)`, writes the DPAPI blob beneath `C:\ProgramData\RadioTEDU\secrets`, disables inherited ACLs, and grants FullControl only to `SYSTEM` and `BUILTIN\Administrators`. It never accepts a non-Qwen TTS setting.

Create `packaging/broadcast/service.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$SecretPath = "C:\ProgramData\RadioTEDU\secrets\broadcast.json.dpapi"
$Protected = [IO.File]::ReadAllBytes($SecretPath)
$Plain = [Security.Cryptography.ProtectedData]::Unprotect(
    $Protected,
    $null,
    [Security.Cryptography.DataProtectionScope]::LocalMachine
)
$Secrets = [Text.Encoding]::UTF8.GetString($Plain) | ConvertFrom-Json -AsHashtable
try {
    foreach ($Key in $Secrets.Keys) {
        [Environment]::SetEnvironmentVariable($Key, [string]$Secrets[$Key], "Process")
    }
    $env:RADIOTEDU_ROLE = "broadcast"
    $env:RADIOTEDU_TTS_PROVIDER = "qwen"
    & "$Root\venv\Scripts\python.exe" -m scripts.run_broadcast_computer --profiles-dir config/stations --station radiotedu-en --station radiotedu-fr
    exit $LASTEXITCODE
}
finally {
    [Array]::Clear($Plain, 0, $Plain.Length)
    foreach ($Key in $Secrets.Keys) {
        [Environment]::SetEnvironmentVariable($Key, $null, "Process")
    }
}
```

- [ ] **Step 5: Add install and uninstall scripts**

`install.ps1` must require an elevated PowerShell session, verify the artifact signature and manifest before copying, create `C:\Program Files\RadioTEDU\Broadcast` and `C:\ProgramData\RadioTEDU`, create `venv` with Python 3.12.10, run `pip install --require-hashes -r requirements.lock`, call `first_run.ps1`, install/start WinSW, and fail if `python -m scripts.run_broadcast_computer --profiles-dir config/stations --station radiotedu-en --station radiotedu-fr --check-only --json` is not ready.

`uninstall.ps1` stops and uninstalls WinSW, removes only `C:\Program Files\RadioTEDU\Broadcast`, and preserves `C:\ProgramData\RadioTEDU` unless called with `-PurgeData`. With `-PurgeData` it requires the exact confirmation string `PURGE-RADIOTEDU-BROADCAST-DATA`.

The installer control flow is:

```powershell
param(
    [Parameter(Mandatory)][string]$BundleRoot,
    [Parameter(Mandatory)][string]$Manifest,
    [Parameter(Mandatory)][string]$Signature,
    [Parameter(Mandatory)][string]$PublicKey
)
$ErrorActionPreference = "Stop"
$Principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator privileges are required"
}
& openssl pkeyutl -verify -rawin -pubin -inkey $PublicKey -in $Manifest -sigfile $Signature
if ($LASTEXITCODE -ne 0) { throw "Release signature verification failed" }
$InstallRoot = "C:\Program Files\RadioTEDU\Broadcast"
New-Item -ItemType Directory -Force $InstallRoot, "C:\ProgramData\RadioTEDU\logs" | Out-Null
Copy-Item -Recurse -Force "$BundleRoot\*" $InstallRoot
& py -3.12 -m venv "$InstallRoot\venv"
& "$InstallRoot\venv\Scripts\python.exe" -m pip install --require-hashes -r "$InstallRoot\requirements.lock"
& "$InstallRoot\first_run.ps1"
& "$InstallRoot\RadioTEDU.BroadcastService.exe" install
& "$InstallRoot\RadioTEDU.BroadcastService.exe" start
& "$InstallRoot\venv\Scripts\python.exe" -m scripts.run_broadcast_computer --profiles-dir config/stations --station radiotedu-en --station radiotedu-fr --check-only --json
if ($LASTEXITCODE -ne 0) { throw "Broadcast readiness failed after service install" }
```

- [ ] **Step 6: Run PowerShell static parsing and installer tests**

Run:

```powershell
Get-ChildItem packaging\broadcast\*.ps1 | ForEach-Object {
    $null = [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$null, [ref]$null)
}
py -3.12 -m pytest tests/release/test_broadcast_installer.py -v
```

Expected: PowerShell parsing exits zero and all installer contract tests PASS.

- [ ] **Step 7: Commit Windows operations**

```bash
git add packaging/broadcast tests/release/test_broadcast_installer.py
git commit -m "ops: add Windows broadcast service installer"
```

### Task 5: Install and Supervise the Linux Webserver Bundle

**Dependencies:** Tasks 1–3 and the completed `backend.public_app:app`.

**Owned files:** `packaging/webserver/radiotedu-web.service`, `packaging/webserver/first_run.sh`, `packaging/webserver/install.sh`, `packaging/webserver/uninstall.sh`, `tests/release/test_webserver_installer.py`.

**Forbidden files:** `release/**`, broadcast packaging, source `.env`, private operator endpoints, music/Qwen/Liquidsoap code, actual secrets, and root SSH configuration.

**Interfaces:**
- Consumes: verified webserver tarball, Python 3.12, `requirements.lock`, `backend.public_app:app`.
- Produces: user `radiotedu-web`, root-owned `/etc/radiotedu/webserver.env` mode `0600`, `radiotedu-web.service`, and localhost HTTP on `127.0.0.1:8000` behind the existing HTTPS proxy.

- [ ] **Step 1: Write failing systemd hardening tests**

Create `tests/release/test_webserver_installer.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "packaging" / "webserver"


def test_systemd_unit_is_role_specific_and_hardened() -> None:
    unit = (PKG / "radiotedu-web.service").read_text(encoding="utf-8")
    required = [
        "User=radiotedu-web",
        "EnvironmentFile=/etc/radiotedu/webserver.env",
        "backend.public_app:app",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=strict",
        "ProtectHome=true",
        "ReadWritePaths=/var/lib/radiotedu-web /var/log/radiotedu-web",
    ]
    assert all(value in unit for value in required)


def test_installer_protects_secret_file_and_uses_hash_lock() -> None:
    install = (PKG / "install.sh").read_text(encoding="utf-8")
    first_run = (PKG / "first_run.sh").read_text(encoding="utf-8")
    assert "install -m 0600 -o root -g root" in first_run
    assert "--require-hashes" in install
    assert "git clone" not in install
    assert ".env" not in install
```

- [ ] **Step 2: Run webserver installer tests and verify RED**

Run: `python -m pytest tests/release/test_webserver_installer.py -v`

Expected: FAIL because the systemd unit and scripts are absent.

- [ ] **Step 3: Add the hardened systemd unit**

Create `packaging/webserver/radiotedu-web.service`:

```ini
[Unit]
Description=RadioTEDU public webserver
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=radiotedu-web
Group=radiotedu-web
WorkingDirectory=/opt/radiotedu-webserver
Environment=RADIOTEDU_ROLE=webserver
EnvironmentFile=/etc/radiotedu/webserver.env
ExecStart=/opt/radiotedu-webserver/venv/bin/uvicorn backend.public_app:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=10
TimeoutStopSec=60
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
ReadWritePaths=/var/lib/radiotedu-web /var/log/radiotedu-web
UMask=0077

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Add secret bootstrap and installer scripts**

`first_run.sh` accepts the English and French snapshot HMAC keys on standard input without echo, validates each is at least 32 random bytes encoded as 64 lowercase hexadecimal characters, writes only `RADIOTEDU_SNAPSHOT_KEY_RADIOTEDU_EN` and `RADIOTEDU_SNAPSHOT_KEY_RADIOTEDU_FR` to a temporary file under root umask `0077`, then installs it with:

```bash
install -d -m 0750 -o root -g radiotedu-web /etc/radiotedu
install -m 0600 -o root -g root "$SECRET_TMP" /etc/radiotedu/webserver.env
rm -f "$SECRET_TMP"
```

`install.sh` verifies signature and SHA-256 before extraction, creates the system user with no shell/home login, copies the already-extracted payload to `/opt/radiotedu-webserver`, installs the exact Python lock into `venv`, installs the unit, runs `systemd-analyze verify`, enables the service, and validates `/api/health` plus `/api/public/stations/radiotedu-en/status` and `/api/public/stations/radiotedu-fr/status` locally.

`uninstall.sh` disables/removes only the service and `/opt/radiotedu-webserver`. Data under `/var/lib/radiotedu-web` and secrets under `/etc/radiotedu` survive unless `--purge-data PURGE-RADIOTEDU-WEBSERVER-DATA` is supplied.

The installer control flow is:

```bash
set -euo pipefail
test "$(id -u)" -eq 0 || { echo "root is required" >&2; exit 1; }
openssl pkeyutl -verify -rawin -pubin -inkey "$PUBLIC_KEY" -in "$MANIFEST" -sigfile "$SIGNATURE"
sha256sum --check "$CHECKSUM"
id radiotedu-web >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin radiotedu-web
install -d -m 0755 /opt/radiotedu-webserver
cp -a "$BUNDLE_ROOT"/. /opt/radiotedu-webserver/
python3.12 -m venv /opt/radiotedu-webserver/venv
/opt/radiotedu-webserver/venv/bin/pip install --require-hashes -r /opt/radiotedu-webserver/requirements.lock
/opt/radiotedu-webserver/first_run.sh
install -m 0644 /opt/radiotedu-webserver/radiotedu-web.service /etc/systemd/system/radiotedu-web.service
systemd-analyze verify /etc/systemd/system/radiotedu-web.service
systemctl daemon-reload
systemctl enable --now radiotedu-web.service
python3.12 /opt/radiotedu-webserver/scripts/smoke_public_server.py --base-url http://127.0.0.1:8000
```

- [ ] **Step 5: Run shell and unit validation**

Run:

```bash
bash -n packaging/webserver/first_run.sh
bash -n packaging/webserver/install.sh
bash -n packaging/webserver/uninstall.sh
systemd-analyze verify packaging/webserver/radiotedu-web.service
python -m pytest tests/release/test_webserver_installer.py -v
```

Expected: shell parsing, unit validation, and all webserver installer tests PASS.

- [ ] **Step 6: Commit Linux operations**

```bash
git add packaging/webserver tests/release/test_webserver_installer.py
git commit -m "ops: add hardened Linux webserver installer"
```

### Task 6: Add Verified Online Backup and Atomic Restore

**Dependencies:** Station Profile v1 and station-root/storage interfaces from the dual-station implementation.

**Owned files:** `backend/operations/__init__.py`, `backend/operations/backup.py`, `backend/operations/restore.py`, `backend/operations/cli.py`, `tests/operations/test_backup_restore.py`.

**Forbidden files:** `release/**`, live production data, secret files, packaging manifests, database migrations, and web/public code.

**Interfaces:**
- Consumes explicit `station_id`, resolved station `data_root`, one `config/stations/<station_id>.json` profile path, and the selected `config/voices/<voice_pack>/` metadata root. It never infers configuration as a child of `data_root`.
- The SQLite source is exactly `<data_root>/radio.db`; schedule truth is backed up through that database's schedule/program tables, not a fabricated `schedules/` directory.
- Produces `BackupResult`, a SQLite online-backup archive, canonical `backup-manifest.json`, `create_backup()`, `verify_backup()`, and staged atomic `restore_backup()`.

- [ ] **Step 1: Write failing round-trip, schedule, configuration, and traversal tests**

Create `tests/operations/test_backup_restore.py`:

```python
from pathlib import Path
import sqlite3
import tarfile

import pytest

from backend.operations.backup import create_backup, verify_backup
from backend.operations.restore import restore_backup


def _station(root: Path) -> tuple[Path, Path, Path]:
    station_id = "radiotedu-en"
    data_root = root / "data" / "stations" / station_id
    profile_path = root / "config" / "stations" / f"{station_id}.json"
    voice_root = root / "config" / "voices" / "radiotedu-en-voices-v1"
    data_root.mkdir(parents=True)
    profile_path.parent.mkdir(parents=True)
    voice_root.mkdir(parents=True)
    with sqlite3.connect(data_root / "radio.db") as db:
        db.execute("create table plays(id integer primary key, title text)")
        db.execute("insert into plays(title) values ('Blue Room')")
        db.execute("create table program_schedule(id integer primary key, title text)")
        db.execute("insert into program_schedule(title) values ('Morning Energy')")
    profile_path.write_text(
        '{"station_id":"radiotedu-en","voice_pack":"radiotedu-en-voices-v1"}\\n',
        encoding="utf-8",
    )
    (voice_root / "metadata.json").write_text(
        '{"voice_pack":"radiotedu-en-voices-v1","checksum":"abc123"}\\n',
        encoding="utf-8",
    )
    return data_root, profile_path, voice_root


def test_online_backup_round_trip(tmp_path: Path) -> None:
    source, restored = tmp_path / "source", tmp_path / "restored"
    data_root, profile_path, voice_root = _station(source)
    result = create_backup(
        station_id="radiotedu-en",
        data_root=data_root,
        profile_path=profile_path,
        voice_metadata_root=voice_root,
        output=tmp_path / "backups",
    )
    verify_backup(result.archive)
    restore_backup(
        result.archive,
        data_root=restored / "data" / "stations" / "radiotedu-en",
        profile_path=restored / "config" / "stations" / "radiotedu-en.json",
        voice_metadata_root=restored / "config" / "voices" / "radiotedu-en-voices-v1",
        replace=True,
    )
    with sqlite3.connect(restored / "data" / "stations" / "radiotedu-en" / "radio.db") as db:
        assert db.execute("select title from plays").fetchone()[0] == "Blue Room"
        assert db.execute("select title from program_schedule").fetchone()[0] == "Morning Energy"
    assert (restored / "config" / "stations" / "radiotedu-en.json").is_file()
    assert (restored / "config" / "voices" / "radiotedu-en-voices-v1" / "metadata.json").is_file()


def test_restore_rejects_path_traversal_before_writing(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("../../outside.txt")
        info.size = 1
        tar.addfile(info, __import__("io").BytesIO(b"x"))
    with pytest.raises(ValueError, match="unsafe archive path"):
        restore_backup(
            archive,
            data_root=tmp_path / "data" / "stations" / "radiotedu-en",
            profile_path=tmp_path / "config" / "stations" / "radiotedu-en.json",
            voice_metadata_root=tmp_path / "config" / "voices" / "radiotedu-en-voices-v1",
            replace=True,
        )
    assert not (tmp_path / "outside.txt").exists()
```

- [ ] **Step 2: Run backup tests and verify RED**

Run: `python -m pytest tests/operations/test_backup_restore.py -v`

Expected: collection ERROR because `backend.operations` does not exist.

- [ ] **Step 3: Implement online backup and verification**

Create `backend/operations/backup.py` with:

```python
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

ARCHIVE_DATABASE = Path("runtime/radio.db")
ARCHIVE_PROFILE_DIR = Path("profile")
ARCHIVE_VOICE_DIR = Path("voice-pack")


@dataclass(frozen=True)
class BackupResult:
    station_id: str
    archive: Path
    sha256: str
    file_count: int


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_backup(
    station_id: str,
    data_root: Path,
    profile_path: Path,
    voice_metadata_root: Path,
    output: Path,
) -> BackupResult:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile["station_id"] != station_id:
        raise ValueError("station identity mismatch")
    if voice_metadata_root.name != profile["voice_pack"]:
        raise ValueError("voice-pack identity mismatch")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        stage = Path(temporary) / station_id
        (stage / ARCHIVE_DATABASE.parent).mkdir(parents=True)
        with sqlite3.connect(data_root / "radio.db") as source:
            with sqlite3.connect(stage / ARCHIVE_DATABASE) as target:
                source.backup(target)
        (stage / ARCHIVE_PROFILE_DIR).mkdir()
        shutil.copy2(profile_path, stage / ARCHIVE_PROFILE_DIR / profile_path.name)
        shutil.copytree(voice_metadata_root, stage / ARCHIVE_VOICE_DIR)
        files = sorted(path for path in stage.rglob("*") if path.is_file())
        manifest = {
            "schema_version": 1,
            "station_id": station_id,
            "voice_pack": profile["voice_pack"],
            "schedule_storage": ARCHIVE_DATABASE.as_posix(),
            "files": {path.relative_to(stage).as_posix(): _sha(path) for path in files},
        }
        (stage / "backup-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\\n", encoding="utf-8"
        )
        archive = output / f"{station_id}-backup.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(stage, arcname=station_id)
    return BackupResult(station_id, archive, _sha(archive), len(files))


def verify_backup(archive: Path) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise ValueError("unsafe archive path")
            tar.extractall(temporary, filter="data")
        roots = [path for path in Path(temporary).iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ValueError("backup must contain one station root")
        root = roots[0]
        manifest = json.loads((root / "backup-manifest.json").read_text(encoding="utf-8"))
        for relative, expected in manifest["files"].items():
            if _sha(root / relative) != expected:
                raise ValueError(f"backup checksum mismatch: {relative}")
        with sqlite3.connect(root / ARCHIVE_DATABASE) as db:
            if db.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise ValueError("sqlite integrity check failed")
        return manifest
```

- [ ] **Step 4: Implement staged atomic restore and CLI**

`restore_backup(archive, data_root, profile_path, voice_metadata_root, replace)` first calls `verify_backup()`, extracts into a private staging directory, verifies the station and voice-pack identities, prepares all three configured targets, fsyncs staged files, and replaces them with rollback records. `replace=False` performs verification only and never writes a target.

`backend/operations/cli.py` uses argparse subcommands with the frozen command signatures above. It returns `0` only after verification, `2` for invalid arguments, and `1` for a rejected backup/restore operation; output is one JSON object with no secret values or absolute source paths.

Implement the atomic replacement path as:

```python
def restore_backup(
    archive: Path,
    data_root: Path,
    profile_path: Path,
    voice_metadata_root: Path,
    replace: bool,
) -> None:
    manifest = verify_backup(archive)
    if not replace:
        return
    with tempfile.TemporaryDirectory(dir=data_root.parent) as temporary:
        extracted = Path(temporary) / "verified"
        extracted.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise ValueError("unsafe archive path")
            tar.extractall(extracted, filter="data")
        archive_root = extracted / manifest["station_id"]
        archived_profile = next((archive_root / ARCHIVE_PROFILE_DIR).glob("*.json"))
        profile = json.loads(archived_profile.read_text(encoding="utf-8"))
        if profile["station_id"] != manifest["station_id"]:
            raise ValueError("station identity mismatch")
        if profile["voice_pack"] != manifest["voice_pack"]:
            raise ValueError("voice-pack identity mismatch")

        staged_data = data_root.parent / f".{data_root.name}.restore"
        staged_profile = profile_path.with_suffix(profile_path.suffix + ".restore")
        staged_voice = voice_metadata_root.parent / f".{voice_metadata_root.name}.restore"
        shutil.rmtree(staged_data, ignore_errors=True)
        shutil.rmtree(staged_voice, ignore_errors=True)
        staged_profile.unlink(missing_ok=True)
        staged_data.mkdir(parents=True)
        shutil.copy2(archive_root / ARCHIVE_DATABASE, staged_data / "radio.db")
        staged_profile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archived_profile, staged_profile)
        shutil.copytree(archive_root / ARCHIVE_VOICE_DIR, staged_voice)

        atomic_replace_many(
            (
                (data_root, staged_data),
                (profile_path, staged_profile),
                (voice_metadata_root, staged_voice),
            ),
            rollback_suffix=".pre-restore",
        )
```

Implement `atomic_replace_many` in `backend/operations/restore.py`: every target and staged path must resolve under its configured parent; fsync each staged file and directory; move existing targets to sibling `.pre-restore` paths; promote all staged paths; if any promotion fails, remove already-promoted targets and restore every previous path in reverse order. Delete rollback paths only after all three promotions and a reopened SQLite integrity check succeed. This is a coordinated rollback protocol, not a claim of cross-filesystem atomicity.

- [ ] **Step 5: Run round-trip, negative, and full database tests**

Run:

```bash
python -m pytest tests/operations/test_backup_restore.py -v
python -m pytest tests/backend/test_core_behaviour.py -q
```

Expected: online round-trip and traversal tests PASS; existing database behavior remains green.

- [ ] **Step 6: Commit backup and restore**

```bash
git add backend/operations tests/operations/test_backup_restore.py
git commit -m "ops: add verified station backup and atomic restore"
```

### Task 7: Export Redacted Operational Diagnostics

**Dependencies:** Task 6 and station-scoped health interfaces.

**Owned files:** `backend/operations/diagnostics.py`, `backend/operations/cli.py` diagnostics subcommand, `tests/operations/test_diagnostics.py`.

**Forbidden files:** `release/**`, raw secrets, full environment dumps, listener messages/identities, music files, database rows, model weights, and installer code.

**Interfaces:**
- Consumes: explicit role/root, allowlisted health JSON, release manifest, service status, last 200 redacted log lines, disk/cpu/memory summaries, and per-station queue/stream metrics.
- Produces: `export_diagnostics(role, root, output) -> DiagnosticsResult` and deterministic zip containing `summary.json`, `health.json`, `services.json`, and `logs/*.log`.

- [ ] **Step 1: Write failing redaction tests**

Create `tests/operations/test_diagnostics.py`:

```python
from pathlib import Path
import zipfile

from backend.operations.diagnostics import export_diagnostics, redact


def test_redact_removes_credentials_paths_and_listener_identity() -> None:
    value = redact({
        "PUBLIC_SYNC_TOKEN": "secret-token",
        "Authorization": "Bearer private",
        "listener_email": "student@example.edu",
        "database_path": r"C:\\RadioTEDU\\private\\station.db",
        "status": "degraded",
    })
    assert value == {
        "PUBLIC_SYNC_TOKEN": "[REDACTED]",
        "Authorization": "[REDACTED]",
        "listener_email": "[REDACTED]",
        "database_path": "[REDACTED_PATH]",
        "status": "degraded",
    }


def test_export_contains_only_allowlisted_files(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "backend.log").write_text("PUBLIC_SYNC_TOKEN=secret\\nstatus=ok\\n")
    (root / "secrets").mkdir()
    (root / "secrets" / "private.env").write_text("TOKEN=secret\\n")
    result = export_diagnostics("broadcast", root, tmp_path / "diagnostics.zip")
    with zipfile.ZipFile(result.archive) as archive:
        names = set(archive.namelist())
        body = b"".join(archive.read(name) for name in names)
    assert names <= {"summary.json", "health.json", "services.json", "logs/backend.log"}
    assert b"secret" not in body
```

- [ ] **Step 2: Run diagnostics tests and verify RED**

Run: `python -m pytest tests/operations/test_diagnostics.py -v`

Expected: collection ERROR because `backend.operations.diagnostics` does not exist.

- [ ] **Step 3: Implement recursive redaction and allowlisted export**

Create `backend/operations/diagnostics.py`:

```python
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECRET = re.compile(r"(token|secret|password|authorization|cookie|listener_(email|id|ip))", re.I)
PATH_KEY = re.compile(r"(path|directory|root|music_dir|database)", re.I)


@dataclass(frozen=True)
class DiagnosticsResult:
    role: str
    archive: Path
    files: tuple[str, ...]


def redact(value: Any, key: str = "") -> Any:
    if SECRET.search(key):
        return "[REDACTED]"
    if PATH_KEY.search(key) and isinstance(value, str):
        return "[REDACTED_PATH]"
    if isinstance(value, dict):
        return {name: redact(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(token|secret|password|authorization)=\\S+", r"\\1=[REDACTED]", value)
        value = re.sub(r"(?i)Bearer\\s+\\S+", "Bearer [REDACTED]", value)
    return value


def export_diagnostics(role: str, root: Path, output: Path) -> DiagnosticsResult:
    documents = {
        "summary.json": {"role": role, "diagnostic_schema": 1},
        "health.json": {},
        "services.json": {},
    }
    logs = sorted((root / "logs").glob("*.log")) if (root / "logs").exists() else []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in documents.items():
            archive.writestr(name, json.dumps(redact(value), sort_keys=True, indent=2) + "\\n")
        for path in logs:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
            archive.writestr(f"logs/{path.name}", "\\n".join(redact(lines)) + "\\n")
    with zipfile.ZipFile(output) as archive:
        files = tuple(sorted(archive.namelist()))
    return DiagnosticsResult(role, output, files)
```

Extend `backend.operations.cli` with the exact `diagnostics` signature and print only archive name, SHA-256, role, and included file names.

- [ ] **Step 4: Run diagnostics and secret-corpus tests**

Run: `python -m pytest tests/operations/test_diagnostics.py -v`

Expected: redaction and allowlist tests PASS, and no fixture secret occurs in the zip bytes.

- [ ] **Step 5: Commit diagnostics**

```bash
git add backend/operations/diagnostics.py backend/operations/cli.py tests/operations/test_diagnostics.py
git commit -m "ops: add privacy-safe diagnostic exports"
```

### Task 8: Qualify Both Packages on Clean Machines

**Dependencies:** Tasks 4–7.

**Owned files:** `scripts/qualify_clean_install.ps1`, `scripts/qualify_clean_install.sh`, `tests/qualification/test_clean_install_contract.py`, `docs/CLEAN_INSTALL_QUALIFICATION.md`.

**Forbidden files:** `release/**`, source working tree during target execution, production hosts, production credentials, and runtime implementation.

**Interfaces:**
- Consumes: signed broadcast zip, signed webserver tarball, public key, disposable Windows Server 2022/Windows 11 and Ubuntu 24.04 machines.
- Produces: `clean-install-windows.json` and `clean-install-linux.json` with artifact digest, OS, install/boot/restart/uninstall/restore checks, timestamps, and zero source-repository dependency.

- [ ] **Step 1: Write failing plan-mode tests**

Create `tests/qualification/test_clean_install_contract.py`:

```python
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_windows_clean_install_plan_has_reboot_and_music_only_checks() -> None:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(ROOT / "scripts/qualify_clean_install.ps1"), "-PlanJson"],
        check=True, capture_output=True, text=True,
    )
    plan = json.loads(result.stdout)
    assert plan["role"] == "broadcast"
    assert plan["requires_source_repository"] is False
    assert {"install", "reboot", "dual_stream", "qwen_failure_music_only", "restore", "uninstall"} <= set(plan["checks"])


def test_linux_clean_install_plan_has_hardening_and_route_checks() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/qualify_clean_install.sh"), "--plan-json"],
        check=True, capture_output=True, text=True,
    )
    plan = json.loads(result.stdout)
    assert plan["role"] == "webserver"
    assert plan["requires_source_repository"] is False
    assert {"signature", "systemd_hardening", "ai_alias", "english_route", "french_route", "uninstall"} <= set(plan["checks"])
```

- [ ] **Step 2: Run clean-install contract tests and verify RED**

Run: `python -m pytest tests/qualification/test_clean_install_contract.py -v`

Expected: FAIL because both qualification scripts are missing.

- [ ] **Step 3: Implement non-destructive plan mode and destructive disposable-host mode**

`qualify_clean_install.ps1` requires `-Artifact`, `-Manifest`, `-Signature`, `-PublicKey`, and `-EvidenceDir` outside `-PlanJson` mode. It verifies metadata before install, asserts no `.git` or source checkout exists, installs, runs readiness, reboots, verifies automatic service recovery, checks both Icecast mounts, stops Qwen and proves continuous music with TTS degraded, restores a backup, uninstalls without deleting data, and writes canonical evidence JSON.

`qualify_clean_install.sh` accepts corresponding long options, verifies signature/checksum before extraction, installs, uses `systemd-analyze security radiotedu-web.service --json=short`, reboots, checks `/ai`, `/ai/en`, `/ai/fr` and station-scoped status, tests wrong-station HMAC rejection, uninstalls while preserving data, and writes canonical evidence JSON.

Both scripts refuse a hostname not beginning with `radiotedu-qual-` unless `--disposable-host-confirmed` / `-DisposableHostConfirmed` is supplied.

Each plan mode emits this complete contract, with the role-specific check list selected by the script:

```python
def clean_install_plan(role: str) -> dict:
    checks = {
        "broadcast": [
            "signature", "install", "reboot", "dual_stream",
            "qwen_failure_music_only", "restore", "uninstall",
        ],
        "webserver": [
            "signature", "systemd_hardening", "ai_alias",
            "english_route", "french_route", "wrong_station_rejected", "uninstall",
        ],
    }
    if role not in checks:
        raise ValueError(f"unsupported qualification role: {role}")
    return {
        "schema_version": 1,
        "role": role,
        "requires_source_repository": False,
        "checks": checks[role],
    }
```

- [ ] **Step 4: Document exact clean-machine procedure**

`docs/CLEAN_INSTALL_QUALIFICATION.md` records image names, minimum CPU/RAM/disk/GPU, artifact transfer, disposable credentials, commands, reboot continuation, evidence paths, expected exit codes, and cleanup. It states that passing unit/static tests never substitutes for both clean-machine runs.

- [ ] **Step 5: Run contract tests and plan-mode commands**

Run:

```powershell
py -3.12 -m pytest tests/qualification/test_clean_install_contract.py -v
pwsh -NoProfile -File scripts/qualify_clean_install.ps1 -PlanJson
bash scripts/qualify_clean_install.sh --plan-json
```

Expected: tests PASS and each command emits one valid JSON plan without changing the host.

- [ ] **Step 6: Commit clean-install qualification**

```bash
git add scripts/qualify_clean_install.ps1 scripts/qualify_clean_install.sh tests/qualification/test_clean_install_contract.py docs/CLEAN_INSTALL_QUALIFICATION.md
git commit -m "test: add clean-machine release qualification"
```

### Task 9: Run Independent Security and Station-Isolation Audits

**Dependencies:** Tasks 2, 4, 5, 7 and completed station/snapshot isolation.

**Owned files:** `qualification/security_policy.json`, `scripts/audit_release.py`, `tests/qualification/test_release_security.py`, `docs/SECURITY_QUALIFICATION.md`.

**Forbidden files:** implementation source, secrets, production data, `release/**`, and approval of the reviewer's own code.

**Interfaces:**
- Consumes: extracted role payloads and disposable dual-station runtime URLs.
- Produces: `security-audit.json` with checks `artifact_allowlist`, `secret_scan`, `public_surface`, `snapshot_negative_cases`, `cross_station_storage`, `cross_station_cache`, `cross_station_stream`, and `service_hardening`.

- [ ] **Step 1: Write failing artifact-policy tests**

Create `tests/qualification/test_release_security.py`:

```python
import json
from pathlib import Path

from scripts.audit_release import audit_tree


def test_webserver_tree_rejects_private_modules_and_secret_shapes(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "radio_agent.py").write_text("TOKEN='abc'\\n")
    report = audit_tree("webserver", tmp_path)
    assert report["passed"] is False
    assert {finding["rule"] for finding in report["findings"]} >= {
        "webserver-private-module",
        "embedded-secret",
    }


def test_policy_contains_all_snapshot_negative_cases() -> None:
    root = Path(__file__).resolve().parents[2]
    policy = json.loads((root / "qualification/security_policy.json").read_text())
    assert set(policy["snapshot_rejections"]) == {
        "wrong_station", "invalid_signature", "stale_timestamp", "replayed_nonce",
        "duplicate_sequence", "out_of_order_sequence", "oversized_body", "malformed_schema",
    }
```

- [ ] **Step 2: Run security tests and verify RED**

Run: `python -m pytest tests/qualification/test_release_security.py -v`

Expected: collection ERROR because `scripts.audit_release` is absent.

- [ ] **Step 3: Implement explicit policy and read-only audit**

`qualification/security_policy.json` lists exact forbidden webserver modules, forbidden secret key patterns, maximum public response keys, eight Snapshot v2 rejection cases, expected systemd/WinSW hardening, and cross-station probes. `audit_tree(role: str, root: Path) -> dict` walks only the extracted payload, records relative paths and rule IDs, never prints matching secret values, and exits nonzero for any finding.

Dynamic audit mode submits every signed-snapshot negative case, attempts English credentials on French paths and the reverse, writes sentinel data into each station database/cache/artwork/log root, and proves the other station cannot read or mutate it. It then stops English Liquidsoap/Icecast and proves French remains live, repeats in reverse, and stores request IDs rather than credentials.

Implement the static entry point as:

```python
def audit_tree(role: str, root: Path) -> dict:
    findings: list[dict[str, str]] = []
    private_web_modules = {
        "backend/app.py",
        "backend/liquidsoap.py",
        "backend/music_library.py",
        "backend/ollama_setup.py",
        "backend/orchestrator.py",
        "backend/playback.py",
        "backend/radio_agent.py",
        "backend/tts/__init__.py",
        "backend/tts/base.py",
        "backend/tts/dummy_tts.py",
        "backend/tts/factory.py",
        "backend/tts/piper_tts.py",
        "backend/tts/qwen_tts.py",
        "backend/tts/sapi_tts.py",
        "scripts/run_broadcast_computer.py",
        "scripts/qwen_tts_command.py",
    }
    secret_pattern = re.compile(
        rb"(?i)(token|secret|password|authorization)\\s*[:=]\\s*['\\\"][^'\\\"]+"
    )
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if role == "webserver" and relative in private_web_modules:
            findings.append({"rule": "webserver-private-module", "path": relative})
        if path.stat().st_size <= 2_000_000 and secret_pattern.search(path.read_bytes()):
            findings.append({"rule": "embedded-secret", "path": relative})
    return {
        "schema_version": 1,
        "role": role,
        "passed": not findings,
        "findings": findings,
    }
```

- [ ] **Step 4: Document independent review roles**

`docs/SECURITY_QUALIFICATION.md` requires a strong security reviewer who did not implement Tasks 2, 4, 5, or 7. OpenCode performs a second read-only artifact and policy cross-check. Disagreements become bounded remediation cards with rule ID, owned files, reproduction command, and evidence required for closure.

- [ ] **Step 5: Run static policy tests**

Run:

```bash
python -m pytest tests/qualification/test_release_security.py -v
python scripts/audit_release.py --role broadcast --root artifacts/extracted/broadcast --output artifacts/evidence/security-broadcast.json
python scripts/audit_release.py --role webserver --root artifacts/extracted/webserver --output artifacts/evidence/security-webserver.json
```

Expected: unit tests PASS; both audit commands report `"passed": true` against built artifacts, with zero secret values in evidence.

- [ ] **Step 6: Commit security qualification**

```bash
git add qualification/security_policy.json scripts/audit_release.py tests/qualification/test_release_security.py docs/SECURITY_QUALIFICATION.md
git commit -m "test: add independent release security audits"
```

### Task 10: Qualify Eight Qwen Voices and Finished Audio

**Dependencies:** signed English/French voice packs, Qwen scheduler, pronunciation dictionaries, audio finishing, and both station profiles.

**Owned files:** `qualification/voice-audio-policy.json`, `scripts/qualify_voice_audio.py`, `tests/qualification/test_voice_audio_qualification.py`, `docs/VOICE_AUDIO_QUALIFICATION.md`.

**Forbidden files:** voice model/reference mutation, synthetic fallback engines, editorial prompts, production queues, `release/**`, and reviewer identities in public artifacts.

**Interfaces:**
- Consumes: 60-script matrix per host, 500 synthesized clips per language, ffprobe/ffmpeg measurements, English reviewer scores, native-French reviewer scores, blind host assignments, model/voice checksums.
- Produces: `voice-audio-qualification.json`; PASS requires eight hosts, 60 scripts each, 500 valid clips per language, reviewer averages at least `4.0/5`, blind recognition at least `0.90`, approximately `-16 LUFS`, approximately `-1 dBTP`, and zero silent/corrupt/clipped/substitute clips.

- [ ] **Step 1: Write failing threshold tests**

Create `tests/qualification/test_voice_audio_qualification.py`:

```python
from scripts.qualify_voice_audio import evaluate


def _evidence() -> dict:
    return {
        "hosts": {name: {"scripts": 60, "mean_score": 4.3, "blind_correct": 57, "blind_total": 60}
                  for name in ("maya", "elliot", "selin", "theo", "camille", "mathieu", "elodie", "jules")},
        "languages": {
            "en": {"clips": 500, "invalid": 0, "substitutes": 0, "lufs_outside": 0, "peak_outside": 0},
            "fr-FR": {"clips": 500, "invalid": 0, "substitutes": 0, "lufs_outside": 0, "peak_outside": 0},
        },
        "native_french_approved": True,
        "qwen_only": True,
    }


def test_complete_evidence_passes() -> None:
    assert evaluate(_evidence())["passed"] is True


def test_one_fallback_clip_fails_release() -> None:
    evidence = _evidence()
    evidence["languages"]["en"]["substitutes"] = 1
    report = evaluate(evidence)
    assert report["passed"] is False
    assert "qwen-only" in report["failed_gates"]
```

- [ ] **Step 2: Run qualification tests and verify RED**

Run: `python -m pytest tests/qualification/test_voice_audio_qualification.py -v`

Expected: collection ERROR because `scripts.qualify_voice_audio` is absent.

- [ ] **Step 3: Implement deterministic evidence evaluation**

`qualification/voice-audio-policy.json` names the eight approved hosts and exact thresholds. `evaluate(evidence: dict) -> dict` returns every gate with actual, required, pass/fail, and source-evidence digest. CLI collection mode validates WAV decoding, non-silence, sample rate, duration, integrated loudness, true peak, voice/host/style/cache metadata, and exact `qwen` provider provenance for every clip.

Human score inputs are signed CSV files with `clip_id, reviewer_id_hash, warmth, naturalness, clarity, identity, program_fit`. French approval additionally covers diction, phrasing, liaison, names, dates, numbers, and cultural tone. Blind assignments are scored by clip ID without exposing the expected host until evaluation.

Implement gate evaluation as:

```python
def evaluate(evidence: dict) -> dict:
    failed: list[str] = []
    hosts = evidence.get("hosts", {})
    if len(hosts) != 8 or any(value["scripts"] < 60 for value in hosts.values()):
        failed.append("host-script-coverage")
    if any(value["mean_score"] < 4.0 for value in hosts.values()):
        failed.append("human-score")
    if any(value["blind_total"] == 0 or value["blind_correct"] / value["blind_total"] < 0.90 for value in hosts.values()):
        failed.append("blind-host-recognition")
    languages = evidence.get("languages", {})
    if set(languages) != {"en", "fr-FR"} or any(value["clips"] < 500 for value in languages.values()):
        failed.append("language-clip-coverage")
    if not evidence.get("qwen_only") or any(value["substitutes"] for value in languages.values()):
        failed.append("qwen-only")
    if any(value["invalid"] or value["lufs_outside"] or value["peak_outside"] for value in languages.values()):
        failed.append("audio-validity")
    if not evidence.get("native_french_approved"):
        failed.append("native-french-review")
    return {"schema_version": 1, "passed": not failed, "failed_gates": failed}
```

- [ ] **Step 4: Document audition and rejection procedure**

`docs/VOICE_AUDIO_QUALIFICATION.md` defines randomized clip order, headphone/level calibration, reviewer separation, conflict adjudication, evidence signing, pronunciation regression, and rejection of SAPI, Piper, cloud, dummy, silence-as-speech, or unknown provenance.

- [ ] **Step 5: Run harness tests and full evidence evaluation**

Run:

```bash
python -m pytest tests/qualification/test_voice_audio_qualification.py -v
python scripts/qualify_voice_audio.py --policy qualification/voice-audio-policy.json --clips artifacts/qualification/clips --reviews artifacts/qualification/reviews --output artifacts/evidence/voice-audio-qualification.json
```

Expected: unit tests PASS; the full command exits `0` only when all eight host, English, French, Qwen-only, pronunciation, and audio gates pass.

- [ ] **Step 6: Commit voice/audio qualification**

```bash
git add qualification/voice-audio-policy.json scripts/qualify_voice_audio.py tests/qualification/test_voice_audio_qualification.py docs/VOICE_AUDIO_QUALIFICATION.md
git commit -m "test: add Qwen voice and audio release gates"
```

### Task 11: Run the 24-Hour Dual-Station Soak and Seven-Day Canary

**Dependencies:** Tasks 8–10 and a release candidate installed on qualified machines.

**Owned files:** `qualification/resilience-policy.json`, `scripts/run_release_qualification.py`, `tests/qualification/test_resilience_evidence.py`, `docs/RELEASE_QUALIFICATION_RUNBOOK.md`.

**Forbidden files:** runtime implementation, production secrets, real listener identities, `release/**`, and mutation of the candidate artifact after its recorded digest.

**Interfaces:**
- Consumes: English/French health, Icecast mount samples, Qwen synthesis health, prepared-buffer depths, supervisor events, silence detector events, snapshot sequence/staleness, host resource metrics, and signed release digest.
- Produces: append-only JSONL samples, canonical `24h-soak-summary.json` and `7d-canary-summary.json`, and `verify_evidence_index(evidence_dir: Path, required: tuple[str, ...]) -> dict`.

- [ ] **Step 1: Write failing fake-clock gate tests**

Create `tests/qualification/test_resilience_evidence.py`:

```python
from scripts.run_release_qualification import summarize


def test_soak_requires_full_duration_and_both_streams() -> None:
    samples = [
        {"at": 0, "en_audio": True, "fr_audio": True, "dead_air_seconds": 0, "severity": None},
        {"at": 86_400, "en_audio": True, "fr_audio": True, "dead_air_seconds": 0, "severity": None},
    ]
    assert summarize("soak", samples)["passed"] is True
    assert summarize("soak", samples[:1])["passed"] is False


def test_canary_rejects_unresolved_severity_two() -> None:
    samples = [
        {"at": 0, "en_audio": True, "fr_audio": True, "dead_air_seconds": 0, "severity": None},
        {"at": 604_800, "en_audio": True, "fr_audio": True, "dead_air_seconds": 0,
         "severity": 2, "resolved": False},
    ]
    report = summarize("canary", samples)
    assert report["passed"] is False
    assert "unresolved-severity-1-or-2" in report["failed_gates"]
```

- [ ] **Step 2: Run resilience tests and verify RED**

Run: `python -m pytest tests/qualification/test_resilience_evidence.py -v`

Expected: collection ERROR because `scripts.run_release_qualification` is absent.

- [ ] **Step 3: Implement append-only sampling and summaries**

`qualification/resilience-policy.json` fixes `soak_seconds=86400`, `canary_seconds=604800`, `sample_interval_seconds=15`, zero dead-air tolerance, minimum Qwen buffers of five when healthy, music-only continuity while degraded, and zero unresolved severity 1/2 incidents.

`run_release_qualification.py` provides `collect(mode, endpoints, evidence_path)` and `summarize(mode, samples)`. Each JSONL record contains prior-record SHA-256, release digest, monotonic timestamp, wall-clock UTC, station health, audio-present result, queue depth, Qwen real-synthesis result, snapshot freshness, resource metrics, and active incidents. Summary verification recalculates the chain and rejects gaps longer than twice the sample interval.

`verify_evidence_index()` loads the required signed evidence documents, verifies each recorded candidate digest equals the unsigned payload digest, rejects missing/failed/unsigned documents, and writes `qualification-index.json` containing sorted evidence names and SHA-256 values. Its CLI is `verify-index --evidence PATH --require NAME [NAME ...]`.

The 24-hour soak includes controlled failure injections for Qwen, each station's Liquidsoap, each station's Icecast, web synchronization, and process restart. The seven-day canary uses monitored broadcast hours, forbids artifact/config changes without a restarted canary, and records operator acknowledgement and closure for every incident.

Implement summary gates as:

```python
def summarize(mode: str, samples: list[dict]) -> dict:
    required_seconds = {"soak": 86_400, "canary": 604_800}
    if mode not in required_seconds:
        raise ValueError(f"unsupported qualification mode: {mode}")
    failed: list[str] = []
    duration = samples[-1]["at"] - samples[0]["at"] if len(samples) >= 2 else 0
    if duration < required_seconds[mode]:
        failed.append("incomplete-duration")
    if any(not sample["en_audio"] or not sample["fr_audio"] for sample in samples):
        failed.append("stream-interruption")
    if any(sample["dead_air_seconds"] > 0 for sample in samples):
        failed.append("dead-air")
    if any(sample.get("severity") in (1, 2) and not sample.get("resolved", False) for sample in samples):
        failed.append("unresolved-severity-1-or-2")
    return {
        "schema_version": 1,
        "mode": mode,
        "duration_seconds": duration,
        "passed": not failed,
        "failed_gates": failed,
    }
```

- [ ] **Step 4: Document stop/continue/rollback decisions**

`docs/RELEASE_QUALIFICATION_RUNBOOK.md` defines severity levels, evidence custody, safe failure-injection windows, immediate rollback triggers, canary restart conditions, and the rule that incomplete duration, missing samples, or unsigned summaries fail closed.

- [ ] **Step 5: Run unit tests, then qualification commands**

Run:

```bash
python -m pytest tests/qualification/test_resilience_evidence.py -v
python scripts/run_release_qualification.py soak --duration-seconds 86400 --interval-seconds 15 --output artifacts/evidence/soak.jsonl
python scripts/run_release_qualification.py summarize --mode soak --input artifacts/evidence/soak.jsonl --output artifacts/evidence/24h-soak-summary.json
python scripts/run_release_qualification.py canary --duration-seconds 604800 --interval-seconds 15 --output artifacts/evidence/canary.jsonl
python scripts/run_release_qualification.py summarize --mode canary --input artifacts/evidence/canary.jsonl --output artifacts/evidence/7d-canary-summary.json
```

Expected: unit tests PASS; soak and canary summaries contain `"passed": true`, complete durations, unbroken evidence chains, zero dead air, and no unresolved severity 1/2 incident.

- [ ] **Step 6: Commit resilience qualification**

```bash
git add qualification/resilience-policy.json scripts/run_release_qualification.py tests/qualification/test_resilience_evidence.py docs/RELEASE_QUALIFICATION_RUNBOOK.md
git commit -m "test: gate releases on soak and canary evidence"
```

### Task 12: Orchestrate, Sign, and Publish the Qualified Release

**Dependencies:** Tasks 1–11 green with independent review evidence.

**Owned files:** `packaging/ownership.json`, `.github/workflows/release.yml`, `docs/RELEASE_RUNBOOK.md`, `tests/release/test_release_workflow.py`.

**Forbidden files:** `release/**`, private signing key material, implementation files owned by prior tasks, mutable candidate artifacts after signing, and bypass labels/flags.

**Interfaces:**
- Consumes: annotated version tag, exact locks, deterministic payloads, independent audit JSON, clean-install JSON, voice/audio JSON, 24-hour soak summary, seven-day canary summary, protected GitHub environment `radiotedu-release`, and secret `RELEASE_SIGNING_PRIVATE_KEY_B64`.
- Produces: signed GitHub release with both payloads, manifests, SPDX SBOMs, SHA-256 files, detached Ed25519 signatures, public key fingerprint, and one qualification index linking every evidence digest.

- [ ] **Step 1: Write failing workflow-policy tests**

Create `tests/release/test_release_workflow.py`:

```python
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_orders_unsigned_qualification_before_signing() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert workflow.index("build-unsigned:") < workflow.index("qualify-clean:")
    assert workflow.index("qualify-clean:") < workflow.index("sign:")
    assert workflow.index("sign:") < workflow.index("publish:")
    assert "environment: radiotedu-release" in workflow
    assert "RELEASE_SIGNING_PRIVATE_KEY_B64" in workflow
    assert "release/" not in workflow
    assert not re.search(r"uses:\s+[^\s]+@v\d", workflow)


def test_ownership_caps_workers_and_separates_reviewers() -> None:
    policy = json.loads((ROOT / "packaging/ownership.json").read_text())
    assert policy["max_implementation_agents"] == 3
    assert policy["reviewer_may_approve_own_work"] is False
    assert policy["opencode"]["may_bypass_contracts"] is False
    assert {"architecture", "migration", "security", "concurrency", "final_audit"} <= set(policy["strong_review_required"])
```

- [ ] **Step 2: Run workflow tests and verify RED**

Run: `python -m pytest tests/release/test_release_workflow.py -v`

Expected: FAIL because `packaging/ownership.json` and `.github/workflows/release.yml` are absent.

- [ ] **Step 3: Freeze agent ownership and review policy**

Create `packaging/ownership.json`:

```json
{
  "schema_version": 1,
  "max_implementation_agents": 3,
  "reviewer_may_approve_own_work": false,
  "shared_file_owner_per_wave": 1,
  "mini_class_default": [
    "tests",
    "installer scripting",
    "diagnostic harness",
    "qualification harness",
    "runbook updates"
  ],
  "strong_review_required": [
    "architecture",
    "migration",
    "security",
    "concurrency",
    "final_audit"
  ],
  "opencode": {
    "roles": ["independent worker", "read-only reviewer"],
    "may_bypass_contracts": false,
    "may_bypass_file_leases": false,
    "may_bypass_tests": false,
    "may_approve_own_work": false
  },
  "remediation": {
    "bounded_task_card_required": true,
    "required_fields": ["gate", "reproduction", "owned_files", "forbidden_files", "evidence", "commit_boundary"]
  }
}
```

- [ ] **Step 4: Add the gated release workflow**

Create `.github/workflows/release.yml` with jobs in this exact dependency order:

```yaml
name: RadioTEDU release
on:
  workflow_dispatch:
    inputs:
      version:
        description: Qualified semantic version without a v prefix
        required: true
        type: string
      revision:
        description: Qualified 40-character Git revision
        required: true
        type: string
      qualification_run_id:
        description: Actions run containing the qualified-evidence artifact
        required: true
        type: string
permissions:
  contents: write
  actions: read
jobs:
  verify-locks:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: "${{ inputs.revision }}"}
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
        with: {python-version: "3.12.10"}
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020
        with: {node-version: "22.14.0", cache: "npm"}
      - run: python -m pip install --require-hashes -r requirements.lock
      - run: npm ci --ignore-scripts
      - run: python -m pytest tests -q
      - run: npm test
      - run: npm run build
  build-unsigned:
    needs: verify-locks
    strategy:
      matrix: {role: [broadcast, webserver]}
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: "${{ inputs.revision }}"}
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
        with: {python-version: "3.12.10"}
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020
        with: {node-version: "22.14.0", cache: "npm"}
      - run: python -m pip install --require-hashes -r requirements.lock
      - run: npm ci --ignore-scripts && npm run build
      - id: epoch
        shell: bash
        run: echo "value=$(git log -1 --format=%ct)" >> "$GITHUB_OUTPUT"
      - run: python scripts/build_release.py --role "${{ matrix.role }}" --version "${{ inputs.version }}" --revision "${{ inputs.revision }}" --source-date-epoch "${{ steps.epoch.outputs.value }}" --output-dir artifacts/release
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with: {name: "unsigned-${{ matrix.role }}", path: artifacts/release}
  qualify-clean:
    needs: build-unsigned
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: "${{ inputs.revision }}"}
      - env:
          GH_TOKEN: "${{ github.token }}"
        run: gh run download "${{ inputs.qualification_run_id }}" --name qualified-evidence --dir artifacts/evidence
      - run: python scripts/run_release_qualification.py verify-index --evidence artifacts/evidence --require clean-install-windows clean-install-linux
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with: {name: gated-evidence, path: artifacts/evidence}
  evidence-gate:
    needs: qualify-clean
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: "${{ inputs.revision }}"}
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
        with: {name: gated-evidence, path: artifacts/evidence}
      - run: python scripts/run_release_qualification.py verify-index --evidence artifacts/evidence --require clean-install-windows clean-install-linux security isolation voice-audio 24h-soak 7d-canary
  sign:
    needs: evidence-gate
    runs-on: ubuntu-24.04
    environment: radiotedu-release
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: "${{ inputs.revision }}"}
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
        with: {pattern: "unsigned-*", path: artifacts/release, merge-multiple: true}
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
        with: {name: gated-evidence, path: artifacts/evidence}
      - env:
          RELEASE_SIGNING_PRIVATE_KEY_B64: "${{ secrets.RELEASE_SIGNING_PRIVATE_KEY_B64 }}"
        run: python scripts/release_metadata.py sign-directory --input artifacts/release --evidence artifacts/evidence --output artifacts/signed --private-key-env RELEASE_SIGNING_PRIVATE_KEY_B64
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with: {name: signed-release, path: artifacts/signed}
  publish:
    needs: sign
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
        with: {name: signed-release, path: artifacts/signed}
      - env:
          GH_TOKEN: "${{ github.token }}"
        run: gh release create "v${{ inputs.version }}" artifacts/signed/* --target "${{ inputs.revision }}" --title "RadioTEDU v${{ inputs.version }}"
```

The test keeps every third-party action pinned to an immutable commit SHA. The supplied `qualification_run_id` must contain evidence for the same revision and both unsigned artifact digests; `verify-index` rejects any mismatch before the protected signing environment is entered.

- [ ] **Step 5: Write the operator release runbook**

`docs/RELEASE_RUNBOOK.md` defines tag creation, protected-environment approval, public-key rotation, exact evidence inventory, signature verification, clean-machine proof, backup/restore proof, security/isolation review, English/native-French voice signoff, 24-hour soak, seven-day canary, publication, rollback, revocation, and post-release diagnostics. It names no private secret value and forbids manual upload of files not indexed by the signed qualification manifest.

- [ ] **Step 6: Run final workflow and repository verification**

Run:

```bash
python -m pytest tests/release tests/operations tests/qualification -q
python -m pytest tests/backend -q
npm ci --ignore-scripts
npm test
npm run build
git status --short
```

Expected: all Python suites PASS, frontend tests/build PASS, and `git status --short` lists only the intended Task 12 files before commit. `release/` remains untouched and untracked.

- [ ] **Step 7: Commit the release gate**

```bash
git add packaging/ownership.json .github/workflows/release.yml docs/RELEASE_RUNBOOK.md tests/release/test_release_workflow.py
git commit -m "ci: publish only independently qualified releases"
```

## Final Qualification Gate

The orchestrator records every task commit and verifies file ownership before integration. Mini-class agents implement bounded tests, installers, diagnostics, and harnesses; strong reasoning agents review dependency reproducibility, destructive restore behavior, security, concurrency, and final evidence. OpenCode may independently implement a leased task or perform read-only cross-checks, but cannot change frozen interfaces, approve its own output, bypass tests, or merge.

A release is complete only when both signed role artifacts install without the repository, services survive reboot, backup/restore and redacted diagnostics pass, cross-station access fails closed, all eight Qwen hosts and 1,000 language clips pass, both streams complete the 24-hour soak without dead air, and the seven-day canary has no unresolved severity-one or severity-two defect. Signing and publication occur after those immutable-candidate gates, never before them.

## Self-Review Checklist

- Spec coverage: deterministic locks/artifacts, role separation, Windows/Linux services, secret protection, backup/restore, diagnostics, clean-machine installs, security/isolation, voice/audio, 24-hour soak, seven-day canary, signing/SBOM, and delegated governance each map to an explicit task.
- Deferred-content scan: the plan contains no deferred implementation markers or cross-task shorthand; generated resolver output and human evidence are produced by exact commands and schemas.
- Type consistency: `ReleaseBuild`, `build_release()`, `BackupResult`, `DiagnosticsResult`, fixed role names, station IDs, artifact names, and CLI signatures are consistent across producers and consumers.
- Entrypoint check: broadcast supervision names `config/stations`, `radiotedu-en`, and `radiotedu-fr` explicitly; public service and package tests use only `backend.public_app:app` and reject private agent, orchestrator, music, TTS, playback, Liquidsoap, Ollama, and admin modules.
- Boundary check: no task owns or modifies `release/`; generated output is confined to `artifacts/`.
