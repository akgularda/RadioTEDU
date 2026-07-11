"""Deterministic, station-scoped imaging rotation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from backend.imaging.library import ImagingAsset


@dataclass(frozen=True, slots=True)
class ImagingPlay:
    """One historical imaging play used to choose the next asset safely."""

    station_id: str
    category: str
    checksum_sha256: str
    played_at: datetime


@dataclass(frozen=True, slots=True)
class ImagingRotationPolicy:
    """Cycle configured categories and keep each content hash outside its reuse window."""

    category_order: tuple[str, ...] = ()
    asset_reuse_windows: Mapping[str, timedelta] = field(default_factory=dict)
    default_asset_reuse_window: timedelta = timedelta(minutes=90)

    def __post_init__(self) -> None:
        if self.default_asset_reuse_window < timedelta(0):
            raise ValueError("default_asset_reuse_window cannot be negative")
        if len(self.category_order) != len(set(self.category_order)):
            raise ValueError("category_order cannot contain duplicates")
        if any(not category for category in self.category_order):
            raise ValueError("category_order cannot contain empty categories")
        for category, window in self.asset_reuse_windows.items():
            if not category or window < timedelta(0):
                raise ValueError("asset reuse windows require categories and non-negative durations")

    def select(
        self,
        station_id: str,
        assets: Iterable[ImagingAsset],
        history: Iterable[ImagingPlay],
        *,
        now: datetime,
    ) -> ImagingAsset | None:
        """Return a safe next asset, or ``None`` instead of repeating content."""

        local_history = tuple(play for play in history if play.station_id == station_id)
        candidates_by_category: dict[str, list[ImagingAsset]] = {}
        for asset in _deduplicate_assets(
            asset for asset in assets if asset.station_id == station_id
        ):
            if not self._recently_used(asset, local_history, now):
                candidates_by_category.setdefault(asset.category, []).append(asset)

        for category in self._rotated_categories(candidates_by_category, local_history):
            return min(
                candidates_by_category[category],
                key=lambda asset: _asset_sort_key(asset, local_history),
            )
        return None

    def _recently_used(
        self, asset: ImagingAsset, history: Iterable[ImagingPlay], now: datetime
    ) -> bool:
        window = self.asset_reuse_windows.get(asset.category, self.default_asset_reuse_window)
        return any(
            play.checksum_sha256 == asset.checksum_sha256
            and _within_window(play.played_at, now, window)
            for play in history
        )

    def _rotated_categories(
        self,
        candidates_by_category: Mapping[str, list[ImagingAsset]],
        history: Iterable[ImagingPlay],
    ) -> tuple[str, ...]:
        available = set(candidates_by_category)
        ordered = tuple(category for category in self.category_order if category in available)
        ordered += tuple(sorted(available.difference(ordered)))
        if not ordered:
            return ()
        last_category = _last_category(history)
        if last_category not in ordered:
            return ordered
        start = (ordered.index(last_category) + 1) % len(ordered)
        return ordered[start:] + ordered[:start]


def _deduplicate_assets(assets: Iterable[ImagingAsset]) -> tuple[ImagingAsset, ...]:
    """Collapse identical render hashes before they can influence rotation weight."""

    unique: dict[str, ImagingAsset] = {}
    for asset in assets:
        existing = unique.get(asset.checksum_sha256)
        if existing is None or _asset_identity_key(asset) < _asset_identity_key(existing):
            unique[asset.checksum_sha256] = asset
    return tuple(sorted(unique.values(), key=_asset_identity_key))


def _asset_sort_key(
    asset: ImagingAsset, history: Iterable[ImagingPlay]
) -> tuple[bool, datetime, str, str]:
    prior_plays = [
        play.played_at for play in history if play.checksum_sha256 == asset.checksum_sha256
    ]
    if not prior_plays:
        return (False, datetime.min, asset.checksum_sha256, asset.relative_path.as_posix())
    return (True, min(prior_plays), asset.checksum_sha256, asset.relative_path.as_posix())


def _asset_identity_key(asset: ImagingAsset) -> tuple[str, str, str]:
    return asset.category, asset.checksum_sha256, asset.relative_path.as_posix()


def _last_category(history: Iterable[ImagingPlay]) -> str | None:
    plays = tuple(history)
    if not plays:
        return None
    return max(plays, key=lambda play: (play.played_at, play.category)).category


def _within_window(played_at: datetime, now: datetime, window: timedelta) -> bool:
    return window > timedelta(0) and now - played_at < window
