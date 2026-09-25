"""Shared chat-pipeline doubles for the Phase 6 adversarial test matrix.

These are deliberately small and honest about failure: every stub can be told
to fail, to lie, or to return stale/corrupt payloads. Import them from the
``test_adversarial_*.py`` modules.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import (
    Alert,
    AlertSummary,
    ForecastDay,
    LocationCandidate,
    Provenance,
    ResolveResult,
    ValidationReport,
    WeatherObservation,
)
from app.main import create_app
from app.providers.base import ProviderUnavailable

NOW = datetime.now(timezone.utc)


# --- builders ---------------------------------------------------------------


def provenance(
    source_name: str = "Open-Meteo",
    *,
    source_id: str = "open-meteo",
    authoritative: bool = False,
    fetched_at: datetime | None = None,
    ttl_seconds: int = 300,
) -> Provenance:
    return Provenance(
        source_id=source_id,
        source_name=source_name,
        authoritative=authoritative,
        fetched_at=fetched_at or NOW,
        ttl_seconds=ttl_seconds,
    )


def observation(
    name: str = "Kolkata",
    *,
    latitude: float = 22.57,
    longitude: float = 88.36,
    temperature_c: float = 29.4,
    humidity_pct: float = 78.0,
    wind_speed_kmph: float = 12.6,
    pressure_hpa: float = 1008.0,
    rainfall_24h_mm: float = 2.3,
    condition_text: str = "Overcast",
    fetched_at: datetime | None = None,
    ttl_seconds: int = 300,
) -> WeatherObservation:
    return WeatherObservation(
        latitude=latitude,
        longitude=longitude,
        location_name=name,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        wind_speed_kmph=wind_speed_kmph,
        wind_direction="S",
        pressure_hpa=pressure_hpa,
        condition_text=condition_text,
        rainfall_24h_mm=rainfall_24h_mm,
        provenance=provenance(fetched_at=fetched_at, ttl_seconds=ttl_seconds),
    )


def forecast(*, fetched_at: datetime | None = None, ttl_seconds: int = 600) -> list[ForecastDay]:
    return [
        ForecastDay(
            date="2026-09-07",
            tmax_c=32.0,
            tmin_c=25.0,
            condition_text="Overcast",
            rainfall_mm=4.5,
            provenance=provenance(fetched_at=fetched_at, ttl_seconds=ttl_seconds),
        ),
        ForecastDay(
            date="2026-09-08",
            tmax_c=31.0,
            tmin_c=24.0,
            condition_text="Partly cloudy",
            rainfall_mm=None,
            provenance=provenance(fetched_at=fetched_at, ttl_seconds=ttl_seconds),
        ),
    ]


def stale_observation(name: str = "Kolkata") -> WeatherObservation:
    """An observation fetched two hours ago against a 5-minute TTL."""
    return observation(name, fetched_at=NOW - timedelta(hours=2), ttl_seconds=300)


def candidate(name: str = "Kolkata", **overrides) -> LocationCandidate:
    base = {
        "name": name,
        "state": "Test",
        "country_code": "IN",
        "latitude": 22.57,
        "longitude": 88.36,
        "source": "aliases",
        "confidence": 0.99,
    }
    base.update(overrides)
    return LocationCandidate(**base)


# --- provider doubles -------------------------------------------------------


class StubRegistry:
    """Returns a fresh observation/forecast for whatever place was resolved."""

    def __init__(self, *, fail: bool = False, stale: bool = False):
        self.fail = fail
        self.stale = stale
        self.calls: list[tuple[str, str]] = []

    async def current_weather(self, location, use_cache: bool = True):
        self.calls.append(("current", location.city_name or ""))
        if self.fail:
            raise ProviderUnavailable("all weather providers failed (test)")
        obs = (
            stale_observation(location.city_name or "Kolkata")
            if self.stale
            else observation(
                location.city_name or "Kolkata",
                latitude=location.latitude,
                longitude=location.longitude,
            )
        )
        return obs, "open-meteo", ValidationReport(valid=True)

    async def daily_forecast(self, location, days: int = 7, use_cache: bool = True):
        self.calls.append(("forecast", location.city_name or ""))
        if self.fail:
            raise ProviderUnavailable("all weather providers failed (test)")
        return forecast(), "open-meteo", ValidationReport(valid=True)


class StubAlerts:
    def __init__(self, summaries: list[AlertSummary] | None = None, *, fail: bool = False):
        self.summaries = summaries or []
        self.fail = fail

    async def fetch_nearby(self, lat, lng, radius_km: int = 20):
        if self.fail:
            raise ProviderUnavailable("sachet unavailable (test)")
        return self.summaries

    async def fetch_alert_detail(self, identifier: str) -> Alert:
        return Alert(
            identifier=identifier,
            sender="NDMA",
            event="Heavy Rain",
            severity="Severe",
            headline="Heavy to very heavy rainfall very likely",
            instruction="Avoid waterlogged areas.",
            provenance=provenance("SACHET — NDMA National Disaster Alert Portal"),
        )


class EchoResolver:
    """A geocoder that echoes the query back as the candidate name."""

    def __init__(self, *, ambiguous: bool = False, empty: bool = False):
        self.ambiguous = ambiguous
        self.empty = empty

    async def search(self, query, limit: int = 8):
        if self.empty:
            return ResolveResult(query=query, normalized=query, candidates=[])
        if self.ambiguous:
            return ResolveResult(
                query=query,
                normalized=query,
                ambiguous=True,
                candidates=[
                    candidate(query.title(), state="Uttarakhand", latitude=29.5, longitude=78.5),
                    candidate(query.title(), state="Uttar Pradesh", latitude=28.6, longitude=77.8),
                ],
            )
        return ResolveResult(
            query=query,
            normalized=query,
            candidates=[candidate(query.title())],
        )


class FixedResolver:
    """A geocoder that normalizes any query to canonical, fixed places.

    Used by the injection drills: a hostile message may pollute the raw place
    string, but a real geocoder still returns clean canonical names.
    """

    def __init__(self, places: list[LocationCandidate] | None = None):
        self.places = places or [candidate("Kolkata")]

    async def search(self, query, limit: int = 8):
        return ResolveResult(query=query, normalized=query, candidates=list(self.places))


# --- LLM doubles ------------------------------------------------------------


class FailingLLM:
    """Provider outage: the expected, well-behaved failure."""

    provider_id = "failing"
    name = "Failing LLM (test)"

    def is_configured(self) -> bool:
        return True

    async def grounded_response(self, evidence, user_message, language: str = "en"):
        raise ProviderUnavailable("llm provider exploded (test)")


class ExplodingLLM:
    """A provider *bug*: an error the adapters were never expected to raise."""

    provider_id = "exploding"
    name = "Exploding LLM (test)"

    def is_configured(self) -> bool:
        return True

    async def grounded_response(self, evidence, user_message, language: str = "en"):
        raise RuntimeError("unexpected provider bug (test)")


class BlankLLM:
    """Succeeds, but returns nothing — a blank bubble is still a failure."""

    provider_id = "blank"
    name = "Blank LLM (test)"

    def is_configured(self) -> bool:
        return True

    async def grounded_response(self, evidence, user_message, language: str = "en"):
        return "   \n  "


class ScriptedLLM:
    """Returns a fixed string, however wrong. The hallucination drill."""

    provider_id = "scripted"
    name = "Scripted LLM (test)"

    def __init__(self, text: str):
        self.text = text
        self.seen_evidence = None

    def is_configured(self) -> bool:
        return True

    async def grounded_response(self, evidence, user_message, language: str = "en"):
        self.seen_evidence = evidence
        return self.text


# --- app / SSE helpers ------------------------------------------------------


def make_client(*, registry=None, resolver=None, alerts=None, llm=None) -> TestClient:
    """Build the app with every network-touching dependency stubbed out.

    Defaults are hermetic on purpose: without them a test that forgot to pass
    a stub would call the real Open-Meteo API.
    """
    app = create_app(Settings())
    app.state.registry = registry or StubRegistry()
    app.state.location_resolver = resolver or EchoResolver()
    app.state.alerts = alerts or StubAlerts()
    if llm is not None:
        app.state.llm = llm
    return TestClient(app)


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        events.append((event, json.loads("\n".join(data_lines))))
    return events


def event_names(events) -> list[str]:
    return [name for name, _ in events]


def done_event(events) -> dict:
    return next(data for name, data in events if name == "done")


def meta_event(events, status: str) -> dict:
    return next(
        data
        for name, data in events
        if name == "meta" and data.get("status") == status
    )
