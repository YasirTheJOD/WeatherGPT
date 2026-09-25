"""Open-Meteo provider tests — fixtures are captured real responses
(see fixtures/README.md). No network in tests; an optional live test runs
only when RUN_LIVE_TESTS=1."""

import os

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import LocationQuery
from app.providers.weather.open_meteo import OpenMeteoProvider
from tests.conftest import load_fixture

KOLKATA = LocationQuery(latitude=22.57, longitude=88.36, city_name="Kolkata")


def _provider_with(fixture_name: str) -> OpenMeteoProvider:
    settings = Settings(open_meteo_base_url="https://api.open-meteo.com")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture(fixture_name))
    )
    return OpenMeteoProvider(
        settings,
        client=httpx.AsyncClient(transport=transport, base_url=settings.open_meteo_base_url),
    )


async def test_current_weather_parses_captured_response():
    provider = _provider_with("open_meteo_current.json")
    obs = await provider.current_weather(KOLKATA)
    assert obs.temperature_c == 28.4
    assert obs.humidity_pct == 90
    assert obs.wind_speed_kmph == 5.2
    assert obs.condition_text == "Overcast"  # WMO code 3
    assert obs.provenance.source_id == "open-meteo"
    assert obs.provenance.authoritative is False
    assert obs.observed_at is not None


async def test_daily_forecast_parses_captured_response():
    provider = _provider_with("open_meteo_daily.json")
    forecast = await provider.daily_forecast(KOLKATA, days=7)
    assert len(forecast) == 7
    assert forecast[0].date == "2026-09-06"
    assert forecast[0].tmax_c == 32.8
    assert forecast[1].rainfall_mm == 13.4
    assert forecast[1].condition_text == "Thunderstorm with light hail"  # WMO 96
    assert all(day.provenance.source_id == "open-meteo" for day in forecast)


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="network test; set RUN_LIVE_TESTS=1 to run",
)
async def test_live_open_meteo():
    provider = OpenMeteoProvider(Settings())
    obs = await provider.current_weather(KOLKATA)
    assert obs.temperature_c is not None
    assert obs.provenance.fetched_at is not None