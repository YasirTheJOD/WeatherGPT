"""Geocoders — forward search (Open-Meteo, keyless) and reverse (BigDataCloud, keyless).

Both were verified live on 2026-09-06:
  - Open-Meteo geocoding: GET https://geocoding-api.open-meteo.com/v1/search?name=..&count=..
    Results carry name/latitude/longitude/country/country_code/admin1 (state).
  - BigDataCloud reverse: GET https://api.bigdatacloud.net/data/reverse-geocode-client
    ?latitude=..&longitude=..&localityLanguage=en  -> city/locality/principalSubdivision/countryName.

The India filter prefers Indian matches but falls back to all matches so
queries outside India still resolve.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.domain.models import LocationCandidate
from app.providers.base import ProviderUnavailable


class OpenMeteoGeocoder:
    """Forward geocoding via the Open-Meteo geocoding API."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(
            base_url=settings.geocoding_base_url, timeout=10.0
        )

    async def search(self, query: str, limit: int = 8) -> list[LocationCandidate]:
        try:
            resp = await self._client.get(
                "/v1/search",
                params={"name": query, "count": limit, "language": "en"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"Geocoding search failed: {exc}") from exc

        results = data.get("results") or []
        candidates = [
            LocationCandidate(
                name=str(r.get("name", "")),
                state=r.get("admin1"),
                country=r.get("country"),
                country_code=r.get("country_code"),
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                source="open-meteo",
                confidence=0.6,
            )
            for r in results
            if isinstance(r, dict) and r.get("latitude") is not None and r.get("longitude") is not None
        ]
        india = [c for c in candidates if c.country_code == "IN"]
        return india or candidates


class BigDataCloudReverseGeocoder:
    """Reverse geocoding via BigDataCloud (free tier, no API key)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(
            base_url=settings.reverse_geocoding_base_url, timeout=10.0
        )

    async def reverse(self, latitude: float, longitude: float) -> LocationCandidate | None:
        try:
            resp = await self._client.get(
                "/data/reverse-geocode-client",
                params={"latitude": latitude, "longitude": longitude, "localityLanguage": "en"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"Reverse geocoding failed: {exc}") from exc

        name = data.get("city") or data.get("locality")
        if not name:
            return None
        return LocationCandidate(
            name=str(name),
            state=data.get("principalSubdivision"),
            country=data.get("countryName"),
            country_code=data.get("countryCode"),
            latitude=float(data.get("latitude", latitude)),
            longitude=float(data.get("longitude", longitude)),
            source="bigdatacloud",
            confidence=0.8,
        )