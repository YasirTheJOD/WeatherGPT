"""Number-provenance post-check — the hallucination firewall."""

from datetime import datetime, timezone

from app.domain.chat import EvidenceBundle
from app.domain.models import (
    ForecastDay,
    Provenance,
    WeatherObservation,
)
from app.services.response.provenance import check_provenance


def _provenance():
    return Provenance(
        source_id="open-meteo",
        source_name="Open-Meteo",
        fetched_at=datetime.now(timezone.utc),
    )


def _observation_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        observation=WeatherObservation(
            latitude=22.57,
            longitude=88.36,
            location_name="Kolkata",
            temperature_c=29.4,
            humidity_pct=78.0,
            wind_speed_kmph=12.6,
            pressure_hpa=1008.0,
            rainfall_24h_mm=2.3,
            provenance=_provenance(),
        )
    )


def test_all_numbers_trace_to_evidence():
    check = check_provenance(
        "Right now in Kolkata: 29°C, Overcast — humidity 78%, wind 13 km/h S, "
        "pressure 1008 hPa, rain 2.3 mm.",
        _observation_evidence(),
    )
    assert check.verified is True
    assert check.unverified_numbers == []


def test_invented_number_fails():
    check = check_provenance(
        "Right now in Kolkata: 41°C — humidity 78%.",
        _observation_evidence(),
    )
    assert check.verified is False
    assert "41" in check.unverified_numbers


def test_calendar_label_does_not_trip_firewall():
    evidence = EvidenceBundle(
        forecast=[
            ForecastDay(
                date="2026-09-08",
                tmax_c=31.0,
                tmin_c=24.0,
                provenance=_provenance(),
            )
        ],
        location_name="Mumbai",
        day_offset=1,
    )
    check = check_provenance(
        "Tomorrow (Mon 8 Sep) in Mumbai: high 31°, low 24°.",
        evidence,
    )
    assert check.verified is True


def test_decimal_matches_within_rounding():
    check = check_provenance(
        "Right now in Kolkata: 29.4°C, rain 2.3 mm.",
        _observation_evidence(),
    )
    assert check.verified is True