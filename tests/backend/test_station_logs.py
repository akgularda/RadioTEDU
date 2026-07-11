from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePosixPath

from backend.audio.segue_policy import CueMetadata, Genre, MediaKind, SegueItem
from backend.imaging.library import ImagingAsset
from backend.programming.clocks import ClockPosition, ProgramClock
from backend.programming.logs import (
    ImagingLogCandidate,
    MusicLogCandidate,
    SevenDayLogGenerator,
    SevenDayLogValidator,
)
from backend.programming.rotation import ImagingRotationPolicy
from backend.programming.separation import SeparationPolicy, TrackCandidate
from backend.scheduler import generate_station_qualification_log


FIRST_BOUNDARY = datetime(2026, 7, 11, 10, tzinfo=timezone.utc)


def clock() -> ProgramClock:
    return ProgramClock(
        clock_id="morning-v1",
        station_id="radiotedu-en",
        name="Morning",
        daypart="morning",
        timezone_name="Europe/Istanbul",
        version=1,
        effective_from=date(2026, 7, 1),
        effective_until=None,
        active=True,
        checksum="a" * 64,
        positions=(
            ClockPosition(1, 0, "music", "current", "soft", 30, {}),
            ClockPosition(2, 180, "imaging", "station-id", "hard", 2, {}),
        ),
    )


def music_candidate(number: int) -> MusicLogCandidate:
    track = TrackCandidate(
        "radiotedu-en",
        f"track-{number}",
        f"Title {number}",
        f"Artist {number}",
        f"Album {number}",
        f"{number:064x}",
    )
    item = SegueItem(
        MediaKind.MUSIC,
        180,
        Genre.POP,
        CueMetadata(0, 180, 5, 0.95, True),
    )
    return MusicLogCandidate(track.track_id, track, item)


def imaging_candidate(letter: str, category: str) -> ImagingLogCandidate:
    checksum = letter * 64
    asset = ImagingAsset(
        "radiotedu-en",
        "en",
        category,
        8,
        checksum,
        PurePosixPath("assets", f"{checksum}.mp3"),
    )
    return ImagingLogCandidate(
        f"{category}-{letter}", asset, SegueItem(MediaKind.FULL_JINGLE, 8)
    )


def build_log():
    return SevenDayLogGenerator(
        rotation_policy=ImagingRotationPolicy(category_order=("jingle", "program-promo"))
    ).generate(
        "radiotedu-en",
        clock(),
        FIRST_BOUNDARY,
        tuple(music_candidate(number) for number in range(1, 8)),
        (imaging_candidate("a", "jingle"), imaging_candidate("b", "program-promo")),
    )


def test_seven_day_log_is_reproducible_simulated_and_qualified_by_all_policies() -> None:
    first = build_log()
    second = build_log()

    assert first.simulated is True
    assert first.fingerprint == second.fingerprint
    assert [block.daypart for block in first.blocks] == ["morning"] * 7
    assert SevenDayLogValidator().validate(first) == ()


def test_seven_day_log_validator_explains_a_track_rotation_violation() -> None:
    log = build_log()
    repeated_track = replace(log.blocks[1], music=log.blocks[0].music)
    invalid_log = replace(log, blocks=(log.blocks[0], repeated_track, *log.blocks[2:]))

    violations = SevenDayLogValidator().validate(invalid_log)

    assert any("separation" in violation for violation in violations)


def test_seven_day_log_validator_does_not_allow_a_weakened_title_policy() -> None:
    log = build_log()
    invalid_log = replace(
        log,
        separation_policy=SeparationPolicy(title_cooldown=timedelta(0)),
    )

    violations = SevenDayLogValidator().validate(invalid_log)

    assert any("seven-day" in violation for violation in violations)


def test_scheduler_generates_only_the_requested_station_qualification_log() -> None:
    generator = SevenDayLogGenerator(
        rotation_policy=ImagingRotationPolicy(category_order=("jingle", "program-promo"))
    )

    log = generate_station_qualification_log(
        "radiotedu-en",
        clock(),
        FIRST_BOUNDARY,
        tuple(music_candidate(number) for number in range(1, 8)),
        (imaging_candidate("a", "jingle"), imaging_candidate("b", "program-promo")),
        generator=generator,
    )

    assert log.station_id == "radiotedu-en"
    assert SevenDayLogValidator().validate(log) == ()
