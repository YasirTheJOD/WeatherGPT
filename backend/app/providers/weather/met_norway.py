"""MET Norway Locationforecast provider — free, keyless, global.

Why a third provider exists
---------------------------
Open-Meteo's free tier allows **one concurrent request per IP** (five queued
before it answers 429). On shared hosting egress that budget belongs to every
tenant on the address, so ``api.open-meteo.com`` can answer 429 for hours at a
time while ``geocoding-api.open-meteo.com`` — a different host, same deploy —
stays healthy.

Measured 2026-09-25 from the Render free service: **0 of 18** requests
succeeded over ~110s (all 429), while the identical call from a residential IP
returned 200 in 1.4s. A single vendor's rate limiter must not be able to take
the weather down, which is what a real fallback chain is for.

MET Norway's Locationforecast 2.0 is keyless and global, and its terms require
only a descriptive ``User-Agent`` (``MET_NORWAY_USER_AGENT``) — no account, no
card, no whitelist. That keeps the zero-keys demo property intact.

Normalization notes (both deliberate)
-------------------------------------
MET Norway is a *forecast model*, not an observation source (Open-Meteo is the
same), so two fields carry forecast-derived meanings:

  - ``current_weather`` reads the **first** timeseries entry — MET Norway
    returns the current hour first — and reports ``rainfall_24h_mm`` as the sum
    of the next 24 entries. That is forecast rainfall for the coming 24h, not
    an observed 24h total.
  - ``daily_forecast`` buckets the series into Asia/Kolkata local days. Each
    entry's ``precipitation_amount`` covers the interval up to the *next*
    entry, so summing per day stays correct across the hourly-to-6-hourly
    switch MET Norway makes a few days out.

Docs:  https://api.met.no/weatherapi/locationforecast/2.0/documentation
Terms: https://api.met.no/doc/TermsOfService
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import Settings
from app.domain.models import ForecastDay, Provenance, WeatherObservation
from app.providers.base import LocationQuery, ProviderUnavailable

# India has no DST, so a fixed offset is exact — and, unlike zoneinfo, it needs
# no `tzdata` dependency (Windows ships no IANA database).
_IST = timezone(timedelta(hours=5, minutes=30))

_CURRENT_TTL_S = 300
_DAILY_TTL_S = 1800
_RAINFALL_WINDOW_ENTRIES = 24

# MET Norway symbol codes -> short text. Day/night/polartwilight variants are
# folded to their base code by _symbol_text (the vocabulary is the same).
_SYMBOL_TEXT: dict[str, str] = {
    "clearsky": "Clear sky",
    "fair": "Fair",
    "partlycloudy": "Partly cloudy",
    "cloudy": "Cloudy",
    "fog": "Fog",
    "lightrain": "Light rain",
    "rain": "Rain",
    "heavyrain": "Heavy rain",
    "lightrainshowers": "Light rain showers",
    "rainshowers": "Rain showers",
    "heavyrainshowers": "Heavy rain showers",
    "lightsleet": "Light sleet",
    "sleet": "Sleet",
    "heavysleet": "Heavy sleet",
    "lightsleetshowers": "Light sleet showers",
    "sleetshowers": "Sleet showers",
    "heavysleetshowers": "Heavy sleet showers",
    "lightsnow": "Light snow",
    "snow": "Snow",
    "heavysnow": "Heavy snow",
    "lightsnowshowers": "Light snow showers",
    "snowshowers": "Snow showers",
    "heavysnowshowers": "Heavy snow showers",
    "rainandthunder": "Rain and thunder",
    "heavyrainandthunder": "Heavy rain and thunder",
    "sleetandthunder": "Sleet and thunder",
    "snowandthunder": "Snow and thunder",
    "rainshowersandthunder": "Rain showers and thunder",
    "heavyrainshowersandthunder": "Heavy rain showers and thunder",
}

_VARIANTS = ("_day", "_night", "_polartwilight")

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


def _symbol_text(code: str | None) -> str | None:
    """Readable condition text. Unknown codes are prettified, never dropped."""
    if not code:
        return None
    if code in _SYMBOL_TEXT:
        return _SYMBOL_TEXT[code]
    for variant in _VARIANTS:
        if code.endswith(variant):
            base = code[: -len(variant)]
            return _SYMBOL_TEXT.get(base) or base.replace("_", " ").capitalize()
    return code.replace("_", " ").capitalize()


def _details(entry: dict, key: str) -> dict:
    return ((entry.get("data") or {}).get(key) or {}).get("details") or {}


def _symbol_code(entry: dict) -> str | None:
    """Finest available period's symbol — the series thins out days ahead."""
    for key in ("next_1_hours", "next_6_hours", "next_12_hours"):
        summary = ((entry.get("data") or {}).get(key) or {}).get("summary") or {}
        if summary.get("symbol_code"):
            return summary["symbol_code"]
    return None


def _precip_amount(entry: dict) -> float | None:
    """Precipitation for the interval up to the next entry, at the finest period.

    Because each amount covers its own interval, summing them over a day is
    correct whether the series is hourly or 6-hourly.
    """
    for key in ("next_1_hours", "next_6_hours", "next_12_hours"):
        amount = _details(entry, key).get("precipitation_amount")
        if amount is not None:
            return amount
    return None


