from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from backend.config import Settings
from backend.stations.context import (
    StationContext,
    build_station_context,
    coerce_station_context,
    english_compatibility_context,
    ensure_station_runtime_dirs,
)
from backend.stations.loader import StationProfileError, load_station_profile, load_station_profiles
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


def test_context_derives_station_scoped_settings() -> None:
    profiles = load_station_profiles("config/stations")
    settings = Settings()

    context = build_station_context(settings, profiles["radiotedu-fr"])

    assert context.profile.station_id == "radiotedu-fr"
    assert context.settings is not settings
    assert settings.database_path == "data/radiotedu.db"
    assert context.settings.database_path.endswith("data/stations/radiotedu-fr/radio.db")
    assert context.settings.liquidsoap_mount == "/radiotedu-fr"
    assert context.announcement_root != context.cache_root


def test_context_resolution_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    root = tmp_path / "radiotedu-fr"
    profile = replace(
        load_station_profiles("config/stations")["radiotedu-fr"],
        runtime=RuntimeProfile(
            str(root),
            str(root / "radio.db"),
            str(tmp_path / "media" / "radiotedu-fr"),
            str(root / "announcements"),
            str(root / "qwen-cache"),
            str(root / "logs"),
        ),
    )

    context = build_station_context(Settings(), profile)

    assert context.data_root == root.resolve()
    assert context.database_file == (root / "radio.db").resolve()
    assert context.music_root == (tmp_path / "media" / "radiotedu-fr").resolve()
    assert context.announcement_root == (root / "announcements").resolve()
    assert context.cache_root == (root / "qwen-cache").resolve()
    assert context.log_root == (root / "logs").resolve()
    assert not root.exists()
    assert not (tmp_path / "media").exists()


def test_runtime_directories_are_created_only_by_explicit_ensure(tmp_path: Path) -> None:
    root = tmp_path / "station"
    profile = replace(
        make_profile(),
        runtime=RuntimeProfile(
            str(root),
            str(root / "radio.db"),
            str(tmp_path / "music"),
            str(root / "announcements"),
            str(root / "qwen-cache"),
            str(root / "logs"),
        ),
    )
    context = build_station_context(Settings(), profile)
    assert not root.exists()

    ensure_station_runtime_dirs(context)

    assert context.data_root.is_dir()
    assert context.database_file.parent.is_dir()
    assert context.music_root.is_dir()
    assert context.announcement_root.is_dir()
    assert context.cache_root.is_dir()
    assert context.log_root.is_dir()


def test_english_compatibility_adapter_preserves_direct_settings() -> None:
    settings = Settings(
        database_path="legacy/radio.db",
        music_dir="legacy/music",
        static_dir="legacy/static",
        public_stream_url="https://example.test/legacy",
        min_ready_announcements=3,
    )

    context = english_compatibility_context(settings)

    assert context.settings is settings
    assert context.profile.station_id == "radiotedu-en"
    assert context.profile.language == "en"
    assert context.profile.locale == "en-US"
    assert context.profile.public.route == "/ai/en"
    assert context.profile.public.compatibility_routes == ("/ai",)
    assert context.profile.public.stream_url == settings.public_stream_url
    assert context.profile.audio.minimum_qwen_buffer == 5
    assert coerce_station_context(settings).settings is settings
    assert coerce_station_context(context) is context


def test_station_context_is_frozen() -> None:
    context = english_compatibility_context(Settings())
    with pytest.raises(FrozenInstanceError):
        context.profile = make_profile("radiotedu-fr")  # type: ignore[misc]


def test_station_selectors_load_from_environment_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "STATION_ID=radiotedu-fr\nSTATION_PROFILES_DIR=private/stations\n",
        encoding="utf-8",
    )

    settings = Settings.from_env(env_file)

    assert settings.station_id == "radiotedu-fr"
    assert settings.station_profiles_dir == "private/stations"
    assert settings.station_profiles_path == Path("private/stations")


