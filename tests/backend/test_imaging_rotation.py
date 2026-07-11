from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from backend.imaging.library import ImagingAsset
from backend.programming.rotation import ImagingPlay, ImagingRotationPolicy


NOW = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)


def asset(
    checksum: str,
    category: str,
    *,
    station_id: str = "radiotedu-en",
) -> ImagingAsset:
    return ImagingAsset(
        station_id=station_id,
        language="en" if station_id == "radiotedu-en" else "fr",
        category=category,
        duration_seconds=4.0,
        checksum_sha256=checksum,
        relative_path=PurePosixPath("assets", f"{checksum}.mp3"),
    )


def play(
    checksum: str,
    category: str,
    *,
    station_id: str = "radiotedu-en",
    minutes_ago: int = 20,
) -> ImagingPlay:
    return ImagingPlay(station_id, category, checksum, NOW - timedelta(minutes=minutes_ago))


def test_rotation_advances_category_and_ignores_duplicate_render_weight() -> None:
    policy = ImagingRotationPolicy(category_order=("jingle", "program-promo"))
    promo = asset("b" * 64, "program-promo")
    jingle = asset("c" * 64, "jingle")
    duplicate_jingle = asset("c" * 64, "jingle")

    selected = policy.select(
        "radiotedu-en",
        (jingle, duplicate_jingle, promo),
        (play("a" * 64, "jingle"),),
        now=NOW,
    )

    assert selected == promo


def test_rotation_never_reuses_local_asset_inside_window_but_keeps_stations_isolated() -> None:
    policy = ImagingRotationPolicy(default_asset_reuse_window=timedelta(minutes=90))
    recent = asset("d" * 64, "jingle")
    french_only = asset("e" * 64, "jingle", station_id="radiotedu-fr")
    history = (
        play("d" * 64, "jingle"),
        play("e" * 64, "jingle", station_id="radiotedu-fr"),
    )

    assert policy.select("radiotedu-en", (recent, french_only), history, now=NOW) is None
