from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

from ..config import Settings


WEATHER_CODES = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class WeatherContext:
    available: bool
    location: str
    summary: str
    temperature_c: float | None = None
    humidity_percent: int | None = None
    wind_kmh: float | None = None
    condition: str | None = None
    source: str = "open-meteo"

    def to_dict(self) -> dict:
        return asdict(self)


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=4) as response:
        return json.loads(response.read().decode("utf-8"))


class OpenMeteoWeatherProvider:
    def __init__(self, settings: Settings, fetch_json=_fetch_json) -> None:
        self.settings = settings
        self.fetch_json = fetch_json

    def current_context(self) -> WeatherContext:
        location = self.settings.weather_location.strip() or "configured location"
        if not self.settings.weather_enabled:
            return WeatherContext(False, location, "No weather data.", source="disabled")
        if not self.settings.weather_latitude.strip() or not self.settings.weather_longitude.strip():
            return WeatherContext(False, location, "No weather data.", source="unconfigured")
        try:
            payload = self.fetch_json(self._url())
            current = payload.get("current") or payload.get("current_weather") or {}
            temperature = _as_float(current.get("temperature_2m", current.get("temperature")))
            humidity = _as_int(current.get("relative_humidity_2m"))
            wind = _as_float(current.get("wind_speed_10m", current.get("windspeed")))
            code = _as_int(current.get("weather_code", current.get("weathercode")))
            condition = WEATHER_CODES.get(code, f"weather code {code}") if code is not None else None
            parts = [location]
            if temperature is not None:
                parts.append(f"{round(temperature)} C")
            if condition:
                parts.append(condition)
            if humidity is not None:
                parts.append(f"humidity {humidity}%")
            if wind is not None:
                parts.append(f"wind {round(wind)} km/h")
            if len(parts) == 1:
                return WeatherContext(False, location, "No weather data.")
            return WeatherContext(
                True,
                location,
                ": ".join([parts[0], ", ".join(parts[1:])]),
                temperature_c=temperature,
                humidity_percent=humidity,
                wind_kmh=wind,
                condition=condition,
            )
        except Exception:
            return WeatherContext(False, location, "No weather data.")

    def _url(self) -> str:
        query = urllib.parse.urlencode(
            {
                "latitude": self.settings.weather_latitude,
                "longitude": self.settings.weather_longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            }
        )
        return f"https://api.open-meteo.com/v1/forecast?{query}"


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