def test_canonical_profiles_have_frozen_identity() -> None:
    profiles = load_station_profiles(Path("config/stations"))

    assert set(profiles) == {"radiotedu-en", "radiotedu-fr"}
    assert profiles["radiotedu-en"] == StationProfile(
        profile_version=1,
        station_id="radiotedu-en",
        display_name="RadioTEDU",
        language="en",
        locale="en-US",
        timezone="Europe/Istanbul",
        public=PublicProfile(
            route="/ai/en",
            compatibility_routes=("/ai",),
            snapshot_endpoint="/api/public/stations/radiotedu-en/snapshot",
            status_endpoint="/api/public/stations/radiotedu-en/status",
            stream_url="https://radiotedu.com:8001/radiotedu-en",
        ),
        audio=AudioProfile("/radiotedu-en", -16, -1, 5),
        runtime=RuntimeProfile(
            "data/stations/radiotedu-en",
            "data/stations/radiotedu-en/radio.db",
            "media/stations/radiotedu-en/music",
            "data/stations/radiotedu-en/announcements",
            "data/stations/radiotedu-en/qwen-cache",
            "data/stations/radiotedu-en/logs",
        ),
        voice_pack="radiotedu-en-voices-v1",
        snapshot_secret_ref="RADIOTEDU_EN_SNAPSHOT_SECRET",
    )
    assert profiles["radiotedu-fr"] == StationProfile(
        profile_version=1,
        station_id="radiotedu-fr",
        display_name="RadioTEDU Français",
        language="fr",
        locale="fr-FR",
        timezone="Europe/Istanbul",
        public=PublicProfile(
            route="/ai/fr",
            compatibility_routes=(),
            snapshot_endpoint="/api/public/stations/radiotedu-fr/snapshot",
            status_endpoint="/api/public/stations/radiotedu-fr/status",
            stream_url="https://radiotedu.com:8001/radiotedu-fr",
        ),
        audio=AudioProfile("/radiotedu-fr", -16, -1, 5),
        runtime=RuntimeProfile(
            "data/stations/radiotedu-fr",
            "data/stations/radiotedu-fr/radio.db",
            "media/stations/radiotedu-fr/music",
            "data/stations/radiotedu-fr/announcements",
            "data/stations/radiotedu-fr/qwen-cache",
            "data/stations/radiotedu-fr/logs",
        ),
        voice_pack="radiotedu-fr-voices-v1",
        snapshot_secret_ref="RADIOTEDU_FR_SNAPSHOT_SECRET",
    )


def _canonical_raw(station_id: str = "radiotedu-en") -> dict[str, object]:
    return json.loads(Path(f"config/stations/{station_id}.json").read_text(encoding="utf-8"))


def _write_profile(directory: Path, name: str, raw: dict[str, object]) -> Path:
    path = directory / name
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_unknown_key_is_rejected_before_runtime_paths_are_created(tmp_path: Path) -> None:
    data_root = tmp_path / "must-not-exist"
    raw = _canonical_raw()
    raw["extra"] = True
    runtime = raw["runtime"]
    assert isinstance(runtime, dict)
    runtime["data_root"] = data_root.as_posix()

    profile_path = _write_profile(tmp_path, "bad.json", raw)
    with pytest.raises(StationProfileError, match="unknown keys: extra"):
        load_station_profile(profile_path)

    assert not data_root.exists()


def test_missing_and_unknown_nested_keys_are_rejected(tmp_path: Path) -> None:
    missing = _canonical_raw()
    del missing["voice_pack"]
    with pytest.raises(StationProfileError, match="missing keys: voice_pack"):
        load_station_profile(_write_profile(tmp_path, "missing.json", missing))

    nested = _canonical_raw()
    public = nested["public"]
    assert isinstance(public, dict)
    public["unexpected"] = "value"
    with pytest.raises(StationProfileError, match="public unknown keys: unexpected"):
        load_station_profile(_write_profile(tmp_path, "nested.json", nested))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("station_id", "RadioTEDU EN", "invalid station_id"),
        ("locale", "fr-FR", "language and locale do not agree"),
        ("timezone", "UTC", "timezone must be Europe/Istanbul"),
    ],
)
def test_identity_fields_are_strict(tmp_path: Path, field: str, value: object, message: str) -> None:
    raw = _canonical_raw()
    raw[field] = value
    with pytest.raises(StationProfileError, match=message):
        load_station_profile(_write_profile(tmp_path, f"bad-{field}.json", raw))


