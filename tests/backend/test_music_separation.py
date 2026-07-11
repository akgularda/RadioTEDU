from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.programming.separation import PlayedTrack, SeparationPolicy, TrackCandidate


NOW = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)


def candidate(
    track_id: str,
    *,
    title: str = "Different title",
    artist: str = "Different artist",
    album: str | None = "Different album",
    checksum: str | None = None,
    station_id: str = "radiotedu-en",
) -> TrackCandidate:
    return TrackCandidate(station_id, track_id, title, artist, album, checksum)


def played(
    track_id: str,
    *,
    title: str = "Previous title",
    artist: str = "Previous artist",
    album: str | None = "Previous album",
    checksum: str | None = None,
    station_id: str = "radiotedu-en",
    minutes_ago: int = 30,
) -> PlayedTrack:
    return PlayedTrack(
        station_id,
        track_id,
        title,
        artist,
        album,
        NOW - timedelta(minutes=minutes_ago),
        checksum,
    )


def test_separation_refuses_every_active_track_title_artist_and_album_repeat() -> None:
    policy = SeparationPolicy()
    history = (
        played("played-track", checksum="a" * 64),
        played("played-title", title="Shared title", minutes_ago=60),
        played("played-artist", artist="Shared artist", minutes_ago=60),
        played("played-album", album="Shared album", minutes_ago=60),
    )
    candidates = (
        candidate("copy", checksum="a" * 64),
        candidate("new-title", title="Shared title"),
        candidate("new-artist", artist="Shared artist"),
        candidate("new-album", album="Shared album"),
    )

    assert policy.select("radiotedu-en", candidates, history, now=NOW) is None


def test_separation_is_station_local_and_deterministically_chooses_safe_track() -> None:
    policy = SeparationPolicy()
    safe = candidate("a-safe")
    blocked = candidate("z-blocked", title="Recent title")
    history = (
        played("other-station", title="Different title", station_id="radiotedu-fr"),
        played("local-history", title="Recent title"),
    )

    first = policy.select("radiotedu-en", (blocked, safe), history, now=NOW)
    second = policy.select("radiotedu-en", (safe, blocked), history, now=NOW)

    assert first == safe
    assert second == safe
