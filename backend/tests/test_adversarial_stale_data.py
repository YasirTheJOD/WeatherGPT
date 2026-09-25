"""Stale + corrupt data drills — surfaced, never hidden.

Semantics under test (see services/validation/validator.py):

  - **Corrupt** (impossible values, inverted min/max) is a hard error: the
    provider result is discarded and the chain moves to the next provider.
  - **Stale** is a warning: the data is still served, with the age carried in
    provenance and the warning in the validation report. It is never silently
    presented as fresh, and it never blanks the demo.
"""

from datetime import datetime

import pytest

from app.domain.models import ForecastDay
from app.providers.base import LocationQuery, ProviderRegistry, ProviderUnavailable
from app.services.validation.validator import ValidationService

from tests.chat_stubs import (
    StubRegistry,
    done_event,
    make_client,
    observation,
    parse_sse,
    provenance,
    stale_observation,
)

LOCATION = LocationQuery(latitude=22.57, longitude=88.36, city_name="Kolkata")


class StubProvider:
    """A provider that serves exactly what it was handed."""

    def __init__(self, provider_id: str, *, observation=None, forecast=None, fail=False):
        self.provider_id = provider_id
        self.name = provider_id
        self._observation = observation
        self._forecast = forecast or []
        self.fail = fail

    def is_configured(self) -> bool:
        return True

    async def current_weather(self, location):
        if self.fail:
            raise ProviderUnavailable(f"{self.provider_id} is down")
        return self._observation

    async def daily_forecast(self, location, days: int = 7):
        if self.fail:
            raise ProviderUnavailable(f"{self.provider_id} is down")
        return self._forecast


def _registry(*providers) -> ProviderRegistry:
    return ProviderRegistry(list(providers), validator=ValidationService())


# --- corrupt payloads are discarded ----------------------------------------


async def test_corrupt_provider_is_discarded_and_the_next_one_wins():
    bad = StubProvider("bad", observation=observation(temperature_c=999.0))
    good = StubProvider("good", observation=observation(temperature_c=30.0))
    obs, provider_id, report = await _registry(bad, good).current_weather(LOCATION)

    assert provider_id == "good"
    assert obs.temperature_c == 30.0
    assert report.valid is True


async def test_all_providers_corrupt_raises_instead_of_serving_garbage():
    bad1 = StubProvider("bad1", observation=observation(humidity_pct=150.0))
    bad2 = StubProvider("bad2", observation=observation(pressure_hpa=10.0))
    with pytest.raises(ProviderUnavailable):
        await _registry(bad1, bad2).current_weather(LOCATION)


async def test_inverted_forecast_is_discarded():
    inverted = [
        ForecastDay(date="2026-09-07", tmax_c=20.0, tmin_c=30.0, provenance=provenance())
    ]
    good = [ForecastDay(date="2026-09-07", tmax_c=31.0, tmin_c=25.0, provenance=provenance())]
    _forecast, provider_id, report = await _registry(
        StubProvider("bad", forecast=inverted),
        StubProvider("good", forecast=good),
    ).daily_forecast(LOCATION)

    assert provider_id == "good"
    assert report.valid is True


# --- stale data is surfaced -------------------------------------------------


async def test_stale_observation_is_served_with_a_warning_not_hidden():
    stale = StubProvider("stale", observation=stale_observation())
    obs, provider_id, report = await _registry(stale).current_weather(LOCATION)

    assert provider_id == "stale"          # still served — the demo continues
    assert report.valid is True             # staleness alone is not fatal
    issue = next(i for i in report.issues if i.code == "stale")
    assert issue.level == "warning"
    assert obs.provenance.ttl_seconds == 300


async def test_the_weather_endpoint_surfaces_staleness_in_the_report():
    client = make_client(registry=_registry(StubProvider("stale", observation=stale_observation())))
    resp = client.get("/api/v1/weather/current", params={"lat": 22.57, "lon": 88.36})

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_used"] == "stale"
    assert any(i["code"] == "stale" for i in body["validation"]["issues"])
    # The age travels with the payload, so the UI can show "as of".
    assert body["observation"]["provenance"]["ttl_seconds"] == 300


def test_chat_keeps_answering_from_stale_data_and_carries_the_timestamp():
    client = make_client(registry=StubRegistry(stale=True))
    resp = client.post("/api/v1/chat", json={"message": "weather in Kolkata"})
    done = done_event(parse_sse(resp.text))

    assert "Right now in Kolkata" in done["text"]
    assert done["provenance_check"]["verified"] is True

    fetched_at = datetime.fromisoformat(done["observation"]["provenance"]["fetched_at"])
    age_seconds = (datetime.now(fetched_at.tzinfo) - fetched_at).total_seconds()
    assert age_seconds > 60 * 60  # an hour old, and we say so rather than hiding it
