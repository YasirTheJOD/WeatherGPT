"""POST /chat SSE endpoint tests — grounded streaming, Hinglish, disambiguation,
candidate picks, and failure resilience (LLM/provider outages → fallback)."""

import json
from datetime import datetime, timezone

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


def _provenance(source_name="Open-Meteo"):
    return Provenance(
        source_id="open-meteo",
        source_name=source_name,
        fetched_at=datetime.now(timezone.utc),
    )


def _observation(name="Kolkata") -> WeatherObservation:
    return WeatherObservation(
        latitude=22.57,
        longitude=88.36,
        location_name=name,
        temperature_c=29.4,
        humidity_pct=78.0,
        wind_speed_kmph=12.6,
        wind_direction="S",
        pressure_hpa=1008.0,
        condition_text="Overcast",
        rainfall_24h_mm=2.3,
        provenance=_provenance(),
    )


def _forecast() -> list[ForecastDay]:
    return [
        ForecastDay(
            date="2026-09-07",
            tmax_c=32.0,
            tmin_c=25.0,
            condition_text="Overcast",
            rainfall_mm=4.5,
            provenance=_provenance(),
        ),
        ForecastDay(
            date="2026-09-08",
            tmax_c=31.0,
            tmin_c=24.0,
            condition_text="Partly cloudy",
            rainfall_mm=None,
            provenance=_provenance(),
        ),
    ]


class StubRegistry:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def current_weather(self, location, use_cache=True):
        self.calls.append(("current", location.city_name or ""))
        if self.fail:
            raise ProviderUnavailable("all weather providers failed (test)")
        return _observation(location.city_name or "Kolkata"), "open-meteo", ValidationReport(valid=True)

    async def daily_forecast(self, location, days=7, use_cache=True):
        self.calls.append(("forecast", location.city_name or ""))
        if self.fail:
            raise ProviderUnavailable("all weather providers failed (test)")
        return _forecast(), "open-meteo", ValidationReport(valid=True)


class StubAlerts:
    def __init__(self, summaries: list[AlertSummary] | None = None, fail: bool = False):
        self.summaries = summaries or []
        self.fail = fail

    async def fetch_nearby(self, lat, lng, radius_km=20):
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
            description="Heavy rain expected over the next 24 hours.",
            instruction="Avoid waterlogged areas; do not drive through flooded roads.",
            provenance=_provenance("SACHET — NDMA National Disaster Alert Portal"),
        )


class StubResolver:
    """Echoes the query back as the candidate name (like a real geocoder)."""

    def __init__(self, ambiguous: bool = False, empty: bool = False):
        self.ambiguous = ambiguous
        self.empty = empty

    async def search(self, query, limit=8):
        if self.empty:
            return ResolveResult(query=query, normalized=query, candidates=[])
        if self.ambiguous:
            return ResolveResult(
                query=query,
                normalized=query,
                ambiguous=True,
                candidates=[
                    LocationCandidate(
                        name=query.title(),
                        state="Uttarakhand",
                        country_code="IN",
                        latitude=29.5,
                        longitude=78.5,
                        source="aliases",
                        confidence=0.71,
                    ),
                    LocationCandidate(
                        name=query.title(),
                        state="Uttar Pradesh",
                        country_code="IN",
                        latitude=28.6,
                        longitude=77.8,
                        source="open-meteo",
                        confidence=0.68,
                    ),
                ],
            )
        return ResolveResult(
            query=query,
            normalized=query,
            candidates=[
                LocationCandidate(
                    name=query.title(),
                    state="Test",
                    country_code="IN",
                    latitude=22.57,
                    longitude=88.36,
                    source="aliases",
                    confidence=0.99,
                )
            ],
        )


class FailingLLM:
    provider_id = "fail"
    name = "Failing LLM (test)"

    def is_configured(self) -> bool:
        return True

    async def grounded_response(self, evidence, user_message, language="en"):
        raise ProviderUnavailable("llm provider exploded (test)")


def _client(registry=None, resolver=None, alerts=None, llm=None) -> TestClient:
    app = create_app(Settings())
    app.state.registry = registry or StubRegistry()
    app.state.location_resolver = resolver or StubResolver()
    app.state.alerts = alerts or StubAlerts()
    if llm is not None:
        app.state.llm = llm
    return TestClient(app)


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        events.append((event, json.loads("\n".join(data_lines))))
    return events


def done_event(events) -> dict:
    return next(d for e, d in events if e == "done")


# --- happy paths ------------------------------------------------------------


