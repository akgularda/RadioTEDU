from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_CONTRACT = ROOT / "config" / "deployment" / "dual-station.json"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _station(contract: dict[str, object], station_id: str) -> dict[str, object]:
    stations = contract["stations"]
    assert isinstance(stations, dict)
    station = stations[station_id]
    assert isinstance(station, dict)
    return station


def test_deployment_contract_keeps_station_roots_databases_and_mounts_distinct() -> None:
    contract = _read_json(DEPLOYMENT_CONTRACT)

    assert contract["contract_version"] == 1
    for station_id, service_name in (
        ("radiotedu-en", "RadioTEDU.Station.EN"),
        ("radiotedu-fr", "RadioTEDU.Station.FR"),
    ):
        station = _station(contract, station_id)
        profile = _read_json(ROOT / "config" / "stations" / f"{station_id}.json")
        runtime = profile["runtime"]
        audio = profile["audio"]

        assert station["service"] == service_name
        assert station["root"] == runtime["data_root"]
        assert station["database"] == runtime["database"]
        assert station["music_root"] == runtime["music_root"]
        assert station["announcement_root"] == runtime["announcement_root"]
        assert station["cache_root"] == runtime["cache_root"]
        assert station["log_root"] == runtime["log_root"]
        assert station["mount"] == audio["stream_mount"]

    en = _station(contract, "radiotedu-en")
    fr = _station(contract, "radiotedu-fr")
    resource_keys = (
        "root",
        "database",
        "music_root",
        "announcement_root",
        "cache_root",
        "log_root",
        "mount",
        "source_credentials_ref",
        "snapshot_secret_ref",
    )
    assert {en[key] for key in resource_keys}.isdisjoint({fr[key] for key in resource_keys})


def test_deployment_contract_gives_each_station_two_distinct_host_fallback_endpoints() -> None:
    contract = _read_json(DEPLOYMENT_CONTRACT)
    stations = (_station(contract, "radiotedu-en"), _station(contract, "radiotedu-fr"))

    endpoints: list[str] = []
    listener_endpoints: list[str] = []
    for station in stations:
        station_id = station["station_id"]
        assert isinstance(station_id, str)
        credentials_ref = station["source_credentials_ref"]
        snapshot_ref = station["snapshot_secret_ref"]
        assert isinstance(credentials_ref, str)
        assert isinstance(snapshot_ref, str)
        assert re.fullmatch(r"RADIOTEDU_(EN|FR)_SOURCE_CREDENTIALS", credentials_ref)
        assert re.fullmatch(r"RADIOTEDU_(EN|FR)_SNAPSHOT_SECRET", snapshot_ref)

        listener_endpoint = station["public_listener_endpoint"]
        assert isinstance(listener_endpoint, str)
        assert listener_endpoint.startswith("https://listen.radiotedu.com/")
        listener_endpoints.append(listener_endpoint)

        host_endpoints = station["host_endpoints"]
        assert isinstance(host_endpoints, dict)
        assert set(host_endpoints) == {"stream-a", "stream-b"}
        for endpoint in host_endpoints.values():
            assert isinstance(endpoint, dict)
            primary = endpoint["primary"]
            fallback = endpoint["fallback"]
            assert isinstance(primary, str)
            assert isinstance(fallback, str)
            assert station_id in primary
            assert station_id in fallback
            assert primary != fallback
            endpoints.extend((primary, fallback))

    assert len(endpoints) == len(set(endpoints))
    assert len(listener_endpoints) == len(set(listener_endpoints))


def test_deployment_contract_reserves_shared_ai_and_public_sync_ownership_boundaries() -> None:
    contract = _read_json(DEPLOYMENT_CONTRACT)
    services = contract["services"]
    assert isinstance(services, dict)

    shared_ai = services["RadioTEDU.SharedAI"]
    public_sync = services["RadioTEDU.PublicSync"]
    assert isinstance(shared_ai, dict)
    assert isinstance(public_sync, dict)

    assert shared_ai["owns"] == ["ollama", "qwen", "model_leases"]
    assert shared_ai["station_database"] is None
    assert shared_ai["playout"] is False
    assert public_sync["database"] == "data/public-sync/public-sync.db"
    assert public_sync["direction"] == "outbound-only"
    assert public_sync["can_control_playout"] is False
