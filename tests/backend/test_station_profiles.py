from dataclasses import FrozenInstanceError

import pytest

from backend.stations.models import AudioProfile, PublicProfile, RuntimeProfile, StationProfile


def make_profile(station_id: str = "radiotedu-en") -> StationProfile:
    return StationProfile(
        profile_version=1,
        station_id=station_id,
        display_name="RadioTEDU",
        language="en",
        locale="en-US",
        timezone="Europe/Istanbul",
        public=PublicProfile(
            route="/ai/en",
            compatibility_routes=("/ai",),
            snapshot_endpoint=f"/api/public/stations/{station_id}/snapshot",
            status_endpoint=f"/api/public/stations/{station_id}/status",
            stream_url=f"https://radiotedu.com:8001/{station_id}",
        ),
        audio=AudioProfile(f"/{station_id}", -16, -1, 5),
        runtime=RuntimeProfile(
            f"data/stations/{station_id}",
            f"data/stations/{station_id}/radio.db",
            f"media/stations/{station_id}/music",
            f"data/stations/{station_id}/announcements",
            f"data/stations/{station_id}/qwen-cache",
            f"data/stations/{station_id}/logs",
        ),
        voice_pack=f"{station_id}-voices-v1",
        snapshot_secret_ref="RADIOTEDU_EN_SNAPSHOT_SECRET",
    )


def test_station_profile_is_nested_and_immutable() -> None:
    profile = make_profile()
    assert profile.public.compatibility_routes == ("/ai",)
    assert profile.audio.minimum_qwen_buffer == 5
    with pytest.raises(FrozenInstanceError):
        profile.display_name = "changed"  # type: ignore[misc]
