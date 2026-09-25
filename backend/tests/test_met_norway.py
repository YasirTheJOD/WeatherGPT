"""MET Norway provider tests — the fixture is a captured real response
(see fixtures/README.md). No network in tests; an optional live test runs only
when RUN_LIVE_TESTS=1.

Expected values were derived from the fixture by an independent aggregation
(IST bucketing, finest-period precipitation), not by re-running provider code,
so a change in the provider's bucketing shows up here.
"""

import os

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import LocationQuery, ProviderRegistry, ProviderUnavailable
from app.providers.weather.met_norway import MetNorwayProvider, _symbol_text
from app.providers.weather.open_meteo import OpenMeteoProvider
from tests.conftest import load_fixture

KOLKATA = LocationQuery(latitude=22.57, longitude=88.36, city_name="Kolkata")

FIXTURE = "met_norway_kolkata_compact.json"


def _provider(fixture_name: str = FIXTURE, recorded: list | None = None) -> MetNorwayProvider:
    settings = Settings(met_norway_base_url="https://api.met.no")

    def handler(request: httpx.Request) -> httpx.Response:
        if recorded is not None:
            recorded.append(request)
        return httpx.Response(200, json=load_fixture(fixture_name))

    return MetNorwayProvider(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler=handler),
            base_url=settings.met_norway_base_url,
        ),
    )


async def test_current_weather_parses_captured_response():
    obs = await _provider().current_weather(KOLKATA)

    assert obs.temperature_c == 25.2
    assert obs.humidity_pct == 96.3
    assert obs.wind_speed_kmph == 16.6  # 4.6 m/s -> km/h
    assert obs.wind_direction == "ESE"  # 104.6 degrees
    assert obs.pressure_hpa == 1008.1
    assert obs.condition_text == "Cloudy"  # first entry's next_1_hours symbol
    assert obs.observed_at is not None
    # MET Norway publishes symbol codes, not WMO codes — never invented.
    assert obs.weather_code is None
    assert obs.rainfall_24h_mm == 7.0
    # This one is a forecast for the *coming* 24h, not an observation.
    assert obs.rainfall_basis == "forecast_24h"
    assert obs.provenance.source_id == "met-no"
    assert obs.provenance.authoritative is False
    assert obs.provenance.ttl_seconds == 300
    assert obs.provenance.raw_endpoint and "locationforecast" in obs.provenance.raw_endpoint


async def test_daily_forecast_buckets_into_local_days():
    forecast = await _provider().daily_forecast(KOLKATA, days=7)

    assert [day.date for day in forecast] == [
        "2026-09-25",
        "2026-09-26",
        "2026-09-27",
        "2026-09-28",
        "2026-09-29",
        "2026-09-30",
        "2026-10-01",
    ]
    # Day 1 is partial: the capture starts at 20:30 IST.
    assert (forecast[0].tmax_c, forecast[0].tmin_c) == (25.9, 25.2)
    assert forecast[0].rainfall_mm == 2.5
    assert forecast[0].condition_text == "Cloudy"

    assert (forecast[1].tmax_c, forecast[1].tmin_c) == (31.6, 25.3)
    assert forecast[1].rainfall_mm == 4.5
    assert forecast[1].condition_text == "Rain showers"  # majority rainshowers_day
    assert forecast[1].humidity_pct == 85.1
    assert forecast[1].wind_speed_kmph == 20.5

    assert (forecast[2].tmax_c, forecast[2].tmin_c) == (31.5, 26.0)
    assert forecast[2].rainfall_mm == 3.5
    assert forecast[2].condition_text == "Clear sky"  # majority clearsky_night

    assert all(day.provenance.source_id == "met-no" for day in forecast)
    assert all(day.provenance.ttl_seconds == 1800 for day in forecast)


