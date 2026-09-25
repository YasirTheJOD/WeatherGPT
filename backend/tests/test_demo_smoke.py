"""Tests for the Phase 8 rehearsal harness (app/scripts/demo_smoke.py).

The harness is what gates the demo laptop before the jury walks in, so its
assertions get their own coverage — a rehearsal tool that silently passes is
worse than no rehearsal tool. Everything here is hermetic: synthetic SSE frames,
no server.
"""

import io
import json
import sys

from app.scripts import demo_smoke
from app.scripts.demo_smoke import (
    Check,
    configure_console,
    evaluate_alerts,
    evaluate_devanagari_hindi,
    evaluate_forecast,
    evaluate_not_found,
    evaluate_weather,
    parse_sse,
    render,
)


def sse(*frames: tuple[str, dict]) -> str:
    return "".join(
        f"event: {event}\ndata: {json.dumps(payload)}\n\n" for event, payload in frames
    )


def weather_events(*, fallback: bool = False, outage: bool = False):
    if outage:
        return parse_sse(
            sse(
                ("meta", {"status": "fetching", "intent": "current_weather"}),
                ("meta", {"status": "generating", "fallback": True}),
                (
                    "done",
                    {
                        "text": "I don't have live data for that right now. Please try again in a moment.",
                        "intent": "current_weather",
                        "observation": None,
                        "forecast": [],
                        "alerts": [],
                    },
                ),
            )
        )
    return parse_sse(
        sse(
            ("meta", {"status": "resolving", "intent": "current_weather"}),
            ("meta", {"status": "fetching", "intent": "current_weather"}),
            ("meta", {"status": "generating", "fallback": fallback}),
            ("delta", {"text": "Right now in Kolkata"}),
            (
                "done",
                {
                    "text": "Right now in Kolkata: 29°C, Overcast — humidity 78%.",
                    "intent": "current_weather",
                    "observation": {"location_name": "Kolkata", "temperature_c": 29.4},
                    "forecast": [],
                    "alerts": [],
                    "location": {"name": "Kolkata"},
                    "provenance_check": {
                        "verified": True,
                        "checked_numbers": 2,
                        "unverified_numbers": [],
                    },
                },
            ),
        )
    )


def forecast_events(*, when: str = "Tomorrow (Tue 8 Sep) in Mumbai: high 31°, low 24°."):
    return parse_sse(
        sse(
            ("meta", {"status": "generating", "fallback": False}),
            (
                "done",
                {
                    "text": when,
                    "intent": "forecast",
                    "forecast": [{"date": "2026-09-08", "tmax_c": 31.0}],
                    "location": {"name": "Mumbai"},
                    "provenance_check": {"verified": True, "checked_numbers": 2},
                },
            ),
        )
    )


# --- parsing ----------------------------------------------------------------


def test_parse_sse_reads_events_and_ignores_blanks():
    body = "event: meta\ndata: {\"status\": \"resolving\"}\n\n\n" + sse(
        ("done", {"text": "hi"})
    )
    events = parse_sse(body)
    assert events == [("meta", {"status": "resolving"}), ("done", {"text": "hi"})]


def test_parse_sse_joins_multiline_data():
    body = 'event: done\ndata: {"a":\ndata: 1}\n\n'
    assert parse_sse(body) == [("done", {"a": 1})]


# --- scenario 1: current weather --------------------------------------------


def test_weather_success_passes():
    ok, detail = evaluate_weather(weather_events())
    assert ok is True
    assert "Kolkata" in detail


def test_weather_detects_an_error_event():
    events = parse_sse(sse(("error", {"message": "boom"})))
    ok, detail = evaluate_weather(events)
    assert ok is False
    assert "error" in detail


def test_weather_detects_a_failed_provenance_check():
    events = weather_events()
    done = next(d for e, d in events if e == "done")
    done["provenance_check"] = {"verified": False, "unverified_numbers": ["41"]}
    ok, _ = evaluate_weather(events)
    assert ok is False