def test_scalar_values_are_not_coerced(tmp_path: Path) -> None:
    raw = _canonical_raw()
    raw["profile_version"] = True

    with pytest.raises(StationProfileError, match="profile.profile_version must be an integer"):
        load_station_profile(_write_profile(tmp_path, "coerced.json", raw))


@pytest.mark.parametrize(
    "mutation",
    [
        "display_name",
        "language_locale",
        "public_route",
        "compatibility_routes",
        "snapshot_endpoint",
        "status_endpoint",
        "stream_url",
        "stream_mount",
        "minimum_qwen_buffer",
        "music_root",
        "voice_pack",
        "snapshot_secret_ref",
    ],
)
def test_frozen_station_identity_rejects_mixed_or_alternate_values(tmp_path: Path, mutation: str) -> None:
    raw = _canonical_raw("radiotedu-en")
    public = raw["public"]
    audio = raw["audio"]
    runtime = raw["runtime"]
    assert isinstance(public, dict)
    assert isinstance(audio, dict)
    assert isinstance(runtime, dict)
    mutations = {
        "display_name": lambda: raw.__setitem__("display_name", "RadioTEDU English"),
        "language_locale": lambda: (raw.__setitem__("language", "fr"), raw.__setitem__("locale", "fr-FR")),
        "public_route": lambda: public.__setitem__("route", "/ai/english"),
        "compatibility_routes": lambda: public.__setitem__("compatibility_routes", []),
        "snapshot_endpoint": lambda: public.__setitem__("snapshot_endpoint", "/api/public/stations/radiotedu-en/other"),
        "status_endpoint": lambda: public.__setitem__("status_endpoint", "/api/public/stations/radiotedu-en/other"),
        "stream_url": lambda: public.__setitem__("stream_url", "https://radiotedu.com:8001/other"),
        "stream_mount": lambda: audio.__setitem__("stream_mount", "/radiotedu-en-alt"),
        "minimum_qwen_buffer": lambda: audio.__setitem__("minimum_qwen_buffer", 6),
        "music_root": lambda: runtime.__setitem__("music_root", "media/stations/radiotedu-en/alternate"),
        "voice_pack": lambda: raw.__setitem__("voice_pack", "radiotedu-en-voices-v2"),
        "snapshot_secret_ref": lambda: raw.__setitem__("snapshot_secret_ref", "RADIOTEDU_EN_OTHER_SECRET"),
    }
    mutations[mutation]()

    with pytest.raises(StationProfileError, match="frozen identity"):
        load_station_profile(_write_profile(tmp_path, f"mixed-{mutation}.json", raw))


def test_regex_valid_but_unsupported_station_id_is_rejected(tmp_path: Path) -> None:
    raw = _canonical_raw("radiotedu-en")
    raw["station_id"] = "radiotedu-de"

    with pytest.raises(StationProfileError, match="unsupported station_id"):
        load_station_profile(_write_profile(tmp_path, "radiotedu-de.json", raw))


def test_profile_directory_requires_both_canonical_stations(tmp_path: Path) -> None:
    _write_profile(tmp_path, "radiotedu-en.json", _canonical_raw("radiotedu-en"))

    with pytest.raises(StationProfileError, match="profile set must contain exactly"):
        load_station_profiles(tmp_path)


def test_profile_directory_rejects_empty_and_extra_sets(tmp_path: Path) -> None:
    with pytest.raises(StationProfileError, match="profile set must contain exactly"):
        load_station_profiles(tmp_path)

    _write_profile(tmp_path, "radiotedu-en.json", _canonical_raw("radiotedu-en"))
    _write_profile(tmp_path, "radiotedu-fr.json", _canonical_raw("radiotedu-fr"))
    extra = json.loads(
        json.dumps(_canonical_raw("radiotedu-en"))
        .replace("radiotedu-en", "radiotedu-de")
        .replace("RADIOTEDU_EN", "RADIOTEDU_DE")
    )
    extra["display_name"] = "RadioTEDU Deutsch"
    extra_public = extra["public"]
    assert isinstance(extra_public, dict)
    extra_public["route"] = "/ai/de"
    extra_public["compatibility_routes"] = []
    _write_profile(tmp_path, "radiotedu-de.json", extra)

    with pytest.raises(StationProfileError, match="unsupported station_id|profile set must contain exactly"):
        load_station_profiles(tmp_path)


