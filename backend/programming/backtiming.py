"""Deterministic, non-overlapping plans that finish on a hard clock boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from backend.audio.segue_policy import SegueDecision, SegueItem, SegueKind, SeguePolicy
from backend.programming.clocks import ClockPosition, ProgramClock


class BacktimingError(ValueError):
    """Raised when a station-local hard-boundary plan cannot be proven safe."""


@dataclass(frozen=True, slots=True)
class BacktimingCandidate:
    """One clock-position item whose measured duration may be backtimed."""

    item_id: str
    station_id: str
    segue_item: SegueItem
    clock_position: ClockPosition

    def __post_init__(self) -> None:
        if not self.item_id:
            raise BacktimingError("backtiming candidates require an item id")
        if not self.station_id:
            raise BacktimingError("backtiming candidates require a station")
        if self.segue_item.duration_seconds <= 0:
            raise BacktimingError("backtiming candidates require a positive duration")


@dataclass(frozen=True, slots=True)
class BacktimedItem:
    """A candidate placed in a no-overlap interval with its outbound segue intent."""

    candidate: BacktimingCandidate
    start_at: datetime
    end_at: datetime
    transition: SegueDecision


@dataclass(frozen=True, slots=True)
class BacktimingPlan:
    """An auditable station-local plan ending at a single hard boundary."""

    station_id: str
    clock_id: str
    boundary_at: datetime
    hard_boundary_tolerance_seconds: int
    items: tuple[BacktimedItem, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise BacktimingError("backtiming plans require at least one item")
        if any(item.candidate.station_id != self.station_id for item in self.items):
            raise BacktimingError("backtiming plans cannot mix stations")
        if any(item.start_at >= item.end_at for item in self.items):
            raise BacktimingError("backtimed items require a positive interval")
        if any(
            current.end_at > following.start_at
            for current, following in zip(self.items, self.items[1:])
        ):
            raise BacktimingError("backtiming plans cannot overlap")

    @property
    def ends_at(self) -> datetime:
        return self.items[-1].end_at

    @property
    def hard_boundary_lateness_seconds(self) -> float:
        return abs((self.ends_at - self.boundary_at).total_seconds())

    @property
    def within_hard_boundary(self) -> bool:
        return self.hard_boundary_lateness_seconds <= self.hard_boundary_tolerance_seconds


class Backtimer:
    """Backtime measured source durations without allowing an on-air overlap."""

    def __init__(
        self,
        *,
        segue_policy: SeguePolicy | None = None,
        hard_boundary_tolerance_seconds: int = 2,
    ) -> None:
        if hard_boundary_tolerance_seconds < 0:
            raise BacktimingError("hard-boundary tolerance cannot be negative")
        self._segue_policy = segue_policy or SeguePolicy()
        self._hard_boundary_tolerance_seconds = hard_boundary_tolerance_seconds

    def plan(
        self,
        station_id: str,
        clock: ProgramClock,
        boundary_at: datetime,
        candidates: Iterable[BacktimingCandidate],
    ) -> BacktimingPlan:
        """Place the supplied clock items backwards from ``boundary_at``.

        The segue policy is consulted for every item pair.  Any approved
        crossfade or talk-over is deliberately converted to a sequential
        transition because this timing phase has no playout mixer to prove an
        audible overlap safe.  That conservative fallback preserves measured
        source duration and gives the hard clock boundary an auditable result.
        """

        if not station_id:
            raise BacktimingError("backtiming requires a station")
        if clock.station_id != station_id:
            raise BacktimingError("clock belongs to another station")
        if boundary_at.tzinfo is None or boundary_at.utcoffset() is None:
            raise BacktimingError("hard boundary must be timezone-aware")

        ordered = tuple(sorted(candidates, key=lambda candidate: (candidate.clock_position.ordinal, candidate.item_id)))
        self._validate_candidates(station_id, clock, ordered)
        tolerance = self._tolerance_for(clock)

        starts_and_ends: list[tuple[datetime, datetime]] = []
        cursor = boundary_at
        for candidate in reversed(ordered):
            start_at = cursor - timedelta(seconds=candidate.segue_item.duration_seconds)
            starts_and_ends.append((start_at, cursor))
            cursor = start_at
        starts_and_ends.reverse()

        items = tuple(
            BacktimedItem(
                candidate=candidate,
                start_at=start_at,
                end_at=end_at,
                transition=self._transition(candidate, ordered[index + 1] if index + 1 < len(ordered) else None),
            )
            for index, (candidate, (start_at, end_at)) in enumerate(zip(ordered, starts_and_ends))
        )
        plan = BacktimingPlan(station_id, clock.clock_id, boundary_at, tolerance, items)
        if not plan.within_hard_boundary:
            raise BacktimingError("backtiming plan misses the hard boundary")
        return plan

    def _validate_candidates(
        self,
        station_id: str,
        clock: ProgramClock,
        candidates: tuple[BacktimingCandidate, ...],
    ) -> None:
        if not candidates:
            raise BacktimingError("backtiming requires at least one candidate")
        if any(candidate.station_id != station_id for candidate in candidates):
            raise BacktimingError("backtiming candidates must be station-local")
        if any(candidate.clock_position not in clock.positions for candidate in candidates):
            raise BacktimingError("backtiming candidate is not in the active clock")
        ordinals = [candidate.clock_position.ordinal for candidate in candidates]
        if len(ordinals) != len(set(ordinals)):
            raise BacktimingError("backtiming candidates cannot share a clock position")

    def _tolerance_for(self, clock: ProgramClock) -> int:
        hard_position_tolerances = [
            position.maximum_lateness_seconds
            for position in clock.positions
            if position.boundary_kind == "hard"
        ]
        if not hard_position_tolerances:
            raise BacktimingError("backtiming clock requires a hard boundary")
        return min(self._hard_boundary_tolerance_seconds, *hard_position_tolerances)

    def _transition(
        self,
        current: BacktimingCandidate,
        following: BacktimingCandidate | None,
    ) -> SegueDecision:
        if following is None:
            return SegueDecision(
                kind=SegueKind.SEQUENTIAL,
                reason="hard boundary follows the final item",
            )
        decision = self._segue_policy.choose(None, current.segue_item, following.segue_item)
        if decision.overlap_seconds > 0 or decision.kind is SegueKind.TALK_OVER:
            return SegueDecision(
                kind=SegueKind.SEQUENTIAL,
                time_stretch_ratio=1.0,
                speaks_over_vocals=False,
                reason=f"no overlap in deterministic backtiming: {decision.reason}",
            )
        return decision
