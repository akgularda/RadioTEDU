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


def test_single_broadcast_computer_runner_exists() -> None:
    runner_path = ROOT / "scripts" / "run_broadcast_computer.py"
    assert runner_path.exists()
    runner = runner_path.read_text(encoding="utf-8")

    assert "check_ollama_setup" in runner
    assert "PublicSnapshotPusher" in runner
    assert "render_liquidsoap_config" in runner
    assert "liquidsoap_status" in runner
    assert "uvicorn" in runner


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
