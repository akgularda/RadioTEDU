"""Pure, station-scoped music separation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TrackCandidate:
    """A catalog track offered to one station's deterministic selector."""

    station_id: str
    track_id: str
    title: str
    artist: str
    album: str | None
    checksum_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PlayedTrack:
    """One historical play used to enforce station-local cooldowns."""

    station_id: str
    track_id: str
    title: str
    artist: str
    album: str | None
    played_at: datetime
    checksum_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SeparationPolicy:
    """Cooldown configuration for music rotation without constraint relaxation."""

    title_cooldown: timedelta = timedelta(hours=3)
    artist_cooldown: timedelta = timedelta(hours=2)
    album_cooldown: timedelta = timedelta(hours=4)
    track_cooldown: timedelta = timedelta(hours=5)

    def __post_init__(self) -> None:
        for name in (
            "title_cooldown",
            "artist_cooldown",
            "album_cooldown",
            "track_cooldown",
        ):
            if getattr(self, name) < timedelta(0):
                raise ValueError(f"{name} cannot be negative")

    def select(
        self,
        station_id: str,
        candidates: Iterable[TrackCandidate],
        history: Iterable[PlayedTrack],
        *,
        now: datetime,
    ) -> TrackCandidate | None:
        """Return the first safe local candidate, or ``None`` when none is safe."""

        local_history = tuple(play for play in history if play.station_id == station_id)
        safe_candidates = _deduplicate_tracks(
            candidate for candidate in candidates if candidate.station_id == station_id
        )
        for candidate in safe_candidates:
            if not self._is_on_cooldown(candidate, local_history, now):
                return candidate
        return None

    def _is_on_cooldown(
        self,
        candidate: TrackCandidate,
        history: Iterable[PlayedTrack],
        now: datetime,
    ) -> bool:
        title = _normalise(candidate.title)
        artist = _normalise(candidate.artist)
        album = _normalise(candidate.album)
        for play in history:
            if _within_window(play.played_at, now, self.track_cooldown) and _same_track(
                candidate, play
            ):
                return True
            if _within_window(play.played_at, now, self.title_cooldown) and title == _normalise(
                play.title
            ):
                return True
            if _within_window(play.played_at, now, self.artist_cooldown) and artist == _normalise(
                play.artist
            ):
                return True
            if (
                album is not None
                and _within_window(play.played_at, now, self.album_cooldown)
                and album == _normalise(play.album)
            ):
                return True
        return False


def _deduplicate_tracks(candidates: Iterable[TrackCandidate]) -> tuple[TrackCandidate, ...]:
    """Keep one checksum-equivalent candidate so copied files do not add weight."""

    unique: dict[tuple[str, str], TrackCandidate] = {}
    for candidate in candidates:
        identity = _track_identity(candidate.track_id, candidate.checksum_sha256)
        existing = unique.get(identity)
        if existing is None or _track_sort_key(candidate) < _track_sort_key(existing):
            unique[identity] = candidate
    return tuple(sorted(unique.values(), key=_track_sort_key))


def _same_track(candidate: TrackCandidate, play: PlayedTrack) -> bool:
    if candidate.track_id == play.track_id:
        return True
    return (
        candidate.checksum_sha256 is not None
        and play.checksum_sha256 is not None
        and candidate.checksum_sha256 == play.checksum_sha256
    )


def _track_identity(track_id: str, checksum_sha256: str | None) -> tuple[str, str]:
    return ("checksum", checksum_sha256) if checksum_sha256 is not None else ("track", track_id)


def _track_sort_key(candidate: TrackCandidate) -> tuple[str, str, str, str]:
    return (
        candidate.track_id,
        _normalise(candidate.title) or "",
        _normalise(candidate.artist) or "",
        _normalise(candidate.album) or "",
    )


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = " ".join(value.split()).casefold()
    return normalised or None


def _within_window(played_at: datetime, now: datetime, window: timedelta) -> bool:
    return window > timedelta(0) and now - played_at < window