async def test_daily_forecast_respects_the_days_limit():
    forecast = await _provider().daily_forecast(KOLKATA, days=2)
    assert [day.date for day in forecast] == ["2026-09-25", "2026-09-26"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("clearsky_night", "Clear sky"),
        ("rainshowers_day", "Rain showers"),
        ("partlycloudy_polartwilight", "Partly cloudy"),
        ("heavyrainandthunder", "Heavy rain and thunder"),
        ("some_new_code", "Some new code"),
    ],
)
def test_symbol_text_folds_variants_and_never_drops_a_code(code, expected):
    assert _symbol_text(code) == expected


def test_symbol_text_passes_through_none():
    assert _symbol_text(None) is None


async def test_requests_identify_the_app_and_round_coordinates():
    """MET Norway's terms require a descriptive User-Agent and 4-decimal coords."""
    recorded: list[httpx.Request] = []
    provider = _provider(recorded=recorded)
    await provider.current_weather(
        LocationQuery(latitude=22.572645, longitude=88.363892)
    )

    request = recorded[0]
    assert request.url.params["lat"] == "22.5726"
    assert request.url.params["lon"] == "88.3639"
    assert "locationforecast/2.0/compact" in str(request.url)


async def test_default_client_sends_the_configured_user_agent():
    # The terms require this header; without a client override it must be set.
    provider = MetNorwayProvider(Settings())
    try:
        agent = provider._client.headers["User-Agent"]
    finally:
        await provider._client.aclose()
    assert "WeatherGPT" in agent
    assert "github.com" in agent  # a contact, not a generic default library string


async def test_http_429_becomes_provider_unavailable():
    """The exact production failure: Open-Meteo answers 429 to shared egress."""
    settings = Settings(met_norway_base_url="https://api.met.no")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(429, json={"reason": "Too Many Requests"})
    )
    provider = MetNorwayProvider(
        settings,
        client=httpx.AsyncClient(
            transport=transport, base_url=settings.met_norway_base_url
        ),
    )

    with pytest.raises(ProviderUnavailable) as exc:
        await provider.current_weather(KOLKATA)
    assert "429" in str(exc.value)


async def test_empty_timeseries_is_unavailable():
    settings = Settings(met_norway_base_url="https://api.met.no")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(
            200, json={"type": "Feature", "properties": {"timeseries": []}}
        )
    )
    provider = MetNorwayProvider(
        settings,
        client=httpx.AsyncClient(
            transport=transport, base_url=settings.met_norway_base_url
        ),
    )

    with pytest.raises(ProviderUnavailable):
        await provider.daily_forecast(KOLKATA)


async def test_chain_falls_through_to_met_norway_when_open_meteo_is_rate_limited():
    """Regression: a 429 from the first fallback must not take the weather down.

    This is the measured 2026-09-25 production failure — the chain has to serve
    the second keyless provider instead of raising.
    """
    om_settings = Settings(open_meteo_base_url="https://api.open-meteo.com")
    rate_limited = OpenMeteoProvider(
        om_settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                handler=lambda req: httpx.Response(429, json={"reason": "Too Many Requests"})
            ),
            base_url=om_settings.open_meteo_base_url,
        ),
    )

    registry = ProviderRegistry([rate_limited, _provider()])
    obs, provider_id, report = await registry.current_weather(KOLKATA)

    assert provider_id == "met-no"
    assert obs.temperature_c == 25.2
    assert report.valid is True

    forecast, forecast_provider, _ = await registry.daily_forecast(KOLKATA, days=7)
    assert forecast_provider == "met-no"
    assert len(forecast) == 7


def test_app_provider_chain_wires_met_norway_after_open_meteo():
    """The chain order is the preference policy — pin it, don't infer it."""
    from app.main import build_registry

    registry = build_registry(Settings())
    assert [provider.provider_id for provider in registry.providers] == [
        "imd",
        "open-meteo",
        "met-no",
    ]


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="network test; set RUN_LIVE_TESTS=1 to run",
)
async def test_live_met_norway():
    provider = MetNorwayProvider(Settings())
    obs = await provider.current_weather(KOLKATA)
    assert obs.temperature_c is not None
    assert obs.condition_text
    assert obs.provenance.fetched_at is not None

    forecast = await provider.daily_forecast(KOLKATA, days=7)
    assert len(forecast) == 7
    assert forecast[0].tmax_c is not None
