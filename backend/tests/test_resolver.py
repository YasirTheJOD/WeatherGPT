"""Location resolver tests — stubbed geocoder, real alias seed."""

from app.domain.models import LocationCandidate, Station
from app.services.location.alias_index import AliasIndex
from app.services.location.resolver import LocationResolver
from app.services.location.station_index import StationIndex
from tests.conftest import DATA_DIR


class StubGeocoder:
    """Deterministic geocoder: returns configured candidates."""

    def __init__(self, candidates: list[LocationCandidate]):
        self._candidates = candidates
        self.reverse_result: LocationCandidate | None = None
        self.calls = 0

    async def search(self, query: str, limit: int = 8) -> list[LocationCandidate]:
        self.calls += 1
        return self._candidates[:limit]

    async def reverse(self, latitude: float, longitude: float) -> LocationCandidate | None:
        return self.reverse_result


def _ranipur_duplicates() -> list[LocationCandidate]:
    return [
        LocationCandidate(name="Rānīpur", state="Uttar Pradesh", country_code="IN",
                          latitude=25.25, longitude=79.06, source="open-meteo", confidence=0.6),
        LocationCandidate(name="Rānīpur", state="Madhya Pradesh", country_code="IN",
                          latitude=22.58, longitude=77.98, source="open-meteo", confidence=0.6),
    ]


def _resolver(geocoder) -> LocationResolver:
    return LocationResolver(
        alias_index=AliasIndex.load_seed(DATA_DIR / "cities_seed.json"),
        geocoder=geocoder,
        reverse_geocoder=geocoder,
    )


async def test_alias_wins_over_geocoder_for_known_city():
    geo = StubGeocoder(
        [LocationCandidate(name="Kolkata", country_code="IN", latitude=22.56, longitude=88.36,
                           source="open-meteo", confidence=0.6)]
    )
    result = await _resolver(geo).search("calcutta")
    assert result.candidates[0].name == "Kolkata"
    assert result.candidates[0].source == "aliases"
    assert result.candidates[0].confidence == 0.95  # deduped, alias kept
    assert result.ambiguous is False
    assert result.normalized == "calcutta"


async def test_ambiguity_flag_for_duplicate_place_names():
    geo = StubGeocoder(_ranipur_duplicates())
    result = await _resolver(geo).search("ranipur")
    assert result.ambiguous is True
    assert len(result.candidates) == 2


async def test_geocoder_failure_degrades_to_aliases_only():
    class BrokenGeocoder:
        async def search(self, query, limit=8):
            raise RuntimeError("down")

        async def reverse(self, latitude, longitude):
            return None

    result = await _resolver(BrokenGeocoder()).search("delhi")
    assert result.candidates[0].name == "Delhi"
    assert result.candidates[0].source == "aliases"
    assert result.ambiguous is False


async def test_reverse_uses_offline_nearest_city_first():
    geo = StubGeocoder([])
    result = await _resolver(geo).search("something-unknown")
    resolver = _resolver(geo)
    candidate = await resolver.reverse(22.57, 88.36)
    assert candidate is not None
    assert candidate.name == "Kolkata"
    assert candidate.source == "aliases"
    assert geo.calls == 1  # only the search above hit the geocoder; reverse was offline


def test_nearest_station_delegates_to_index():
    index = StationIndex(
        [Station(station_code="42182", name="KOLKATA (ALIPORE)", latitude=22.57, longitude=88.36)]
    )
    resolver = LocationResolver(
        alias_index=AliasIndex([]), geocoder=StubGeocoder([]),
        reverse_geocoder=StubGeocoder([]), station_index=index,
    )
    candidate = resolver.nearest_station(22.57, 88.36)
    assert candidate is not None
    assert candidate.source == "imd-station"
    assert candidate.confidence == 0.9


def test_nearest_station_none_outside_range():
    resolver = LocationResolver(
        alias_index=AliasIndex([]), geocoder=StubGeocoder([]),
        reverse_geocoder=StubGeocoder([]), station_index=None,
    )
    assert resolver.nearest_station(22.57, 88.36) is None