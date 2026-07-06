from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover - exercised when mutagen is absent
    MutagenFile = None

from .config import Settings
from .database import connect, init_db, log_event, now_iso


AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg"}


@dataclass
class ScanResult:
    tracks_found: int
    tracks_indexed: int
    music_dir: str


def iter_audio_files(root: Path, limit: int | None = None) -> Iterator[Path]:
    if not root.exists():
        return
    count = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                stack.append(entry)
                continue
            if entry.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            yield entry
            count += 1
            if limit is not None and count >= limit:
                return


def infer_title_artist(path: Path) -> tuple[str, str]:
    stem = path.stem.strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return title.strip() or stem, artist.strip() or "Unknown Artist"
    return stem or path.name, "Unknown Artist"


def _first_tag(audio, names: tuple[str, ...]) -> str | None:
    if not audio or not getattr(audio, "tags", None):
        return None
    for name in names:
        value = audio.tags.get(name)
        if isinstance(value, list) and value:
            return str(value[0])
        if value:
            return str(value)
    return None


def _duration_with_wave(path: Path) -> float | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return round(frames / float(rate), 2) if rate else None
    except Exception:
        return None


def read_metadata(path: Path) -> dict:
    inferred_title, inferred_artist = infer_title_artist(path)
    audio = None
    if MutagenFile is not None:
        try:
            audio = MutagenFile(str(path), easy=True)
        except Exception:
            audio = None
    duration = None
    if audio is not None and getattr(audio, "info", None) is not None:
        duration = round(float(getattr(audio.info, "length", 0) or 0), 2) or None
    if duration is None:
        duration = _duration_with_wave(path)
    return {
        "title": _first_tag(audio, ("title",)) or inferred_title,
        "artist": _first_tag(audio, ("artist", "albumartist")) or inferred_artist,
        "album": _first_tag(audio, ("album",)),
        "genre": _first_tag(audio, ("genre",)),
        "mood": _first_tag(audio, ("mood",)),
        "bpm": None,
        "duration_seconds": duration,
        "file_path": str(path.resolve()),
    }


def scan_music(settings: Settings) -> ScanResult:
    init_db(settings)
    music_root = Path(settings.music_dir)
    found = 0
    indexed = 0
    timestamp = now_iso()
    with connect(settings) as conn:
        for audio_path in iter_audio_files(music_root):
            found += 1
            metadata = read_metadata(audio_path)
            conn.execute(
                """
                insert into tracks (
                    title, artist, album, genre, mood, bpm, duration_seconds, file_path,
                    cover_path, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(file_path) do update set
                    title=excluded.title,
                    artist=excluded.artist,
                    album=excluded.album,
                    genre=excluded.genre,
                    mood=excluded.mood,
                    bpm=excluded.bpm,
                    duration_seconds=excluded.duration_seconds,
                    updated_at=excluded.updated_at
                """,
                (
                    metadata["title"],
                    metadata["artist"],
                    metadata["album"],
                    metadata["genre"],
                    metadata["mood"],
                    metadata["bpm"],
                    metadata["duration_seconds"],
                    metadata["file_path"],
                    None,
                    timestamp,
                    timestamp,
                ),
            )
            indexed += 1
            if indexed % 250 == 0:
                conn.commit()
        log_event(conn, "info", f"Music scan complete: {found} tracks found.", {"music_dir": str(music_root)})
        if found == 0:
            log_event(conn, "info", "Radio loop not started because no playable tracks exist.")
        conn.commit()
    return ScanResult(tracks_found=found, tracks_indexed=indexed, music_dir=str(music_root))
