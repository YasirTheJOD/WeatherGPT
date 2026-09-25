"""Validation service tests — plausibility bounds and freshness semantics."""

from datetime import datetime, timedelta, timezone

from app.domain.models import ForecastDay, Provenance, WeatherObservation
from app.services.validation.validator import ValidationService

NOW = datetime.now(timezone.utc)


def _provenance(fetched_at: datetime = NOW, ttl: int = 300) -> Provenance:
    return Provenance(
        source_id="test", source_name="test", authoritative=False, fetched_at=fetched_at, ttl_seconds=ttl
    )


def _obs(**overrides) -> WeatherObservation:
    base = dict(
        latitude=22.57,
        longitude=88.36,
        temperature_c=30.0,
        humidity_pct=80.0,
        wind_speed_kmph=10.0,
        provenance=_provenance(),
    )
    base.update(overrides)
    return WeatherObservation(**base)


def test_valid_observation_passes():
    report = ValidationService().validate_observation(_obs())
    assert report.valid is True
    assert report.issues == []


def test_out_of_range_temperature_is_hard_error():
    report = ValidationService().validate_observation(_obs(temperature_c=99.0))
    assert report.valid is False
    assert any(i.code == "out_of_range" for i in report.issues)


def test_humidity_out_of_range_is_hard_error():
    report = ValidationService().validate_observation(_obs(humidity_pct=150.0))
    assert report.valid is False


def test_stale_data_is_warning_not_error():
    fetched = NOW - timedelta(seconds=3600)  # age 1h vs TTL 300s
    report = ValidationService().validate_observation(_obs(provenance=_provenance(fetched_at=fetched)))
    assert report.valid is True  # staleness alone does not fail the provider gate
    assert any(i.code == "stale" and i.level == "warning" for i in report.issues)


def test_fresh_data_has_no_staleness_warning():
    report = ValidationService().validate_observation(_obs())
    assert not any(i.code == "stale" for i in report.issues)


def test_inverted_forecast_temps_is_hard_error():
    day = ForecastDay(
        date="2026-09-07", tmax_c=20.0, tmin_c=30.0, provenance=_provenance()
    )
    report = ValidationService().validate_forecast([day])
    assert report.valid is False
    assert any(i.code == "inverted_temps" for i in report.issues)


def test_valid_forecast_passes():
    day = ForecastDay(
        date="2026-09-07", tmax_c=31.0, tmin_c=26.0, rainfall_mm=5.0, provenance=_provenance()
    )
    report = ValidationService().validate_forecast([day])
    assert report.valid is True