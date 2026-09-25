"""Plausibility + freshness validation (pipeline stage 4).

Semantics:
  - Errors (impossible values, inverted min/max) cause the provider result to
    be discarded and the next provider in the chain to be tried.
  - Warnings (staleness) are surfaced, never silenced — provenance already
    shows data age; the report makes it explicit.

Bounds are deliberately wide (India's observed climate ranges) — their job is
to catch corrupt payloads, not to second-guess meteorology.
"""

from datetime import datetime, timezone

from app.domain.models import (
    ForecastDay,
    ValidationIssue,
    ValidationReport,
    WeatherObservation,
)

BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_c": (-50.0, 55.0),
    "humidity_pct": (0.0, 100.0),
    "wind_speed_kmph": (0.0, 500.0),
    "pressure_hpa": (850.0, 1100.0),
    "rainfall_24h_mm": (0.0, 2000.0),
    "rainfall_mm": (0.0, 2000.0),
    "tmax_c": (-50.0, 55.0),
    "tmin_c": (-50.0, 55.0),
}


class ValidationService:
    def __init__(
        self,
        bounds: dict[str, tuple[float, float]] | None = None,
        stale_factor: float = 1.0,
    ):
        self._bounds = bounds or BOUNDS
        self._stale_factor = stale_factor

    def validate_observation(self, obs: WeatherObservation) -> ValidationReport:
        report = ValidationReport(valid=True)
        self._check_range(report, "temperature_c", obs.temperature_c)
        self._check_range(report, "humidity_pct", obs.humidity_pct)
        self._check_range(report, "wind_speed_kmph", obs.wind_speed_kmph)
        self._check_range(report, "pressure_hpa", obs.pressure_hpa)
        self._check_range(report, "rainfall_24h_mm", obs.rainfall_24h_mm)
        self._check_freshness(report, obs.provenance.fetched_at, obs.provenance.ttl_seconds)
        report.valid = not self._has_errors(report)
        return report

    def validate_forecast(self, days: list[ForecastDay]) -> ValidationReport:
        report = ValidationReport(valid=True)
        for index, day in enumerate(days, start=1):
            prefix = f"day {index}: "
            self._check_range(report, "tmax_c", day.tmax_c, prefix=prefix)
            self._check_range(report, "tmin_c", day.tmin_c, prefix=prefix)
            self._check_range(report, "rainfall_mm", day.rainfall_mm, prefix=prefix)
            if day.tmax_c is not None and day.tmin_c is not None and day.tmax_c < day.tmin_c:
                report.issues.append(
                    ValidationIssue(
                        level="error",
                        code="inverted_temps",
                        message=f"{prefix}tmax {day.tmax_c} below tmin {day.tmin_c}",
                        field="tmax_c",
                    )
                )
        if days:
            self._check_freshness(
                report, days[0].provenance.fetched_at, days[0].provenance.ttl_seconds
            )
        report.valid = not self._has_errors(report)
        return report

    def _check_range(
        self,
        report: ValidationReport,
        field: str,
        value: float | None,
        prefix: str = "",
    ) -> None:
        if value is None or field not in self._bounds:
            return
        low, high = self._bounds[field]
        if not (low <= value <= high):
            report.issues.append(
                ValidationIssue(
                    level="error",
                    code="out_of_range",
                    message=f"{prefix}{field}={value} outside plausible range [{low}, {high}]",
                    field=field,
                )
            )

    def _check_freshness(
        self,
        report: ValidationReport,
        fetched_at: datetime | None,
        ttl_seconds: int | None,
    ) -> None:
        if fetched_at is None or ttl_seconds is None:
            return
        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age > ttl_seconds * self._stale_factor:
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="stale",
                    message=f"data age {int(age)}s exceeds TTL {ttl_seconds}s",
                    field="provenance.fetched_at",
                )
            )

    @staticmethod
    def _has_errors(report: ValidationReport) -> bool:
        return any(issue.level == "error" for issue in report.issues)