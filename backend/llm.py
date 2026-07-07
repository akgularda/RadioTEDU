from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Settings


SYSTEM_PROMPT = """You are RadioTEDU, a concise local AI radio DJ.
You must return valid JSON only.
Never invent songs that are not in the candidate list.
Keep narration short, warm, and specific.
Do not mention being a language model.
Do not mention internal tools.
Do not exceed 24 words for the DJ line."""


@dataclass
class DJChoice:
    song_id: int
    dj_line: str
    reason: str
    used_fallback: bool = False


def _fallback(candidates: list[dict], reason: str, web_context: list[dict] | None = None) -> DJChoice:
    selected = sorted(candidates, key=lambda item: int(item["id"]))[0]
    line = _fallback_line(selected, web_context or [])
    return DJChoice(song_id=int(selected["id"]), dj_line=line, reason=f"Fallback: {reason}", used_fallback=True)


def _fallback_line(selected: dict, web_context: list[dict]) -> str:
    title = selected.get("title") or "this track"
    artist = selected.get("artist") or "a local artist"
    snippet = _matching_snippet(selected, web_context)
    if snippet:
        line = f"RadioTEDU cues {title} by {artist}; source note: {_short_phrase(snippet, 12)}."
        return _limit_words(line, 24)
    album = _clean_value(selected.get("album"))
    genre = _clean_value(selected.get("genre"))
    mood = _clean_value(selected.get("mood"))
    duration = _duration_phrase(selected.get("duration_seconds"))
    if album and genre:
        line = f"RadioTEDU cues {title} by {artist}, from {album}, a {genre} track."
    elif album:
        line = f"RadioTEDU cues {title} by {artist}, from {album}."
    elif genre:
        line = f"RadioTEDU cues {title} by {artist}, a {genre} track."
    elif mood:
        line = f"RadioTEDU cues {title} by {artist}, with a {mood} mood."
    elif duration:
        line = f"RadioTEDU cues {title} by {artist}, running {duration}."
    else:
        line = f"RadioTEDU keeps it local with {title} by {artist}."
    return _limit_words(line, 24)


def _matching_snippet(selected: dict, web_context: list[dict]) -> str | None:
    title = str(selected.get("title") or "").lower()
    artist = str(selected.get("artist") or "").lower()
    for item in web_context[:5]:
        haystack = f"{item.get('title') or ''} {item.get('snippet') or ''}".lower()
        if title and title in haystack:
            return _clean_value(item.get("snippet"))
        if artist and artist in haystack:
            return _clean_value(item.get("snippet"))
    return None


def _clean_value(value: object) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


def _short_phrase(text: str, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max_words])


def _duration_phrase(value: object) -> str | None:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    minutes, remaining = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remaining:02d}s"
    return f"{remaining}s"


def _limit_words(line: str, limit: int) -> str:
    words = line.split()
    if len(words) <= limit:
        return line
    return " ".join(words[:limit])


def validate_choice(payload: dict, candidates: list[dict]) -> DJChoice:
    candidate_ids = {int(item["id"]) for item in candidates}
    song_id = int(payload.get("song_id"))
    line = str(payload.get("dj_line", "")).strip()
    reason = str(payload.get("reason", "")).strip()
    if song_id not in candidate_ids:
        raise ValueError("song_id outside candidates")
    if not line:
        raise ValueError("dj_line is empty")
    if len(line.split()) > 24:
        raise ValueError("dj_line exceeds 24 words")
    if not reason:
        raise ValueError("reason is empty")
    return DJChoice(song_id=song_id, dj_line=line, reason=reason)


def choose_track_with_llm(
    candidates: list[dict],
    program: dict,
    recent_tracks: list[dict],
    web_context: list[dict],
    settings: Settings | None = None,
    llm_response_text: str | None = None,
    weather_context: dict | None = None,
    runtime_status: dict | None = None,
) -> DJChoice:
    if not candidates:
        raise ValueError("cannot choose a track without candidates")
    if llm_response_text is not None:
        try:
            return validate_choice(json.loads(llm_response_text), candidates)
        except Exception as exc:
            return _fallback(candidates, str(exc), web_context)
    if settings is None:
        return _fallback(candidates, "LLM settings were not provided", web_context)
    if runtime_status is not None and not _runtime_can_generate(runtime_status):
        status = runtime_status.get("status", "unavailable")
        model = runtime_status.get("configured_model", settings.ollama_model)
        return _fallback(candidates, f"LLM runtime unavailable ({status}: {model})", web_context)
    prompt = build_user_prompt(program, candidates, recent_tracks, web_context, weather_context)
    last_error: Exception | None = None
    try:
        for attempt in range(2):
            response_text = call_ollama(settings, prompt if attempt == 0 else f"{prompt}\n\nYour previous response was invalid JSON. Return valid JSON only.")
            try:
                return validate_choice(json.loads(response_text), candidates)
            except Exception as exc:
                last_error = exc
        return _fallback(candidates, str(last_error), web_context)
    except Exception as exc:
        return _fallback(candidates, str(exc), web_context)


