"""Station index — nearest-station resolution and name search.

Python nearest-neighbour over the station list is ample for a few thousand
stations; PostGIS takes over this job in Phase 3+ without changing callers.
"""

import math

from app.domain.models import Station

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class StationIndex:
    def __init__(self, stations: list[Station]):
        self._stations = list(stations)

    @property
    def stations(self) -> list[Station]:
        return self._stations

    def __len__(self) -> int:
        return len(self._stations)

    def nearest(self, latitude: float, longitude: float, max_km: float = 50.0) -> Station | None:
        best: Station | None = None
        best_distance = float("inf")
        for station in self._stations:
            distance = haversine_km(latitude, longitude, station.latitude, station.longitude)
            if distance < best_distance:
                best, best_distance = station, distance
        if best is None or best_distance > max_km:
            return None
        return best

    def search(self, query: str, limit: int = 10) -> list[Station]:
        q = query.strip().lower()
        if not q:
            return []
        matches = [
            s
            for s in self._stations
            if q in s.name.lower() or (s.state and q in s.state.lower())
        ]
        return matches[:limit]