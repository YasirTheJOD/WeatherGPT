"""Open-Meteo provider — free, keyless, GFS-derived point forecasts.

Resilience / fallback layer until the IMD key and IP whitelist are active.
Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.domain.models import ForecastDay, Provenance, WeatherObservation
from app.providers.base import LocationQuery, ProviderUnavailable

# WMO weather codes -> short text. Subset sufficient for the prototype;
# extended in Phase 4 together with the IMD code normalizer.
_WMO_TEXT: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail",
}

_COMPASS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _degrees_to_compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    idx = int((degrees % 360) / 22.5 + 0.5) % 16
    return _COMPASS[idx]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _at(values: list | None, index: int) -> float | int | str | None:
    """Safe element access for parallel Open-Meteo arrays."""
    if not values or index >= len(values):
        return None
    return values[index]


class OpenMeteoProvider:
    provider_id = "open-meteo"
    name = "Open-Meteo (GFS-derived)"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.open_meteo_base_url, timeout=10.0
        )

    def is_configured(self) -> bool:
        return True  # keyless by design

    async def _get(self, params: dict) -> dict:
        try:
            resp = await self._client.get("/v1/forecast", params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"Open-Meteo request failed: {exc}") from exc

    async def current_weather(self, location: LocationQuery) -> WeatherObservation:
        data = await self._get(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": (
                    "temperature_2m,relative_humidity_2m,wind_speed_10m,"
                    "wind_direction_10m,surface_pressure,weather_code,precipitation"
                ),
            }
        )
        current = data.get("current") or {}
        code = current.get("weather_code")
        fetched_at = datetime.now(timezone.utc)
        return WeatherObservation(
            latitude=location.latitude,
            longitude=location.longitude,
            location_name=location.city_name,
            temperature_c=current.get("temperature_2m"),
            humidity_pct=current.get("relative_humidity_2m"),
            wind_speed_kmph=current.get("wind_speed_10m"),
            wind_direction=_degrees_to_compass(current.get("wind_direction_10m")),
            pressure_hpa=current.get("surface_pressure"),
            weather_code=code,
            condition_text=_WMO_TEXT.get(code) if code is not None else None,
            rainfall_24h_mm=current.get("precipitation"),
            # `current.precipitation` is instantaneous, NOT a 24h accumulation.
            rainfall_basis="instant",
            observed_at=_parse_iso(current.get("time")),
            provenance=Provenance(
                source_id=self.provider_id,
                source_name=self.name,
                authoritative=False,
                fetched_at=fetched_at,
                ttl_seconds=300,
            ),
        )

    async def daily_forecast(self, location: LocationQuery, days: int = 7) -> list[ForecastDay]:
        data = await self._get(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,relative_humidity_2m_mean,wind_speed_10m_max"
                ),
                "forecast_days": days,
                "timezone": "Asia/Kolkata",
            }
        )
        daily = data.get("daily") or {}
        dates = daily.get("time") or []
        fetched_at = datetime.now(timezone.utc)
        result: list[ForecastDay] = []
        for i, date in enumerate(dates):
            code = _at(daily.get("weather_code"), i)
            result.append(
                ForecastDay(
                    date=date,
                    tmax_c=_at(daily.get("temperature_2m_max"), i),
                    tmin_c=_at(daily.get("temperature_2m_min"), i),
                    condition_text=_WMO_TEXT.get(code) if code is not None else None,
                    rainfall_mm=_at(daily.get("precipitation_sum"), i),
                    humidity_pct=_at(daily.get("relative_humidity_2m_mean"), i),
                    wind_speed_kmph=_at(daily.get("wind_speed_10m_max"), i),
                    provenance=Provenance(
                        source_id=self.provider_id,
                        source_name=self.name,
                        authoritative=False,
                        fetched_at=fetched_at,
                        ttl_seconds=1800,
                    ),
                )
            )
        return result