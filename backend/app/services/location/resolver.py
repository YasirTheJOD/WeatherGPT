"""Location resolver — the location stage of the pipeline.

Resolution order for a query:
  1. Alias index (curated, offline, deterministic) — highest confidence.
  2. Open-Meteo geocoder (live, India-preferred).
Candidates are merged (deduped by proximity), ranked by confidence, and
flagged `ambiguous` when the top candidates are close — the orchestrator
(Phase 4) turns ambiguity into a clarifying question.

Reverse resolution: nearest curated city first (offline), then BigDataCloud.
"""

from __future__ import annotations

from app.domain.models import LocationCandidate, ResolveResult
from app.services.location.alias_index import AliasIndex, normalize
from app.services.location.geocoder import BigDataCloudReverseGeocoder, OpenMeteoGeocoder
from app.services.location.station_index import StationIndex, haversine_km

_DEDUPE_KM = 5.0
_AMBIGUITY_GAP = 0.2


class LocationResolver:
    def __init__(
        self,
        alias_index: AliasIndex,
        geocoder: OpenMeteoGeocoder,
        reverse_geocoder: BigDataCloudReverseGeocoder,
        station_index: StationIndex | None = None,
    ):
        self._aliases = alias_index
        self._geocoder = geocoder
        self._reverse_geocoder = reverse_geocoder
        self._station_index = station_index

    async def search(self, query: str, limit: int = 8) -> ResolveResult:
        normalized = normalize(query)
        alias_hits = self._aliases.lookup(query)
        geo_hits: list[LocationCandidate] = []
        try:
            geo_hits = await self._geocoder.search(query, limit=limit)
        except Exception:  # geocoder outage must not kill location search
            geo_hits = []

        merged = self._dedupe(alias_hits + geo_hits)
        merged.sort(key=lambda c: c.confidence, reverse=True)
        merged = merged[:limit]

        ambiguous = (
            len(merged) >= 2
            and (merged[0].confidence - merged[1].confidence) < _AMBIGUITY_GAP
        )
        return ResolveResult(query=query, normalized=normalized, candidates=merged, ambiguous=ambiguous)

    async def reverse(self, latitude: float, longitude: float) -> LocationCandidate | None:
        nearest = self._aliases.nearest(latitude, longitude)
        if nearest is not None:
            return nearest
        try:
            return await self._reverse_geocoder.reverse(latitude, longitude)
        except Exception:
            return None

    def nearest_station(self, latitude: float, longitude: float) -> LocationCandidate | None:
        if self._station_index is None:
            return None
        station = self._station_index.nearest(latitude, longitude)
        if station is None:
            return None
        return LocationCandidate(
            name=station.name,
            state=station.state,
            country_code="IN",
            latitude=station.latitude,
            longitude=station.longitude,
            source="imd-station",
            confidence=0.9,
        )

    @staticmethod
    def _dedupe(candidates: list[LocationCandidate]) -> list[LocationCandidate]:
        """Keep the highest-confidence candidate within a small radius."""
        kept: list[LocationCandidate] = []
        for candidate in sorted(candidates, key=lambda c: c.confidence, reverse=True):
            if not any(
                haversine_km(candidate.latitude, candidate.longitude, k.latitude, k.longitude)
                < _DEDUPE_KM
                for k in kept
            ):
                kept.append(candidate)
        return kept