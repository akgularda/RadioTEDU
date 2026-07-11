"""Pure, reproducible seven-day qualification logs for one station."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Iterable

from backend.audio.segue_policy import SegueItem
from backend.imaging.library import ImagingAsset
from backend.programming.backtiming import Backtimer, BacktimingCandidate, BacktimingPlan
from backend.programming.clocks import ClockPosition, ProgramClock
from backend.programming.rotation import ImagingPlay, ImagingRotationPolicy
from backend.programming.separation import PlayedTrack, SeparationPolicy, TrackCandidate


SEVEN_DAYS = timedelta(days=7)


class StationLogError(ValueError):
    """Raised when a qualification log cannot be generated safely."""


@dataclass(frozen=True, slots=True)
class MusicLogCandidate:
    """A selectable music track and its measured playout facts."""

    item_id: str
    track: TrackCandidate
    segue_item: SegueItem

    def __post_init__(self) -> None:
        if not self.item_id or self.segue_item.duration_seconds <= 0:
            raise StationLogError("music log candidates require an id and positive duration")


@dataclass(frozen=True, slots=True)
class ImagingLogCandidate:
    """A selectable imaging asset and its measured playout facts."""

    item_id: str
    asset: ImagingAsset
    segue_item: SegueItem

    def __post_init__(self) -> None:
        if not self.item_id or self.segue_item.duration_seconds <= 0:
            raise StationLogError("imaging log candidates require an id and positive duration")


@dataclass(frozen=True, slots=True)
class StationLogBlock:
    """One simulated daypart boundary with its policy-selected items."""

    station_id: str
    daypart: str
    clock: ProgramClock
    boundary_at: datetime
    music: MusicLogCandidate
    imaging: ImagingLogCandidate
    plan: BacktimingPlan


@dataclass(frozen=True, slots=True)
class SevenDayStationLog:
    """A deterministic fixture, not evidence of seven days of live playout."""

    station_id: str
    simulated: bool
    music_candidates: tuple[MusicLogCandidate, ...]
    imaging_candidates: tuple[ImagingLogCandidate, ...]
    separation_policy: SeparationPolicy
    rotation_policy: ImagingRotationPolicy
    blocks: tuple[StationLogBlock, ...]

    @property
    def fingerprint(self) -> str:
        """Return a stable fingerprint suitable for reproducibility evidence."""

        payload = {
            "station_id": self.station_id,
            "simulated": self.simulated,
            "blocks": [
                {
                    "daypart": block.daypart,
                    "clock_id": block.clock.clock_id,
                    "boundary_at": block.boundary_at.isoformat(),
                    "music": block.music.track.track_id,
                    "imaging": block.imaging.asset.checksum_sha256,
                    "items": [
                        {
                            "item_id": item.candidate.item_id,
                            "start_at": item.start_at.isoformat(),
                            "end_at": item.end_at.isoformat(),
                            "transition": item.transition.kind,
                        }
                        for item in block.plan.items
                    ],
                }
                for block in self.blocks
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()


class SevenDayLogGenerator:
    """Generate exactly seven station-local daily daypart log blocks."""

    def __init__(
        self,
        *,
        backtimer: Backtimer | None = None,
        separation_policy: SeparationPolicy | None = None,
        rotation_policy: ImagingRotationPolicy | None = None,
    ) -> None:
        self._backtimer = backtimer or Backtimer()
        self._separation_policy = _seven_day_title_policy(separation_policy or SeparationPolicy())
        self._rotation_policy = rotation_policy or ImagingRotationPolicy()

    def generate(
        self,
        station_id: str,
        clock: ProgramClock,
        first_boundary_at: datetime,
        music_candidates: Iterable[MusicLogCandidate],
        imaging_candidates: Iterable[ImagingLogCandidate],
    ) -> SevenDayStationLog:
        """Create a reproducible seven-day fixture from fixed inventories only."""

        if not station_id or clock.station_id != station_id:
            raise StationLogError("station log clock must belong to the requested station")
        if first_boundary_at.tzinfo is None or first_boundary_at.utcoffset() is None:
            raise StationLogError("station log boundaries must be timezone-aware")

        music = tuple(sorted(music_candidates, key=lambda candidate: candidate.item_id))
        imaging = tuple(sorted(imaging_candidates, key=lambda candidate: candidate.item_id))
        self._validate_inventory(station_id, music, imaging)
        music_position = _clock_position(clock, "music")
        imaging_position = _clock_position(clock, "imaging")

        played_tracks: list[PlayedTrack] = []
        played_imaging: list[ImagingPlay] = []
        blocks: list[StationLogBlock] = []
        for day in range(7):
            boundary_at = first_boundary_at + timedelta(days=day)
            selected_track = self._separation_policy.select(
                station_id,
                (candidate.track for candidate in music),
                played_tracks,
                now=boundary_at,
            )
            selected_imaging = self._rotation_policy.select(
                station_id,
                (candidate.asset for candidate in imaging),
                played_imaging,
                now=boundary_at,
            )
            if selected_track is None:
                raise StationLogError("music inventory cannot satisfy seven-day separation")
            if selected_imaging is None:
                raise StationLogError("imaging inventory cannot satisfy rotation")

            music_candidate = _music_candidate_for(music, selected_track)
            imaging_candidate = _imaging_candidate_for(imaging, selected_imaging)
            plan = self._backtimer.plan(
                station_id,
                clock,
                boundary_at,
                (
                    BacktimingCandidate(
                        music_candidate.item_id,
                        station_id,
                        music_candidate.segue_item,
                        music_position,
                    ),
                    BacktimingCandidate(
                        imaging_candidate.item_id,
                        station_id,
                        imaging_candidate.segue_item,
                        imaging_position,
                    ),
                ),
            )
            block = StationLogBlock(
                station_id,
                clock.daypart,
                clock,
                boundary_at,
                music_candidate,
                imaging_candidate,
                plan,
            )
            blocks.append(block)
            played_tracks.append(
                PlayedTrack(
                    station_id,
                    selected_track.track_id,
                    selected_track.title,
                    selected_track.artist,
                    selected_track.album,
                    plan.items[0].start_at,
                    selected_track.checksum_sha256,
                )
            )
            played_imaging.append(
                ImagingPlay(
                    station_id,
                    selected_imaging.category,
                    selected_imaging.checksum_sha256,
                    plan.items[1].start_at,
                )
            )

        return SevenDayStationLog(
            station_id,
            True,
            music,
            imaging,
            self._separation_policy,
            self._rotation_policy,
            tuple(blocks),
        )

    @staticmethod
    def _validate_inventory(
        station_id: str,
        music: tuple[MusicLogCandidate, ...],
        imaging: tuple[ImagingLogCandidate, ...],
    ) -> None:
        if not music or not imaging:
            raise StationLogError("station logs require music and imaging inventories")
        if any(candidate.track.station_id != station_id for candidate in music):
            raise StationLogError("music inventory must be station-local")
        if any(candidate.asset.station_id != station_id for candidate in imaging):
            raise StationLogError("imaging inventory must be station-local")


class SevenDayLogValidator:
    """Explain failed daypart, separation, rotation, and backtiming checks."""

    def validate(self, log: SevenDayStationLog) -> tuple[str, ...]:
        violations: list[str] = []
        if not log.simulated:
            violations.append("qualification logs must be simulated fixtures, not live-run evidence")
        if len(log.blocks) != 7:
            violations.append("qualification log must contain exactly seven daily blocks")
        if log.separation_policy.title_cooldown < SEVEN_DAYS:
            violations.append("title separation cannot be weaker than the frozen seven-day window")
        separation_policy = _seven_day_title_policy(log.separation_policy)

        track_history: list[PlayedTrack] = []
        imaging_history: list[ImagingPlay] = []
        previous_boundary: datetime | None = None
        for index, block in enumerate(log.blocks):
            if block.station_id != log.station_id or block.clock.station_id != log.station_id:
                violations.append(f"block {index}: station isolation violated")
            if block.daypart != block.clock.daypart:
                violations.append(f"block {index}: daypart does not match its clock")
            if previous_boundary is not None and block.boundary_at - previous_boundary != timedelta(days=1):
                violations.append(f"block {index}: boundaries are not consecutive daily fixtures")
            previous_boundary = block.boundary_at
            violations.extend(_backtiming_violations(index, block))

            expected_track = separation_policy.select(
                log.station_id,
                (candidate.track for candidate in log.music_candidates),
                track_history,
                now=block.boundary_at,
            )
            if expected_track != block.music.track:
                violations.append(f"block {index}: music separation selection is not deterministic")
            else:
                track_history.append(
                    PlayedTrack(
                        log.station_id,
                        block.music.track.track_id,
                        block.music.track.title,
                        block.music.track.artist,
                        block.music.track.album,
                        block.plan.items[0].start_at,
                        block.music.track.checksum_sha256,
                    )
                )

            expected_imaging = log.rotation_policy.select(
                log.station_id,
                (candidate.asset for candidate in log.imaging_candidates),
                imaging_history,
                now=block.boundary_at,
            )
            if expected_imaging != block.imaging.asset:
                violations.append(f"block {index}: imaging rotation selection is not deterministic")
            else:
                imaging_history.append(
                    ImagingPlay(
                        log.station_id,
                        block.imaging.asset.category,
                        block.imaging.asset.checksum_sha256,
                        block.plan.items[1].start_at,
                    )
                )
        return tuple(violations)


def _seven_day_title_policy(policy: SeparationPolicy) -> SeparationPolicy:
    return SeparationPolicy(
        title_cooldown=max(policy.title_cooldown, SEVEN_DAYS),
        artist_cooldown=policy.artist_cooldown,
        album_cooldown=policy.album_cooldown,
        track_cooldown=policy.track_cooldown,
    )


def _clock_position(clock: ProgramClock, item_kind: str) -> ClockPosition:
    try:
        return next(position for position in clock.positions if position.item_kind == item_kind)
    except StopIteration as error:
        raise StationLogError(f"clock has no {item_kind} position") from error


def _music_candidate_for(
    candidates: tuple[MusicLogCandidate, ...], selected: TrackCandidate
) -> MusicLogCandidate:
    return next(candidate for candidate in candidates if candidate.track == selected)


def _imaging_candidate_for(
    candidates: tuple[ImagingLogCandidate, ...], selected: ImagingAsset
) -> ImagingLogCandidate:
    return next(candidate for candidate in candidates if candidate.asset == selected)


def _backtiming_violations(index: int, block: StationLogBlock) -> tuple[str, ...]:
    violations: list[str] = []
    plan = block.plan
    if plan.station_id != block.station_id or plan.clock_id != block.clock.clock_id:
        violations.append(f"block {index}: backtiming plan belongs to another station or clock")
    if plan.boundary_at != block.boundary_at or not plan.within_hard_boundary:
        violations.append(f"block {index}: hard boundary is outside tolerance")
    if plan.ends_at != block.boundary_at:
        violations.append(f"block {index}: plan does not finish at the requested boundary")
    if any(
        current.end_at > following.start_at
        for current, following in zip(plan.items, plan.items[1:])
    ):
        violations.append(f"block {index}: backtiming plan overlaps items")
    expected_ids = (block.music.item_id, block.imaging.item_id)
    if tuple(item.candidate.item_id for item in plan.items) != expected_ids:
        violations.append(f"block {index}: plan does not contain the selected station items")
    return tuple(violations)
