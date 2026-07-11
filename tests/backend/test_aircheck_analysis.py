from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from backend.aircheck import (
    AircheckMetadata,
    RecordedAircheckAnalysis,
    create_aircheck_schema,
    daily_summary,
    prune_expired_airchecks,
    record_hourly_aircheck,
)


def _metadata(*, window_start: datetime, suffix: str = "01") -> AircheckMetadata:
    return AircheckMetadata(
        window_start=window_start,
        window_end=window_start + timedelta(hours=1),
        file_relative_path=f"airchecks/{suffix}.aac",
        file_checksum=f"checksum-{suffix}",
        codec="aac",
        bitrate_kbps=64,
        channels=2,
    )


def _recorded_analysis(
    *, loudness_lufs: float = -16.0, true_peak_dbtp: float = -1.0, silence_seconds: float = 0.25
) -> RecordedAircheckAnalysis:
    return RecordedAircheckAnalysis(
        loudness_lufs=loudness_lufs,
        true_peak_dbtp=true_peak_dbtp,
        silence_seconds=silence_seconds,
        clipping_count=0,
        transition_count=3,
        analyzer_version="aircheck-v1",
    )


def test_records_station_scoped_hourly_aac_aircheck_with_supplied_analysis_results() -> None:
    conn = sqlite3.connect(":memory:")
    create_aircheck_schema(conn)
    window_start = datetime(2026, 7, 11, 10, tzinfo=UTC)

    report = record_hourly_aircheck(
        conn,
        station_id="radiotedu-en",
        metadata=_metadata(window_start=window_start),
        analysis=_recorded_analysis(),
    )

    assert report.station_id == "radiotedu-en"
    assert report.metadata.codec == "aac"
    assert report.metadata.bitrate_kbps == 64
    assert report.metadata.channels == 2
    assert report.analysis.loudness_lufs == -16.0
    assert report.analysis.true_peak_dbtp == -1.0
    assert report.analysis.silence_seconds == 0.25
    assert report.result == "qualified"
    stored = conn.execute(
        "select station_id, codec, bitrate_kbps, channels, loudness_lufs, true_peak_dbtp, "
        "silence_seconds, result from aircheck_reports"
    ).fetchone()
    assert stored == ("radiotedu-en", "aac", 64, 2, -16.0, -1.0, 0.25, "qualified")


def test_rejects_non_compliant_aircheck_metadata_before_persisting() -> None:
    conn = sqlite3.connect(":memory:")
    create_aircheck_schema(conn)
    window_start = datetime(2026, 7, 11, 10, tzinfo=UTC)

    with pytest.raises(ValueError, match="64 kbps stereo AAC"):
        record_hourly_aircheck(
            conn,
            station_id="radiotedu-en",
            metadata=AircheckMetadata(
                window_start=window_start,
                window_end=window_start + timedelta(hours=1),
                file_relative_path="airchecks/invalid.mp3",
                file_checksum="checksum-invalid",
                codec="mp3",
                bitrate_kbps=128,
                channels=2,
            ),
            analysis=_recorded_analysis(),
        )

    assert conn.execute("select count(*) from aircheck_reports").fetchone() == (0,)


def test_retains_fourteen_days_per_station_and_summarizes_recorded_daily_results() -> None:
    conn = sqlite3.connect(":memory:")
    create_aircheck_schema(conn)
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    daily_start = datetime(2026, 7, 14, 9, tzinfo=UTC)
    record_hourly_aircheck(
        conn,
        station_id="radiotedu-en",
        metadata=_metadata(window_start=now - timedelta(days=15), suffix="expired"),
        analysis=_recorded_analysis(),
    )
    record_hourly_aircheck(
        conn,
        station_id="radiotedu-en",
        metadata=_metadata(window_start=daily_start, suffix="first"),
        analysis=_recorded_analysis(),
    )
    record_hourly_aircheck(
        conn,
        station_id="radiotedu-en",
        metadata=_metadata(window_start=daily_start + timedelta(hours=1), suffix="second"),
        analysis=_recorded_analysis(loudness_lufs=-17.5, true_peak_dbtp=-0.5, silence_seconds=2.1),
    )
    record_hourly_aircheck(
        conn,
        station_id="radiotedu-fr",
        metadata=_metadata(window_start=now - timedelta(days=15), suffix="fr-expired"),
        analysis=_recorded_analysis(),
    )

    removed = prune_expired_airchecks(conn, station_id="radiotedu-en", now=now)
    summary = daily_summary(conn, station_id="radiotedu-en", day=daily_start.date())

    assert removed == 1
    assert summary.hourly_report_count == 2
    assert summary.qualified_report_count == 1
    assert summary.loudness_lufs == -16.75
    assert summary.true_peak_dbtp == -0.5
    assert summary.silence_seconds == 2.1
    assert summary.result == "review_required"
    assert conn.execute(
        "select count(*) from aircheck_reports where station_id = 'radiotedu-fr'"
    ).fetchone() == (1,)
