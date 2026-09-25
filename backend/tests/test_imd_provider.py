"""IMD provider tests.

Fixtures are constructed from the field schema published in the official
API reference (https://api.imd.gov.in/public/api_reference.html) because the
live API requires a key we do not yet hold. They will be replaced by captured
real responses once access is granted — see fixtures/README.md and
docs/IMD-ACCESS.md.
"""

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import LocationQuery, ProviderUnavailable
from app.providers.weather.imd import IMDProvider
from tests.conftest import load_fixture


async def test_fails_closed_without_api_key(settings_no_imd):
    provider = IMDProvider(settings_no_imd)
    # Fails closed regardless of which gate fires first (station index vs key).
    with pytest.raises(
        ProviderUnavailable,
        match="(API key not configured|IMD station index not configured)",
    ):
        await provider.current_weather(LocationQuery(latitude=22.57, longitude=88.36))


async def test_current_weather_parses_documented_schema():
    settings = Settings(imd_api_key="test-key")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture("imd_current_wx.json"))
    )
    provider = IMDProvider(
        settings, client=httpx.AsyncClient(transport=transport, base_url=settings.imd_base_url)
    )
    obs = await provider.current_weather(
        LocationQuery(latitude=22.57, longitude=88.36, station_id="42182")
    )
    assert obs.temperature_c == 28.6
    assert obs.humidity_pct == 86
    assert obs.wind_speed_kmph == 12
    assert obs.wind_direction == "Southerly"  # code 180
    assert obs.pressure_hpa == 1008.4
    assert obs.weather_code == 63
    assert obs.condition_text == "Rain, not freezing, continuous moderate"
    assert obs.rainfall_24h_mm == 0.0
    # IMD's "Last 24 hrs Rainfall" really is an observation of the past 24h.
    assert obs.rainfall_basis == "observed_24h"
    assert obs.provenance.authoritative is True
    assert obs.provenance.source_id == "imd"
    assert obs.observed_at is not None


async def test_daily_forecast_parses_documented_schema():
    settings = Settings(imd_api_key="test-key")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture("imd_cityforecast.json"))
    )
    provider = IMDProvider(
        settings, client=httpx.AsyncClient(transport=transport, base_url=settings.imd_base_url)
    )
    forecast = await provider.daily_forecast(
        LocationQuery(latitude=22.57, longitude=88.36, station_id="42182")
    )
    assert len(forecast) == 7
    assert forecast[0].date == "2026-09-06"
    assert forecast[0].tmax_c == 31.0
    assert forecast[1].date == "2026-09-07"
    assert forecast[1].tmax_c == 30.0
    assert "rain" in forecast[1].condition_text.lower()
    assert all(day.provenance.authoritative for day in forecast)


async def test_requires_station_index_when_no_station_id():
    settings = Settings(imd_api_key="test-key")
    provider = IMDProvider(settings)
    with pytest.raises(ProviderUnavailable, match="station index not configured"):
        await provider.current_weather(LocationQuery(latitude=22.57, longitude=88.36))


async def test_resolves_nearest_station_from_index():
    from app.domain.models import Station
    from app.services.location.station_index import StationIndex

    settings = Settings(imd_api_key="test-key")
    index = StationIndex(
        [Station(station_code="42182", name="KOLKATA (ALIPORE)", latitude=22.57, longitude=88.36)]
    )
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture("imd_current_wx.json"))
    )
    provider = IMDProvider(
        settings,
        client=httpx.AsyncClient(transport=transport, base_url=settings.imd_base_url),
        station_index=index,
    )
    obs = await provider.current_weather(LocationQuery(latitude=22.57, longitude=88.36))
    assert obs.location_name == "KOLKATA (ALIPORE)"
    assert obs.provenance.raw_endpoint == "/api/v1/current_wx?id=42182"


async def test_no_station_within_range_is_unavailable():
    from app.domain.models import Station
    from app.services.location.station_index import StationIndex

    settings = Settings(imd_api_key="test-key")
    index = StationIndex(
        [Station(station_code="DEL", name="Delhi", latitude=28.61, longitude=77.21)]
    )
    provider = IMDProvider(settings, station_index=index)
    with pytest.raises(ProviderUnavailable, match="no IMD station within"):
        await provider.current_weather(LocationQuery(latitude=-33.8, longitude=151.2))