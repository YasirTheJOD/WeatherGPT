"""City alias index — curated names + Hinglish/regional aliases.

Locations are the highest-friction part of a conversational weather system
(duplicate Indian place names, Hinglish spellings, regional names). The
alias index is the fast, offline, deterministic first stage of resolution;
the geocoder is the second. Data lives in `data/cities_seed.json`
(curated seed — see backend/data/README.md).
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from app.domain.models import LocationCandidate

_EXACT_CONFIDENCE = 0.95
_SUBSTRING_CONFIDENCE = 0.8


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace — so \"Bengalūru\",
    \"BENGALURU\", and \" Bengaluru \" all match \"bengaluru\"."""
    decomposed = unicodedata.normalize("NFD", text.strip().lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.split())


class AliasIndex:
    def __init__(self, records: list[dict]):
        self._aliases: dict[str, LocationCandidate] = {}
        self._canonical: list[LocationCandidate] = []
        for record in records:
            candidate = LocationCandidate(
                name=str(record["name"]),
                state=record.get("state"),
                country=record.get("country"),
                country_code=record.get("country_code", "IN"),
                latitude=float(record["latitude"]),
                longitude=float(record["longitude"]),
                source="aliases",
                confidence=_EXACT_CONFIDENCE,
            )
            self._canonical.append(candidate)
            keys = {normalize(record["name"])}
            keys.update(normalize(a) for a in record.get("aliases", []))
            for key in keys:
                self._aliases[key] = candidate

    @property
    def candidates(self) -> list[LocationCandidate]:
        return self._canonical

    @classmethod
    def load_seed(cls, path: str | Path) -> "AliasIndex":
        seed = Path(path)
        if not seed.exists():
            return cls([])
        records = json.loads(seed.read_text(encoding="utf-8"))
        return cls(records if isinstance(records, list) else [])

    def lookup(self, query: str) -> list[LocationCandidate]:
        """Exact alias/canonical match first, then substring on canonical names."""
        key = normalize(query)
        if not key:
            return []
        exact = self._aliases.get(key)
        if exact is not None:
            return [exact]
        partial = [
            c.model_copy(update={"confidence": _SUBSTRING_CONFIDENCE})
            for c in self._canonical
            if key in normalize(c.name)
        ]
        return partial

    def nearest(self, latitude: float, longitude: float, max_km: float = 100.0) -> LocationCandidate | None:
        """Offline nearest city (used by reverse resolution before the geocoder)."""
        from app.services.location.station_index import haversine_km

        best: LocationCandidate | None = None
        best_distance = float("inf")
        for candidate in self._canonical:
            distance = haversine_km(latitude, longitude, candidate.latitude, candidate.longitude)
            if distance < best_distance:
                best, best_distance = candidate, distance
        if best is None or best_distance > max_km:
            return None
        return best.model_copy(update={"confidence": 0.7})