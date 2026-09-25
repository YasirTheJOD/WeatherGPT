"""Station index tests — haversine math, nearest-station resolution, search."""

from app.domain.models import Station
from app.services.location.station_index import StationIndex, haversine_km


def _index() -> StationIndex:
    return StationIndex(
        [
            Station(station_code="KOL", name="Kolkata", state="West Bengal", latitude=22.57, longitude=88.36),
            Station(station_code="DEL", name="Delhi", state="Delhi", latitude=28.61, longitude=77.21),
            Station(station_code="BOM", name="Mumbai", state="Maharashtra", latitude=19.08, longitude=72.88),
        ]
    )


def test_haversine_zero_and_known_distance():
    assert haversine_km(22.57, 88.36, 22.57, 88.36) == 0.0
    distance = haversine_km(22.57, 88.36, 28.61, 77.21)  # Kolkata -> Delhi
    assert 1300 < distance < 1600


def test_nearest_resolves_correct_station():
    index = _index()
    assert index.nearest(22.57, 88.36).station_code == "KOL"
    assert index.nearest(28.61, 77.21).station_code == "DEL"
    assert index.nearest(19.08, 72.88).station_code == "BOM"


def test_nearest_returns_none_outside_max_km():
    index = _index()
    assert index.nearest(-33.8, 151.2) is None  # Sydney
    assert index.nearest(30.0, 90.0, max_km=10) is None  # within India but far from all


def test_search_by_name_and_state():
    index = _index()
    assert [s.station_code for s in index.search("kolk")] == ["KOL"]
    assert [s.station_code for s in index.search("bengal")] == ["KOL"]
    assert len(index.search("")) == 0
    assert index.search("xyz") == []