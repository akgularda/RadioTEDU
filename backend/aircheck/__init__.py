"""Persistence for recorded station aircheck analysis results.

This package does not capture or measure live audio. A caller supplies metadata
and results produced by an external analyzer, which are retained for later
qualification review.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath

from backend.database import apply_migrations, now_iso

_AIRCHECK_RETENTION_DAYS = 14
_HOUR = timedelta(hours=1)
_LOUDNESS_MIN_LUFS = -17.0
_LOUDNESS_MAX_LUFS = -15.0
_TRUE_PEAK_CEILING_DBTP = -1.0
_SILENCE_LIMIT_SECONDS = 2.0


@dataclass(frozen=True)
class AircheckMetadata:
    """Identity and frozen encoding metadata for one hourly aircheck file."""

    window_start: datetime
    window_end: datetime
    file_relative_path: str
    file_checksum: str
    codec: str
    bitrate_kbps: int
    channels: int


@dataclass(frozen=True)
class RecordedAircheckAnalysis:
    """Values supplied by an external analyzer; this module does not measure audio."""

    loudness_lufs: float
    true_peak_dbtp: float
    silence_seconds: float
    clipping_count: int
    transition_count: int
    analyzer_version: str


@dataclass(frozen=True)
class AircheckReport:
    station_id: str
    metadata: AircheckMetadata
    analysis: RecordedAircheckAnalysis
    result: str


@dataclass(frozen=True)
class DailyAircheckSummary:
    station_id: str
    day: date
    hourly_report_count: int
    qualified_report_count: int
    loudness_lufs: float | None
    true_peak_dbtp: float | None
    silence_seconds: float | None
    result: str


def create_aircheck_schema(conn: sqlite3.Connection) -> None:
    """Apply the versioned schema that stores station-scoped aircheck reports."""

    apply_migrations(conn)


def record_hourly_aircheck(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    metadata: AircheckMetadata,
    analysis: RecordedAircheckAnalysis,
) -> AircheckReport:
    """Persist supplied hourly analyzer results; it never reads or measures audio files."""

    _validate_station_id(station_id)
    _validate_metadata(metadata)
    _validate_analysis(analysis)
    result = _analysis_result(analysis)
    conn.execute(
        """
        insert into aircheck_reports(
            station_id, window_start, window_end, file_relative_path, file_checksum,
            codec, bitrate_kbps, channels, loudness_lufs, true_peak_dbtp,
            silence_seconds, clipping_count, transition_count, result,
            analyzer_version, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            station_id,
            _utc_iso(metadata.window_start),
            _utc_iso(metadata.window_end),
            metadata.file_relative_path,
            metadata.file_checksum,
            metadata.codec.casefold(),
            metadata.bitrate_kbps,
            metadata.channels,
            analysis.loudness_lufs,
            analysis.true_peak_dbtp,
            analysis.silence_seconds,
            analysis.clipping_count,
            analysis.transition_count,
            result,
            analysis.analyzer_version,
            now_iso(),
        ),
    )
    return AircheckReport(
        station_id=station_id,
        metadata=metadata,
        analysis=analysis,
        result=result,
    )


def prune_expired_airchecks(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    now: datetime,
    retention_days: int = _AIRCHECK_RETENTION_DAYS,
) -> int:
    """Delete reports older than the station's 14-day rolling retention window."""

    _validate_station_id(station_id)
    if retention_days != _AIRCHECK_RETENTION_DAYS:
        raise ValueError("aircheck retention is fixed at 14 days")
    cutoff = _utc_iso(now - timedelta(days=retention_days))
    cursor = conn.execute(
        "delete from aircheck_reports where station_id = ? and window_end < ?",
        (station_id, cutoff),
    )
    return cursor.rowcount


def daily_summary(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    day: date,
) -> DailyAircheckSummary:
    """Aggregate a station's persisted hourly results for one UTC calendar day."""

    _validate_station_id(station_id)
    row = conn.execute(
        """
        select
            count(*) as hourly_report_count,
            sum(case when result = 'qualified' then 1 else 0 end) as qualified_report_count,
            avg(loudness_lufs) as loudness_lufs,
            max(true_peak_dbtp) as true_peak_dbtp,
            max(silence_seconds) as silence_seconds
        from aircheck_reports
        where station_id = ? and substr(window_start, 1, 10) = ?
        """,
        (station_id, day.isoformat()),
    ).fetchone()
    assert row is not None
    report_count = int(row[0])
    qualified_count = int(row[1] or 0)
    return DailyAircheckSummary(
        station_id=station_id,
        day=day,
        hourly_report_count=report_count,
        qualified_report_count=qualified_count,
        loudness_lufs=None if row[2] is None else float(row[2]),
        true_peak_dbtp=None if row[3] is None else float(row[3]),
        silence_seconds=None if row[4] is None else float(row[4]),
        result="qualified" if report_count and report_count == qualified_count else "review_required",
    )


def _validate_station_id(station_id: str) -> None:
    if not station_id.strip():
        raise ValueError("station_id is required")


def _validate_metadata(metadata: AircheckMetadata) -> None:
    if metadata.codec.casefold() != "aac" or metadata.bitrate_kbps != 64 or metadata.channels != 2:
        raise ValueError("airchecks must be 64 kbps stereo AAC")
    if not metadata.file_checksum.strip():
        raise ValueError("aircheck checksum is required")
    path = PurePosixPath(metadata.file_relative_path)
    if path.is_absolute() or ".." in path.parts or not metadata.file_relative_path.strip():
        raise ValueError("aircheck path must be relative")
    _require_utc(metadata.window_start, "window_start")
    _require_utc(metadata.window_end, "window_end")
    if metadata.window_end - metadata.window_start != _HOUR:
        raise ValueError("aircheck analysis window must be exactly one hour")


def _validate_analysis(analysis: RecordedAircheckAnalysis) -> None:
    if analysis.silence_seconds < 0:
        raise ValueError("silence_seconds cannot be negative")
    if analysis.clipping_count < 0 or analysis.transition_count < 0:
        raise ValueError("analysis counts cannot be negative")
    if not analysis.analyzer_version.strip():
        raise ValueError("analyzer_version is required")


def _analysis_result(analysis: RecordedAircheckAnalysis) -> str:
    if (
        _LOUDNESS_MIN_LUFS <= analysis.loudness_lufs <= _LOUDNESS_MAX_LUFS
        and analysis.true_peak_dbtp <= _TRUE_PEAK_CEILING_DBTP
        and analysis.silence_seconds <= _SILENCE_LIMIT_SECONDS
        and analysis.clipping_count == 0
    ):
        return "qualified"
    return "review_required"


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _utc_iso(value: datetime) -> str:
    _require_utc(value, "timestamp")
    return value.astimezone(UTC).isoformat()