def _runtime_can_generate(runtime_status: dict) -> bool:
    return bool(runtime_status.get("reachable")) and bool(runtime_status.get("model_available")) and runtime_status.get("status") == "ready"


def build_user_prompt(
    program: dict,
    candidates: list[dict],
    recent_tracks: list[dict],
    web_context: list[dict],
    weather_context: dict | None = None,
) -> str:
    candidate_lines = [
        (
            f"- id={item['id']} | title={item.get('title')} | artist={item.get('artist')} | "
            f"album={item.get('album') or 'unknown'} | genre={item.get('genre') or 'unknown'} | "
            f"duration={item.get('duration_seconds') or 'unknown'}"
        )
        for item in candidates
    ]
    context_lines = [f"- {item.get('title')}: {item.get('snippet')}" for item in web_context[:3]]
    recent_lines = [f"- {item.get('title')} by {item.get('artist')}" for item in recent_tracks[:5]]
    weather_line = weather_context.get("summary") if weather_context and weather_context.get("available") else "none"
    return "\n".join(
        [
            "Station: RadioTEDU",
            f"Current program: {program.get('name')}",
            f"Program description: {program.get('description')}",
            f"Vibe: {program.get('vibe')}",
            f"Host: {program.get('host_name') or 'RadioTEDU'} ({program.get('host_gender') or 'neutral'})",
            f"Host personality: {program.get('personality') or 'concise, warm, music-first'}",
            f"Last played tracks: {'; '.join(recent_lines) if recent_lines else 'none'}",
            f"Web/RSS context: {'; '.join(context_lines) if context_lines else 'none'}",
            f"Weather context: {weather_line}",
            "",
            "Candidate songs:",
            "\n".join(candidate_lines),
            "",
            "Choose exactly one song and write one DJ line of at most 24 words.",
            'Return JSON: {"song_id": "...", "dj_line": "...", "reason": "..."}',
        ]
    )


def call_ollama(settings: Settings, prompt: str) -> str:
    request = urllib.request.Request(
        f"{settings.ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(
            {
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"num_predict": 160},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.ollama_timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    message = payload.get("message") or {}
    return str(message.get("content") or payload.get("response") or "").strip()


def ollama_runtime_status(settings: Settings, fetch_json=None) -> dict:
    provider = settings.llm_provider.lower()
    base_url = settings.ollama_url.rstrip("/")
    configured_model = settings.ollama_model
    if provider != "ollama":
        return {
            "provider": settings.llm_provider,
            "configured_model": configured_model,
            "base_url": base_url,
            "reachable": False,
            "model_available": False,
            "installed_models": [],
            "status": "disabled",
            "error": None,
        }
    fetch = fetch_json or _fetch_ollama_json
    try:
        payload = fetch(f"{base_url}/api/tags")
    except Exception as exc:
        return {
            "provider": "ollama",
            "configured_model": configured_model,
            "base_url": base_url,
            "reachable": False,
            "model_available": False,
            "installed_models": [],
            "status": "unreachable",
            "error": str(exc),
        }
    installed = []
    for item in payload.get("models", []):
        name = item.get("name") or item.get("model")
        if name:
            installed.append(str(name))
    available = configured_model in installed
    return {
        "provider": "ollama",
        "configured_model": configured_model,
        "base_url": base_url,
        "reachable": True,
        "model_available": available,
        "installed_models": installed,
        "status": "ready" if available else "model_missing",
        "error": None if available else f"Model {configured_model} is not installed.",
    }


def _fetch_ollama_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=0.75) as response:
        return json.loads(response.read().decode("utf-8"))