def _local_date(entry: dict) -> str | None:
    parsed = _parse_iso(entry.get("time"))
    if parsed is None:
        return None
    return parsed.astimezone(_IST).date().isoformat()


def _dominant_symbol(symbols: list[str]) -> str | None:
    """Most frequent symbol for a day; ties go to the first occurrence.

    Deliberately deterministic: one captured series must always yield one daily
    condition, so the rehearsal and the demo cannot drift apart. ``max`` returns
    the first maximal element, which is exactly that tie-break.
    """
    if not symbols:
        return None
    counts = Counter(symbols)
    return max(symbols, key=lambda code: counts[code])


@dataclass
class _DayBucket:
    """One local day's entries, aggregated into the ForecastDay fields."""

    temps: list[float] = field(default_factory=list)
    humidity: list[float] = field(default_factory=list)
    wind: list[float] = field(default_factory=list)
    rain: list[float] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)


class MetNorwayProvider:
    provider_id = "met-no"
    name = "MET Norway (Locationforecast)"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.met_norway_base_url,
            timeout=10.0,
            # MET Norway's terms require a User-Agent that identifies the app.
            headers={"User-Agent": settings.met_norway_user_agent},
        )

    def is_configured(self) -> bool:
        return True  # keyless by design

    async def _series(self, location: LocationQuery) -> list[dict]:
        # MET Norway asks for coordinates rounded to 4 decimals so responses
        # stay cacheable.
        params = {"lat": round(location.latitude, 4), "lon": round(location.longitude, 4)}
        try:
            resp = await self._client.get(
                "/weatherapi/locationforecast/2.0/compact", params=params
            )
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"MET Norway request failed: {exc}") from exc
        series = (payload.get("properties") or {}).get("timeseries") or []
        if not series:
            raise ProviderUnavailable("MET Norway returned an empty forecast series")
        return series

    def _provenance(self, ttl_seconds: int) -> Provenance:
        return Provenance(
            source_id=self.provider_id,
            source_name=self.name,
            authoritative=False,
            fetched_at=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,
            raw_endpoint=(
                f"{self._settings.met_norway_base_url}"
                "/weatherapi/locationforecast/2.0/compact"
            ),
        )

    async def current_weather(self, location: LocationQuery) -> WeatherObservation:
        series = await self._series(location)
        first = series[0]
        instant = _details(first, "instant")

        # Forecast rainfall for the coming 24h (see the module docstring).
        amounts = [
            amount
            for amount in (
                _precip_amount(entry) for entry in series[:_RAINFALL_WINDOW_ENTRIES]
            )
            if amount is not None
        ]
        wind_ms = instant.get("wind_speed")

        return WeatherObservation(
            latitude=location.latitude,
            longitude=location.longitude,
            location_name=location.city_name,
            temperature_c=instant.get("air_temperature"),
            humidity_pct=instant.get("relative_humidity"),
            wind_speed_kmph=round(wind_ms * 3.6, 1) if wind_ms is not None else None,
            wind_direction=_degrees_to_compass(instant.get("wind_from_direction")),
            pressure_hpa=instant.get("air_pressure_at_sea_level"),
            # MET Norway publishes symbol codes, not WMO codes.
            weather_code=None,
            condition_text=_symbol_text(_symbol_code(first)),
            rainfall_24h_mm=round(sum(amounts), 1) if amounts else None,
            observed_at=_parse_iso(first.get("time")),
            provenance=self._provenance(_CURRENT_TTL_S),
        )

    async def daily_forecast(
        self, location: LocationQuery, days: int = 7
    ) -> list[ForecastDay]:
        series = await self._series(location)

        buckets: dict[str, _DayBucket] = {}
        for entry in series:
            day = _local_date(entry)
            if day is None:
                continue
            bucket = buckets.setdefault(day, _DayBucket())
            instant = _details(entry, "instant")
            for target, value in (
                (bucket.temps, instant.get("air_temperature")),
                (bucket.humidity, instant.get("relative_humidity")),
                (bucket.wind, instant.get("wind_speed")),
                (bucket.rain, _precip_amount(entry)),
            ):
                if value is not None:
                    target.append(value)  # type: ignore[arg-type]
            symbol = _symbol_code(entry)
            if symbol:
                bucket.symbols.append(symbol)

        # Earliest local day first — MET Norway starts the series at the current
        # hour, so day 1 is today (partial if the capture began mid-day).
        result: list[ForecastDay] = []
        for day in sorted(buckets)[:days]:
            bucket = buckets[day]
            result.append(
                ForecastDay(
                    date=day,
                    tmax_c=max(bucket.temps) if bucket.temps else None,
                    tmin_c=min(bucket.temps) if bucket.temps else None,
                    condition_text=_symbol_text(_dominant_symbol(bucket.symbols)),
                    rainfall_mm=round(sum(bucket.rain), 1) if bucket.rain else None,
                    humidity_pct=(
                        round(sum(bucket.humidity) / len(bucket.humidity), 1)
                        if bucket.humidity
                        else None
                    ),
                    wind_speed_kmph=(
                        round(max(bucket.wind) * 3.6, 1) if bucket.wind else None
                    ),
                    provenance=self._provenance(_DAILY_TTL_S),
                )
            )
        return result
