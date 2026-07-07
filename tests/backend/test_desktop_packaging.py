import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_electron_desktop_admin_shell_is_declared() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

    assert "desktop:dev" in package["scripts"]
    assert "desktop:build" in package["scripts"]
    assert "electron" in package["devDependencies"]
    assert "electron-builder" in package["devDependencies"]

    main = (ROOT / "desktop" / "main.cjs").read_text(encoding="utf-8")
    assert "BrowserWindow" in main
    assert "RadioTEDU Admin Panel" in main
    assert "127.0.0.1" in main
    assert "child_process" in main
    assert "spawn(" in main
    assert "python" in main
    assert "backend.app" in main
    assert "killBackend" in main
    assert "radiotedu.com" not in main


def test_electron_desktop_admin_manages_local_frontend_and_setup_screen() -> None:
    main = (ROOT / "desktop" / "main.cjs").read_text(encoding="utf-8")

    assert "frontendProcess" in main
    assert "RADIOTEDU_MANAGE_FRONTEND" in main
    assert "npm" in main
    assert "run', 'dev" in main
    assert "waitForUrl" in main
    assert "loadSetupScreen" in main
    assert "killFrontend" in main
    assert "did-fail-load" in main
    assert "Backend startup failed" in main


def test_single_broadcast_computer_runner_exists() -> None:
    runner_path = ROOT / "scripts" / "run_broadcast_computer.py"
    assert runner_path.exists()
    runner = runner_path.read_text(encoding="utf-8")

    assert "check_ollama_setup" in runner
    assert "PublicSnapshotPusher" in runner
    assert "render_liquidsoap_config" in runner
    assert "liquidsoap_status" in runner
    assert "uvicorn" in runner


def test_broadcast_runner_declares_backend_orchestrator_and_backoff_contract() -> None:
    runner = (ROOT / "scripts" / "run_broadcast_computer.py").read_text(encoding="utf-8")

    assert "backend_readiness" in runner
    assert "orchestrator_readiness" in runner
    assert "run_backend_with_backoff" in runner
    assert "restart-on-exit" in runner
    assert "backoff_seconds" in runner
    assert "autonomy_enabled" in runner
    assert "settings.autonomy_enabled" in runner


def test_two_machine_runbooks_and_smoke_scripts_exist() -> None:
    broadcast_runbook = ROOT / "docs" / "BROADCAST_COMPUTER_RUNBOOK.md"
    website_runbook = ROOT / "docs" / "WEBSITE_SERVER_RUNBOOK.md"
    broadcast_smoke = ROOT / "scripts" / "smoke_broadcast.py"
    public_smoke = ROOT / "scripts" / "smoke_public_server.py"

    assert broadcast_runbook.exists()
    assert website_runbook.exists()
    assert broadcast_smoke.exists()
    assert public_smoke.exists()

    broadcast_text = broadcast_runbook.read_text(encoding="utf-8")
    website_text = website_runbook.read_text(encoding="utf-8")
    broadcast_script = broadcast_smoke.read_text(encoding="utf-8")
    public_script = public_smoke.read_text(encoding="utf-8")

    for required in [
        "MUSIC_DIR=F:/Songs/Jazz",
        "MIN_READY_ANNOUNCEMENTS=5",
        "PUBLIC_SYNC_URL",
        "Run Air",
        "Liquidsoap",
        "Icecast",
        "Test TTS",
    ]:
        assert required in broadcast_text
    for required in [
        "radiotedu.com/ai",
        "POST /api/public/snapshot",
        "PUBLIC_SYNC_TOKEN",
        "SNAPSHOT_TTL_SECONDS",
        "session/start",
        "No admin controls",
    ]:
        assert required in website_text
    for required in ["check_ollama_setup", "liquidsoap_status", "public_sync_url", "music_library"]:
        assert required in broadcast_script
    for required in ["/api/public/status", "/api/public/session/start", "snapshot", "wrong token"]:
        assert required in public_script


def test_required_local_streaming_and_sync_helpers_exist() -> None:
    liquidsoap_runner = (ROOT / "scripts" / "run_liquidsoap.ps1").read_text(encoding="utf-8")
    icecast_checker = (ROOT / "scripts" / "check_icecast.py").read_text(encoding="utf-8")
    snapshot_pusher = (ROOT / "scripts" / "push_public_snapshot.py").read_text(encoding="utf-8")
    liq_template = (ROOT / "liquidsoap" / "radiotedu.liq").read_text(encoding="utf-8")

    assert "LIQUIDSOAP_SCRIPT" in liquidsoap_runner
    assert "liquidsoap" in liquidsoap_runner.lower()
    assert "/ai" in icecast_checker
    assert "urllib.request" in icecast_checker
    assert "X-RadioTEDU-Sync-Token" in snapshot_pusher
    assert "PUBLIC_SYNC_URL" in snapshot_pusher
    assert 'mount="/ai"' in liq_template
    assert "playlist" in liq_template
