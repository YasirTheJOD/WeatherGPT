"""IMD provider — official India Meteorological Department API platform.

Authoritative source for observations, forecasts and district warnings.

Access status (verified 2026-09-06):
  - Live probe of /api/v1/current_wx and /api/v1/cityforecast returned
    {"error": "API key missing"} — an API key is required.
  - IMD's own pages additionally mention IP whitelisting and require
    attribution + client-side caching.
  - The exact auth mechanism (header vs query param) is not documented
    publicly; the key is sent as X-API-Key here pending confirmation.
  See docs/IMD-ACCESS.md for the application checklist and test commands.

Endpoint reference (verified 2026-09-06):
  https://api.imd.gov.in/public/api_reference.html
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import httpx

from app.core.config import Settings
from app.domain.models import ForecastDay, Provenance, Station, WeatherObservation
from app.providers.base import LocationQuery, ProviderUnavailable
from app.services.location.station_index import StationIndex

# IMD weather codes (current_wx) -> description, subset transcribed from the
# official API reference (01-99). Full mapping lands with the Phase 2 normalizer.
_IMD_WX_TEXT: dict[int, str] = {
    10: "Mist",
    21: "Rain (not freezing) not falling as showers",
    25: "Showers of rain",
    28: "Fog or ice fog",
    29: "Thunderstorm (with or without precipitation)",
    61: "Rain, not freezing, intermittent slight",
    63: "Rain, not freezing, continuous moderate",
    64: "Rain, not freezing, intermittent heavy",
    80: "Rain shower(s), slight",
    81: "Rain shower(s), moderate or heavy",
    82: "Rain shower(s), violent",
    95: "Thunderstorm, slight/moderate, without hail",
    97: "Thunderstorm, heavy, without hail",
    99: "Thunderstorm, heavy, with hail",
}

# IMD wind direction codes -> description, from the official API reference.
_IMD_WIND_DIR: dict[int, str] = {
    0: "Calm",
    20: "North-northeasterly",
    50: "Northeasterly",
    70: "East-northeasterly",
    90: "Easterly",
    110: "East-southeasterly",
    140: "Southeasterly",
    160: "South-southeasterly",
    180: "Southerly",
    200: "South-southwesterly",
    230: "Southwesterly",
    250: "West-southwesterly",
    270: "Westerly",
    290: "West-northwesterly",
    320: "Northwesterly",
    340: "North-northwesterly",
    360: "Northerly",
}


def _f(value: object) -> float | None:
    """Best-effort float conversion of IMD string fields."""
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _i(value: object) -> int | None:
    f = _f(value)
    return int(f) if f is not None else None


def _first_record(data: object) -> dict:
    """IMD may return a single record or a list of records; normalize."""
    if isinstance(data, list):
        if not data:
            raise ProviderUnavailable("IMD returned an empty record list")
        record = data[0]
    else:
        record = data
    if not isinstance(record, dict):
        raise ProviderUnavailable(f"IMD returned an unexpected shape: {type(record).__name__}")
    return record


class IMDProvider:
    provider_id = "imd"
    name = "India Meteorological Department (IMD)"

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        station_index: StationIndex | None = None,
    ):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.imd_base_url, timeout=10.0
        )
        self._station_index = station_index

    def is_configured(self) -> bool:
        return self._settings.imd_configured

    def _resolve_station(self, location: LocationQuery) -> str:
        """Station code for a request: explicit station_id wins, else the
        nearest indexed station within 50 km (Phase 2 station mapping)."""
        if location.station_id:
            return location.station_id
        if self._station_index is None:
            raise ProviderUnavailable(
                "IMD station index not configured (see docs/IMD-ACCESS.md)"
            )
        station: Station | None = self._station_index.nearest(
            location.latitude, location.longitude
        )
        if station is None:
            raise ProviderUnavailable(
                f"no IMD station within 50 km of ({location.latitude:.2f}, {location.longitude:.2f})"
            )
        return station.station_code

    async def _get(self, path: str, params: dict | None = None) -> object:
        if not self._settings.imd_configured:
            raise ProviderUnavailable("IMD API key not configured (see docs/IMD-ACCESS.md)")
        headers = {"X-API-Key": self._settings.imd_api_key}  # confirm auth mechanism with IMD
        try:
            resp = await self._client.get(path, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(
                f"IMD returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"IMD request failed: {exc}") from exc
        if isinstance(data, dict) and "error" in data:
            raise ProviderUnavailable(f"IMD error: {data['error']}")
        return data

    async def current_weather(self, location: LocationQuery) -> WeatherObservation:
        station_id = self._resolve_station(location)
        data = await self._get("/api/v1/current_wx", {"id": station_id})
        rec = _first_record(data)

        code = _i(rec.get("Weather Code"))
        wind_code = _i(rec.get("Wind Direction"))
        observed_at = self._parse_obs_time(
            rec.get("Date of Observation"), rec.get("Time of Observation")
        )
        return WeatherObservation(
            latitude=location.latitude,
            longitude=location.longitude,
            location_name=rec.get("Station") or location.city_name,
            temperature_c=_f(rec.get("Temperature")),
            humidity_pct=_f(rec.get("Humidity")),
            wind_speed_kmph=_f(rec.get("Wind Speed")),
            wind_direction=_IMD_WIND_DIR.get(wind_code) if wind_code is not None else None,
            pressure_hpa=_f(rec.get("M.S.L.P")),
            weather_code=code,
            condition_text=_IMD_WX_TEXT.get(code) if code is not None else None,
            rainfall_24h_mm=_f(rec.get("Last 24 hrs Rainfall")),
            # IMD's field really is the observed rain of the past 24 hours.
            rainfall_basis="observed_24h",
            observed_at=observed_at,
            provenance=Provenance(
                source_id=self.provider_id,
                source_name=self.name,
                authoritative=True,
                fetched_at=datetime.now(timezone.utc),
                valid_at=observed_at,
                ttl_seconds=300,
                raw_endpoint=f"/api/v1/current_wx?id={station_id}",
            ),
        )

    async def daily_forecast(self, location: LocationQuery, days: int = 7) -> list[ForecastDay]:
        station_id = self._resolve_station(location)
        data = await self._get("/api/v1/cityforecast", {"id": station_id})
        rec = _first_record(data)

        fetched_at = datetime.now(timezone.utc)
        provenance = Provenance(
            source_id=self.provider_id,
            source_name=self.name,
            authoritative=True,
            fetched_at=fetched_at,
            ttl_seconds=1800,
            raw_endpoint=f"/api/v1/cityforecast?id={station_id}",
        )
        # Today's forecast uses the Todays_Forecast_* fields; Day_2..Day_7 use
        # the Day_N_* fields (per the official API reference).
        result: list[ForecastDay] = []
        horizon = min(max(days, 1), 7)
        base_date = self._parse_date(rec.get("Date"))

        today = ForecastDay(
            date=base_date.date().isoformat() if base_date else (rec.get("Date") or "day_1"),
            tmax_c=_f(rec.get("Todays_Forecast_Max_Temp")),
            tmin_c=_f(rec.get("Todays_Forecast_Min_temp")),
            condition_text=rec.get("Todays_Forecast"),
            provenance=provenance,
        )
        result.append(today)

        for offset in range(2, horizon + 1):
            suffix = f"Day_{offset}_"
            date = (
                (base_date + timedelta(days=offset - 1)).date().isoformat()
                if base_date
                else f"day_{offset}"
            )
            result.append(
                ForecastDay(
                    date=date,
                    tmax_c=_f(rec.get(f"{suffix}Max_Temp")),
                    tmin_c=_f(rec.get(f"{suffix}Min_temp")),
                    condition_text=rec.get(f"{suffix}Forecast"),
                    provenance=provenance,
                )
            )
        return result

    @staticmethod
    def _parse_date(value: object) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _parse_obs_time(date_value: object, time_value: object) -> datetime | None:
        base = IMDProvider._parse_date(date_value)
        if base is None:
            return None
        if not time_value:
            return base.replace(tzinfo=timezone.utc)
        try:
            t = datetime.strptime(str(time_value).strip(), "%H:%M").time()
            return datetime.combine(base.date(), t, tzinfo=timezone.utc)
        except ValueError:
            return base.replace(tzinfo=timezone.utc)