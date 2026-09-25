"""Fallback LLM responder — deterministic grounded answers from evidence."""

from datetime import datetime, timezone

import pytest

from app.domain.chat import EvidenceBundle
from app.domain.models import (
    Alert,
    ForecastDay,
    Provenance,
    WeatherObservation,
)
from app.providers.llm.fallback import FallbackLLMProvider


def _provenance(source_name="Open-Meteo"):
    return Provenance(
        source_id="open-meteo",
        source_name=source_name,
        authoritative=False,
        fetched_at=datetime.now(timezone.utc),
    )


def _observation(**overrides) -> WeatherObservation:
    values = dict(
        latitude=22.57,
        longitude=88.36,
        location_name="Kolkata",
        temperature_c=29.4,
        humidity_pct=78.0,
        wind_speed_kmph=12.6,
        wind_direction="S",
        pressure_hpa=1008.0,
        condition_text="Overcast",
        rainfall_24h_mm=2.3,
        provenance=_provenance(),
    )
    values.update(overrides)
    return WeatherObservation(**values)


def _forecast(dates=("2026-09-07", "2026-09-08")) -> list[ForecastDay]:
    return [
        ForecastDay(
            date=dates[0],
            tmax_c=32.0,
            tmin_c=25.0,
            condition_text="Overcast",
            rainfall_mm=4.5,
            provenance=_provenance(),
        ),
        ForecastDay(
            date=dates[1],
            tmax_c=31.0,
            tmin_c=24.0,
            condition_text="Partly cloudy",
            rainfall_mm=None,
            provenance=_provenance(),
        ),
    ]


async def test_observation_answer_interpolates_evidence_numbers():
    text = await FallbackLLMProvider().grounded_response(
        EvidenceBundle(observation=_observation()), "weather in Kolkata"
    )
    assert "Right now in Kolkata" in text
    assert "29°C" in text
    assert "Overcast" in text
    assert "humidity 78%" in text
    assert "wind 13 km/h S" in text  # 12.6 rounds to 13
    assert "pressure 1008 hPa" in text
    assert "rain 2.3 mm" in text


@pytest.mark.parametrize(
    ("basis", "expected"),
    [
        ("observed_24h", "rain 2.3 mm (last 24h)"),
        ("forecast_24h", "rain 2.3 mm (next 24h)"),
        ("instant", "rain 2.3 mm (now)"),
        (None, "rain 2.3 mm"),
    ],
)
async def test_rain_phrase_states_the_window_the_source_actually_gave(basis, expected):
    """One field, three meanings — the prose must not imply an observation it lacks."""
    text = await FallbackLLMProvider().grounded_response(
        EvidenceBundle(observation=_observation(rainfall_basis=basis)), "weather"
    )
    assert expected in text


async def test_forecast_answer_uses_day_offset_and_part_of_day():
    evidence = EvidenceBundle(
        forecast=_forecast(),
        location_name="Mumbai",
        day_offset=1,
        part_of_day="evening",
    )
    text = await FallbackLLMProvider().grounded_response(evidence, "kal shaam baarish")
    assert "Tomorrow evening" in text
    assert "in Mumbai" in text
    assert "high 31°" in text  # day 2 (index 1) values
    assert "low 24°" in text


async def test_forecast_answer_today_without_part():
    evidence = EvidenceBundle(
        forecast=_forecast(), location_name="Delhi", day_offset=0
    )
    text = await FallbackLLMProvider().grounded_response(evidence, "today forecast")
    assert text.startswith("Today in Delhi")
    assert "high 32°" in text


async def test_alerts_answer_uses_most_severe():
    evidence = EvidenceBundle(
        intent="alerts",
        alerts=[
            Alert(
                identifier="CAP-2",
                sender="NDMA",
                event="Heavy Rain",
                severity="Moderate",
                provenance=_provenance("SACHET — NDMA National Disaster Alert Portal"),
            ),
            Alert(
                identifier="CAP-1",
                sender="NDMA",
                event="Cyclone",
                severity="Extreme",
                provenance=_provenance("SACHET — NDMA National Disaster Alert Portal"),
            ),
        ],
        location_name="Chennai",
    )
    text = await FallbackLLMProvider().grounded_response(evidence, "alerts")
    assert "2 official warnings for Chennai" in text
    assert "Cyclone" in text
    assert "Extreme" in text


async def test_alerts_empty_keeps_calm_phrasing():
    evidence = EvidenceBundle(
        intent="alerts", alerts=[], location_name="Kolkata"
    )
    text = await FallbackLLMProvider().grounded_response(evidence, "alerts near me")
    assert "No official warnings near Kolkata right now" in text


async def test_gap_answer_never_guesses():
    evidence = EvidenceBundle(
        gaps=["observation unavailable: all providers failed"], location_name="Kolkata"
    )
    text = await FallbackLLMProvider().grounded_response(evidence, "weather")
    assert "I don't have live data for that right now" in text