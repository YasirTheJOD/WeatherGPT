"""Geocoder tests — fixtures are captured real responses (2026-09-06)."""

import httpx

from app.core.config import Settings
from app.services.location.geocoder import BigDataCloudReverseGeocoder, OpenMeteoGeocoder
from tests.conftest import load_fixture


def _search_provider(fixture_name: str) -> OpenMeteoGeocoder:
    settings = Settings()
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture(fixture_name))
    )
    return OpenMeteoGeocoder(
        settings, client=httpx.AsyncClient(transport=transport, base_url=settings.geocoding_base_url)
    )


async def test_search_kolkata_prefers_india():
    provider = _search_provider("open_meteo_geocoding_kolkata.json")
    candidates = await provider.search("Kolkata")
    assert len(candidates) == 1
    city = candidates[0]
    assert city.name == "Kolkata"
    assert city.country_code == "IN"
    assert city.country == "India"
    assert city.state == "West Bengal"
    assert city.source == "open-meteo"
    assert city.confidence == 0.6
    assert abs(city.latitude - 22.56263) < 1e-4


async def test_search_ranipur_filters_to_india():
    provider = _search_provider("open_meteo_geocoding_ranipur.json")
    candidates = await provider.search("Ranipur")
    assert len(candidates) == 2  # Pakistan/Bangladesh matches filtered out
    assert all(c.country_code == "IN" for c in candidates)
    names = {c.name for c in candidates}
    assert "Rānīpur" in names  # diacritics preserved at geocoder level


async def test_reverse_geocode_kolkata():
    settings = Settings()
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture("bigdatacloud_reverse_kolkata.json"))
    )
    provider = BigDataCloudReverseGeocoder(
        settings, client=httpx.AsyncClient(transport=transport, base_url=settings.reverse_geocoding_base_url)
    )
    candidate = await provider.reverse(22.57, 88.36)
    assert candidate is not None
    assert candidate.name == "Kolkata"
    assert candidate.state == "West Bengal"
    assert candidate.country_code == "IN"
    assert candidate.source == "bigdatacloud"