def test_weather_llm_outage_flag_must_match_the_drill():
    assert evaluate_weather(weather_events(fallback=True))[0] is False
    assert evaluate_weather(weather_events(fallback=True), expect_llm_fallback=True)[0]
    assert evaluate_weather(weather_events())[0] is True
    assert (
        evaluate_weather(weather_events(), expect_llm_fallback=True)[0] is False
    )


def test_weather_provider_outage_accepts_only_a_graceful_gap():
    outage = weather_events(outage=True)
    assert evaluate_weather(outage, expect_provider_outage=True)[0] is True
    # The same events are a failure in normal mode: no observation card.
    assert evaluate_weather(outage)[0] is False
    # ... and invented data must not pass the drill.
    assert evaluate_weather(weather_events(), expect_provider_outage=True)[0] is False


# --- scenario 2: Hinglish forecast -----------------------------------------


def test_forecast_requires_the_right_day_and_place():
    ok, detail = evaluate_forecast(forecast_events())
    assert ok is True
    assert "Mumbai" in detail


def test_forecast_fails_when_kal_was_not_resolved_to_tomorrow():
    events = forecast_events(when="Today in Mumbai: high 31°, low 24°.")
    ok, detail = evaluate_forecast(events)
    assert ok is False
    assert "tomorrow" in detail


def test_forecast_fails_on_the_wrong_location():
    events = forecast_events(when="Tomorrow in Chennai: high 31°.")
    done = next(d for e, d in events if e == "done")
    done["location"] = {"name": "Chennai"}
    ok, _ = evaluate_forecast(events)
    assert ok is False


# --- scenario 3: alerts -----------------------------------------------------


def test_alerts_accepts_a_warning_or_a_clear_none():
    with_alert = parse_sse(
        sse(
            (
                "done",
                {
                    "text": "There is an official warning for Kolkata: Heavy Rain (Severe).",
                    "intent": "alerts",
                    "alerts": [{"event": "Heavy Rain", "severity": "Severe"}],
                },
            )
        )
    )
    ok, detail = evaluate_alerts(with_alert)
    assert ok is True
    assert "1 official warning" in detail

    none_alert = parse_sse(
        sse(
            (
                "done",
                {
                    "text": "No official warnings near Kolkata right now.",
                    "intent": "alerts",
                    "alerts": [],
                },
            )
        )
    )
    assert evaluate_alerts(none_alert)[0] is True


def test_alerts_rejects_the_wrong_intent():
    events = parse_sse(
        sse(("done", {"text": "Right now in Kolkata: 29°C.", "intent": "current_weather"}))
    )
    ok, detail = evaluate_alerts(events)
    assert ok is False
    assert "intent" in detail


# --- scenario 5: the Hindi/Devanagari path ----------------------------------
#
# Devanagari city names were missing from the curated alias index, so every
# Hindi place query failed while the app advertised Hindi support. The geocoder
# cannot rescue it (it is searched in Latin script), which makes this check the
# only thing standing between us and a dead voice demo.


def delhi_search(name: str = "Delhi") -> dict:
    return {"candidates": [{"name": name, "state": "Delhi", "country_code": "IN"}]}


def delhi_forecast_events(when: str = "Tomorrow (Sun 20 Sep) in Delhi: high 34°, low 24°."):
    events = forecast_events(when=when)
    next(d for e, d in events if e == "done")["location"] = {"name": "Delhi"}
    return events


def test_devanagari_hindi_passes_when_delhi_resolves():
    ok, detail = evaluate_devanagari_hindi(delhi_forecast_events(), delhi_search())
    assert ok is True
    assert "Delhi" in detail
    assert "दिल्ली" in detail


def test_devanagari_hindi_rejects_an_answer_for_another_city():
    """The search resolved Delhi; a Mumbai answer must not pass."""
    ok, detail = evaluate_devanagari_hindi(forecast_events(), delhi_search())
    assert ok is False
    assert "the answer is for" in detail