def test_chat_current_weather_streams_grounded_answer():
    client = _client()
    resp = client.post(
        "/api/v1/chat", json={"message": "What is the weather in Kolkata right now?"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(resp.text)
    names = [e for e, _ in events]
    assert names[0] == "meta"
    assert "delta" in names  # token streaming happened
    assert names[-1] == "done"

    done = done_event(events)
    assert done["intent"] == "current_weather"
    assert "Right now in Kolkata" in done["text"]
    assert done["observation"]["temperature_c"] == 29.4
    assert done["location"]["name"] == "Kolkata"
    assert done["source_name"] == "Open-Meteo"
    assert done["provenance_check"]["verified"] is True
    assert done["suggestions"]


def test_chat_contracted_opening_prompt_resolves_the_place():
    """The exact string in the demo script (ARCHITECTURE §10 scenario 1).

    Regression: contraction folding — "What's" must not leak a stray "s" into
    the place name, or the headline demo prompt answers "I couldn't find a
    place called 's kolkata'".
    """
    client = _client()
    resp = client.post(
        "/api/v1/chat", json={"message": "What's the weather in Kolkata right now?"}
    )
    done = done_event(parse_sse(resp.text))
    assert done["location"]["name"] == "Kolkata"
    assert "Right now in Kolkata" in done["text"]
    assert done["provenance_check"]["verified"] is True


def test_chat_hinglish_forecast_grounds_day_two():
    client = _client()
    resp = client.post(
        "/api/v1/chat",
        json={"message": "Kal shaam Mumbai mein baarish hogi kya?"},
    )
    done = done_event(parse_sse(resp.text))
    assert done["intent"] == "forecast"
    assert "Tomorrow evening" in done["text"]
    assert "Mumbai" in done["text"]
    assert done["forecast"][1]["date"] == "2026-09-08"  # day 2 is the target
    assert done["provenance_check"]["verified"] is True


def test_chat_alerts_uses_current_location_and_fetches_cap_detail():
    current = LocationCandidate(
        name="Kolkata",
        state="West Bengal",
        country_code="IN",
        latitude=22.57,
        longitude=88.36,
        source="device-gps",
        confidence=0.9,
    )
    summary = AlertSummary(
        identifier="CAP-1",
        title="Heavy Rain",
        category="Met",
        provenance=_provenance("SACHET — NDMA National Disaster Alert Portal"),
    )
    client = _client(alerts=StubAlerts(summaries=[summary]))
    resp = client.post(
        "/api/v1/chat",
        json={
            "message": "any alerts near me?",
            "current_location": current.model_dump(mode="json"),
        },
    )
    done = done_event(parse_sse(resp.text))
    assert done["intent"] == "alerts"
    assert "official warning for Kolkata" in done["text"]
    assert done["alerts"][0]["event"] == "Heavy Rain"
    assert done["alerts"][0]["severity"] == "Severe"
    assert done["source_name"] == "SACHET — NDMA National Disaster Alert Portal"


def test_chat_explicit_candidate_answers_with_intent():
    client = _client()
    candidate = {
        "name": "Mumbai",
        "state": "Maharashtra",
        "country_code": "IN",
        "latitude": 19.07,
        "longitude": 72.87,
        "source": "aliases",
        "confidence": 0.9,
    }
    resp = client.post(
        "/api/v1/chat",
        json={"intent": "forecast", "candidate": candidate},
    )
    done = done_event(parse_sse(resp.text))
    assert done["intent"] == "forecast"
    assert done["location"]["name"] == "Mumbai"
    assert done["forecast"]
    assert "Mumbai" in done["text"]


# --- conversational outcomes ------------------------------------------------


def test_chat_disambiguation_offers_candidates():
    client = _client(resolver=StubResolver(ambiguous=True))
    resp = client.post("/api/v1/chat", json={"message": "weather in Ranipur"})
    done = done_event(parse_sse(resp.text))
    assert "Which one do you mean" in done["text"]
    assert len(done["candidates"]) == 2
    assert done["observation"] is None


def test_chat_unknown_place_says_so():
    client = _client(resolver=StubResolver(empty=True))
    resp = client.post("/api/v1/chat", json={"message": "weather in xyz"})
    done = done_event(parse_sse(resp.text))
    assert "couldn't find a place called" in done["text"]
    assert done["suggestions"]


def test_chat_asks_for_place_when_none_given():
    client = _client()
    resp = client.post("/api/v1/chat", json={"message": "What is the weather?"})
    done = done_event(parse_sse(resp.text))
    assert "Which place are you asking about" in done["text"]


def test_chat_requires_message_or_candidate():
    client = _client()
    resp = client.post("/api/v1/chat", json={})
    assert resp.status_code == 422


# --- resilience -------------------------------------------------------------


def test_provider_outage_answers_gracefully_via_gap():
    """A data-API outage must NOT kill the demo: the responder says so
    plainly instead of streaming an error event."""
    client = _client(registry=StubRegistry(fail=True))
    resp = client.post("/api/v1/chat", json={"message": "weather in Kolkata"})
    events = parse_sse(resp.text)
    names = [e for e, _ in events]
    assert "error" not in names
    done = done_event(events)
    assert "I don't have live data for that right now" in done["text"]
    assert done["observation"] is None


def test_llm_outage_falls_back_to_deterministic_responder():
    client = _client(llm=FailingLLM())
    resp = client.post("/api/v1/chat", json={"message": "weather in Kolkata"})
    events = parse_sse(resp.text)
    meta_generating = next(d for e, d in events if e == "meta" and d.get("status") == "generating")
    assert meta_generating["fallback"] is True
    done = done_event(events)
    assert "Right now in Kolkata" in done["text"]
    assert done["provenance_check"]["verified"] is True