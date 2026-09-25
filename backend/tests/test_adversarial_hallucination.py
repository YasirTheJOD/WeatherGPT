"""LLM drills — the hallucination firewall and outage resilience.

Two separate guarantees are pinned here:

1. **The firewall.** When an LLM (or a successful prompt injection) invents
   numbers, the number-provenance post-check reports every one of them, and the
   structured cards still come from the evidence bundle — a lying LLM can
   change the prose, never the data.
2. **The demo never dies.** A provider outage, a provider *bug*, or a blank
   answer all fall back to the deterministic responder over the same evidence,
   with identical provenance.
"""

from datetime import datetime, timezone

from app.domain.chat import EvidenceBundle
from app.domain.models import ForecastDay, Provenance, WeatherObservation
from app.services.response.provenance import check_provenance

from tests.chat_stubs import (
    BlankLLM,
    EchoResolver,
    ExplodingLLM,
    FailingLLM,
    ScriptedLLM,
    done_event,
    event_names,
    make_client,
    meta_event,
    parse_sse,
)


def _events(client, message: str = "weather in Kolkata"):
    resp = client.post("/api/v1/chat", json={"message": message})
    assert resp.status_code == 200
    return parse_sse(resp.text)


# --- the firewall -----------------------------------------------------------


def test_every_invented_number_is_reported():
    llm = ScriptedLLM("Right now in Kolkata: 41°C, humidity 90%, wind 300 km/h.")
    events = _events(make_client(resolver=EchoResolver(), llm=llm))
    done = done_event(events)

    assert done["provenance_check"]["verified"] is False
    assert set(done["provenance_check"]["unverified_numbers"]) == {"41", "90", "300"}
    assert done["provenance_check"]["checked_numbers"] == 3


def test_lying_llm_cannot_change_the_cards():
    llm = ScriptedLLM("Right now in Chennai: 41°C, humidity 90%.")
    done = done_event(_events(make_client(resolver=EchoResolver(), llm=llm)))

    # Cards are assembled from evidence, not from the LLM's text.
    assert done["observation"]["temperature_c"] == 29.4
    assert done["observation"]["humidity_pct"] == 78.0
    assert done["location"]["name"] == "Kolkata"
    assert done["source_name"] == "Open-Meteo"


def test_grounded_llm_text_passes_the_firewall():
    """A well-behaved LLM quoting rounded evidence values must verify."""
    llm = ScriptedLLM("Right now in Kolkata: 29°C — humidity 78%, rain 2.3 mm.")
    events = _events(make_client(resolver=EchoResolver(), llm=llm))
    done = done_event(events)

    assert done["provenance_check"]["verified"] is True
    assert done["provenance_check"]["unverified_numbers"] == []
    assert meta_event(events, "generating")["fallback"] is False


def test_calendar_labels_never_trip_the_firewall():
    evidence = EvidenceBundle(
        forecast=[
            ForecastDay(
                date="2026-09-08",
                tmax_c=31.0,
                tmin_c=24.0,
                provenance=Provenance(
                    source_id="open-meteo",
                    source_name="Open-Meteo",
                    fetched_at=datetime.now(timezone.utc),
                ),
            )
        ],
        location_name="Delhi",
        day_offset=1,
    )
    check = check_provenance("Tomorrow (Tue 8 Sep) in Delhi: high 31°, low 24°.", evidence)
    assert check.verified is True


def test_firewall_flags_a_number_off_by_more_than_rounding():
    evidence = EvidenceBundle(
        observation=WeatherObservation(
            latitude=22.57,
            longitude=88.36,
            temperature_c=29.4,
            provenance=Provenance(
                source_id="open-meteo",
                source_name="Open-Meteo",
                fetched_at=datetime.now(timezone.utc),
            ),
        )
    )
    check = check_provenance("It is 30.4°C in Kolkata.", evidence)
    assert check.verified is False
    assert check.unverified_numbers == ["30.4"]


def test_firewall_ignores_structural_zeros():
    """0 in prose ("0 mm of rain") must not be reported as fabricated."""
    evidence = EvidenceBundle(
        observation=WeatherObservation(
            latitude=22.57,
            longitude=88.36,
            rainfall_24h_mm=0.0,
            provenance=Provenance(
                source_id="open-meteo",
                source_name="Open-Meteo",
                fetched_at=datetime.now(timezone.utc),
            ),
        )
    )
    check = check_provenance("No rain: 0 mm in the last few hours.", evidence)
    assert check.verified is True


# --- outage drills ----------------------------------------------------------


def test_provider_outage_falls_back_over_the_same_evidence():
    events = _events(make_client(resolver=EchoResolver(), llm=FailingLLM()))
    assert "error" not in event_names(events)
    assert meta_event(events, "generating")["fallback"] is True

    done = done_event(events)
    assert "Right now in Kolkata" in done["text"]
    assert done["provenance_check"]["verified"] is True
    assert done["observation"]["temperature_c"] == 29.4


def test_unexpected_provider_bug_still_falls_back():
    """A provider raising something other than ProviderUnavailable must not
    kill the SSE stream (the frontend would otherwise lose the answer)."""
    events = _events(make_client(resolver=EchoResolver(), llm=ExplodingLLM()))
    assert "error" not in event_names(events)
    assert event_names(events)[-1] == "done"
    assert meta_event(events, "generating")["fallback"] is True

    done = done_event(events)
    assert done["text"].strip() != ""
    assert done["provenance_check"]["verified"] is True


def test_blank_provider_answer_falls_back():
    events = _events(make_client(resolver=EchoResolver(), llm=BlankLLM()))
    assert meta_event(events, "generating")["fallback"] is True

    done = done_event(events)
    assert done["text"].strip() != ""          # never a blank bubble
    assert "Kolkata" in done["text"]
    assert done["provenance_check"]["verified"] is True