def test_duplicate_station_ids_are_rejected(tmp_path: Path) -> None:
    raw = _canonical_raw()
    _write_profile(tmp_path, "one.json", raw)
    _write_profile(tmp_path, "two.json", raw)

    with pytest.raises(StationProfileError, match="duplicate station_id"):
        load_station_profiles(tmp_path)


def _set_runtime_tree(raw: dict[str, object], data_root: str) -> None:
    runtime = raw["runtime"]
    assert isinstance(runtime, dict)
    root = data_root.rstrip("/\\")
    runtime.update(
        {
            "data_root": root,
            "database": f"{root}/radio.db",
            "announcement_root": f"{root}/announcements",
            "cache_root": f"{root}/qwen-cache",
            "log_root": f"{root}/logs",
        }
    )


def test_cross_field_writable_path_alias_is_rejected(tmp_path: Path) -> None:
    english = _canonical_raw("radiotedu-en")
    french = _canonical_raw("radiotedu-fr")
    root = (tmp_path / "shared").as_posix()
    _set_runtime_tree(english, root)
    _set_runtime_tree(french, f"{root}/radio.db")
    _write_profile(tmp_path, "radiotedu-en.json", english)
    _write_profile(tmp_path, "radiotedu-fr.json", french)

    with pytest.raises(StationProfileError, match="writable path overlap"):
        load_station_profiles(tmp_path)


def test_cross_station_ancestor_descendant_writable_paths_are_rejected(tmp_path: Path) -> None:
    english = _canonical_raw("radiotedu-en")
    french = _canonical_raw("radiotedu-fr")
    root = (tmp_path / "ancestor").as_posix()
    _set_runtime_tree(english, root)
    _set_runtime_tree(french, f"{root}/radio.db/archive")
    _write_profile(tmp_path, "radiotedu-en.json", english)
    _write_profile(tmp_path, "radiotedu-fr.json", french)

    with pytest.raises(StationProfileError, match="writable path overlap"):
        load_station_profiles(tmp_path)


def test_windows_case_alias_between_station_paths_is_rejected(tmp_path: Path) -> None:
    english = _canonical_raw("radiotedu-en")
    french = _canonical_raw("radiotedu-fr")
    _set_runtime_tree(english, "C:/RadioTEDU/ProfileA")
    _set_runtime_tree(french, "c:/radiotedu/profilea/RADIO.DB")
    _write_profile(tmp_path, "radiotedu-en.json", english)
    _write_profile(tmp_path, "radiotedu-fr.json", french)

    with pytest.raises(StationProfileError, match="writable path overlap"):
        load_station_profiles(tmp_path)


def test_station_writable_children_must_be_strict_descendants(tmp_path: Path) -> None:
    raw = _canonical_raw("radiotedu-en")
    runtime = raw["runtime"]
    assert isinstance(runtime, dict)
    runtime["database"] = runtime["data_root"]

    with pytest.raises(StationProfileError, match="strictly beneath runtime.data_root"):
        load_station_profile(_write_profile(tmp_path, "equal-root.json", raw))


@pytest.mark.parametrize(
    "field",
    ["database", "data_root", "music_root", "announcement_root", "cache_root", "log_root"],
)
def test_each_named_writable_field_collision_is_rejected(tmp_path: Path, field: str) -> None:
    english = _canonical_raw("radiotedu-en")
    french = _canonical_raw("radiotedu-fr")
    english_runtime = english["runtime"]
    french_runtime = french["runtime"]
    assert isinstance(english_runtime, dict)
    assert isinstance(french_runtime, dict)
    french_runtime[field] = english_runtime[field]
    _write_profile(tmp_path, "radiotedu-en.json", english)
    _write_profile(tmp_path, "radiotedu-fr.json", french)

    with pytest.raises(StationProfileError):
        load_station_profiles(tmp_path)