def test_devanagari_hindi_fails_when_the_place_does_not_resolve():
    events = delhi_forecast_events(
        when='I couldn\'t find a place called "दिल्ली". Try a different spelling.'
    )
    ok, detail = evaluate_devanagari_hindi(events, delhi_search())
    assert ok is False
    assert "not resolved" in detail


def test_devanagari_hindi_fails_when_search_returns_nothing():
    ok, detail = evaluate_devanagari_hindi(delhi_forecast_events(), {"candidates": []})
    assert ok is False
    assert "resolved to" in detail


def test_devanagari_hindi_requires_cards_and_provenance_in_normal_mode():
    no_cards = parse_sse(
        sse(
            (
                "done",
                {
                    "text": "Delhi forecast available.",
                    "intent": "forecast",
                    "forecast": [],
                    "location": {"name": "Delhi"},
                },
            )
        )
    )
    assert evaluate_devanagari_hindi(no_cards, delhi_search())[0] is False

    unverified = delhi_forecast_events()
    next(d for e, d in unverified if e == "done")["provenance_check"] = {"verified": False}
    assert evaluate_devanagari_hindi(unverified, delhi_search())[0] is False


def test_devanagari_hindi_accepts_a_graceful_gap_in_the_provider_drill():
    gap = weather_events(outage=True)
    ok, detail = evaluate_devanagari_hindi(gap, delhi_search(), expect_provider_outage=True)
    assert ok is True
    assert "graceful gap" in detail


def test_devanagari_hindi_still_fails_on_an_error_stream():
    assert evaluate_devanagari_hindi(parse_sse(sse(("error", {"message": "boom"}))), delhi_search())[0] is False


# --- console encoding -------------------------------------------------------
#
# The harness runs on the demo laptop. On Windows, a real console speaks UTF-8
# through the console API, but a pipe or a redirection falls back to the locale's
# legacy code page (cp1252) — which cannot encode the box characters or the
# answers the report echoes. Every scenario ran, then the first `print` raised
# UnicodeEncodeError: the whole rehearsal result was lost at the finishing line.


def legacy_console() -> tuple[io.TextIOWrapper, io.BytesIO]:
    """A strict cp1252 stdout — what the rehearsal actually ran into."""
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="")
    return stream, raw


def test_the_report_survives_a_legacy_console(monkeypatch):
    stream, raw = legacy_console()
    monkeypatch.setattr(sys, "stdout", stream)

    configure_console()
    code = render(
        [Check("scenario 1 · current weather (English)", True, "29°C — Overcast")],
        drills=[],
    )
    stream.flush()  # UnicodeEncodeError before configure_console()

    assert code == 0
    report = raw.getvalue().decode("utf-8")
    assert "1/1 scripted scenarios passed" in report
    assert "29°C — Overcast" in report


async def test_main_reports_a_dead_stack_on_a_legacy_console(monkeypatch):
    stream, raw = legacy_console()
    monkeypatch.setattr(sys, "stdout", stream)

    async def never_ready(_client, _seconds):
        return False

    monkeypatch.setattr(demo_smoke, "_wait_for_ready", never_ready)

    code = await demo_smoke.main(["--base-url", "http://127.0.0.1:9"])
    stream.flush()

    assert code == 1
    assert "http://127.0.0.1:9" in raw.getvalue().decode("utf-8")


# --- safety -----------------------------------------------------------------


def test_not_found_requires_a_refusal_and_no_data():
    events = parse_sse(
        sse(
            (
                "done",
                {
                    "text": 'I couldn\'t find a place called "xyzzy". Try a different spelling.',
                    "intent": "current_weather",
                    "observation": None,
                    "forecast": [],
                },
            )
        )
    )
    assert evaluate_not_found(events)[0] is True

    invented = parse_sse(
        sse(
            (
                "done",
                {
                    "text": 'I couldn\'t find a place called "xyzzy".',
                    "observation": {"temperature_c": 30.0},
                    "forecast": [{"date": "2026-09-08"}],
                },
            )
        )
    )
    assert evaluate_not_found(invented)[0] is False
