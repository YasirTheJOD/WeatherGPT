"""Locations endpoint tests — stubbed geocoder, real alias seed + sample stations."""

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import LocationCandidate, Station
from app.services.location.alias_index import AliasIndex
from app.services.location.resolver import LocationResolver
from app.services.location.station_index import StationIndex
from tests.conftest import DATA_DIR


class StubGeocoder:
    def __init__(self, candidates, reverse_result=None):
        self._candidates = candidates
        self.reverse_result = reverse_result

    async def search(self, query, limit=8):
        return self._candidates[:limit]

    async def reverse(self, latitude, longitude):
        return self.reverse_result


def _client(geocoder, station_index=None) -> TestClient:
    from app.main import create_app

    app = create_app(Settings())
    app.state.location_resolver = LocationResolver(
        alias_index=AliasIndex.load_seed(DATA_DIR / "cities_seed.json"),
        geocoder=geocoder,
        reverse_geocoder=geocoder,
        station_index=station_index,
    )
    return TestClient(app)


def test_search_known_city_via_alias():
    client = _client(StubGeocoder([]))
    response = client.get("/api/v1/locations/search", params={"q": "calcutta"})
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is False
    assert body["candidates"][0]["name"] == "Kolkata"
    assert body["candidates"][0]["source"] == "aliases"


def test_search_ambiguous_duplicate_place_name():
    duplicates = [
        LocationCandidate(name="Rānīpur", state="Uttar Pradesh", country_code="IN",
                          latitude=25.25, longitude=79.06, source="open-meteo", confidence=0.6),
        LocationCandidate(name="Rānīpur", state="Madhya Pradesh", country_code="IN",
                          latitude=22.58, longitude=77.98, source="open-meteo", confidence=0.6),
    ]
    client = _client(StubGeocoder(duplicates))
    response = client.get("/api/v1/locations/search", params={"q": "ranipur"})
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is True
    assert len(body["candidates"]) == 2


def test_reverse_geocode_offline_nearest_city():
    client = _client(StubGeocoder([]))
    response = client.get("/api/v1/locations/reverse", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kolkata"
    assert body["source"] == "aliases"


def test_reverse_geocode_falls_back_to_geocoder():
    remote = LocationCandidate(name="Kolkata", state="West Bengal", country_code="IN",
                               latitude=22.57, longitude=88.36, source="bigdatacloud",
                               confidence=0.8)
    client = _client(StubGeocoder([], reverse_result=remote))
    # Far from any seed city -> offline nearest is None -> geocoder result.
    response = client.get("/api/v1/locations/reverse", params={"lat": 0.5, "lon": 77.5})
    assert response.status_code == 200
    assert response.json()["source"] == "bigdatacloud"


def test_reverse_geocode_404_when_unknown():
    client = _client(StubGeocoder([], reverse_result=None))
    response = client.get("/api/v1/locations/reverse", params={"lat": -33.8, "lon": 151.2})
    assert response.status_code == 404


def test_nearest_station_from_sample_index():
    index = StationIndex(
        [Station(station_code="SMPL001", name="Kolkata (sample)", latitude=22.57, longitude=88.36)]
    )
    client = _client(StubGeocoder([]), station_index=index)
    response = client.get("/api/v1/locations/nearest-station", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 200
    assert response.json()["source"] == "imd-station"


def test_nearest_station_404_without_index():
    client = _client(StubGeocoder([]), station_index=None)
    response = client.get("/api/v1/locations/nearest-station", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 404