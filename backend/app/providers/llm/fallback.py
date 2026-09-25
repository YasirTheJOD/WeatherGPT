"""Deterministic fallback responder — the demo never dies.

Builds a grammatical, grounded answer straight from the EvidenceBundle with
no LLM in the loop. Numbers are interpolated from evidence values, so the
number-provenance post-check passes by construction (it is still run, as the
uniform firewall). Only fluency differs from an LLM answer; provenance and
safety guarantees are identical.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.chat import EvidenceBundle
from app.domain.models import Alert, ForecastDay, WeatherObservation

_SEVERITY_RANK = {
    "Extreme": 4,
    "Severe": 3,
    "Moderate": 2,
    "Minor": 1,
}

# rainfall_24h_mm means different things per source (see WeatherObservation), so the
# prose says which one it is rather than implying an observed 24h total for all of them.
_RAINFALL_WINDOW = {
    "observed_24h": " (last 24h)",
    "forecast_24h": " (next 24h)",
    "instant": " (now)",
}


def _rain_phrase(observation: WeatherObservation) -> str:
    if observation.rainfall_24h_mm is None:
        return ""
    window = _RAINFALL_WINDOW.get(observation.rainfall_basis or "", "")
    return f"rain {observation.rainfall_24h_mm:g} mm{window}"


class FallbackLLMProvider:
    provider_id = "fallback"
    name = "Deterministic template responder (no LLM)"

    def is_configured(self) -> bool:
        return True

    async def grounded_response(
        self,
        evidence: EvidenceBundle,
        user_message: str,
        language: str = "en",
    ) -> str:
        if evidence.alerts:
            return self._alerts_answer(evidence)
        if evidence.intent == "alerts":
            return self._no_alerts_answer(evidence)
        if evidence.forecast:
            return self._forecast_answer(evidence)
        if evidence.observation is not None:
            return self._observation_answer(evidence)
        return self._gap_answer(evidence)

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _observation_answer(evidence: EvidenceBundle) -> str:
        o: WeatherObservation = evidence.observation  # type: ignore[assignment]
        headline = [
            f"{o.temperature_c:.0f}°C" if o.temperature_c is not None else "",
            o.condition_text or "",
        ]
        headline = [h for h in headline if h]
        details = [
            f"humidity {o.humidity_pct:.0f}%" if o.humidity_pct is not None else "",
            (
                f"wind {o.wind_speed_kmph:.0f} km/h"
                + (f" {o.wind_direction}" if o.wind_direction else "")
                if o.wind_speed_kmph is not None
                else ""
            ),
            f"pressure {o.pressure_hpa:.0f} hPa" if o.pressure_hpa is not None else "",
            _rain_phrase(o),
        ]
        details = [d for d in details if d]
        name = o.location_name or evidence.location_name or "your location"
        if not headline:
            return f"I don't have live observations for {name} right now."
        return (
            f"Right now in {name}: {', '.join(headline)}"
            + (f" — {', '.join(details)}." if details else ".")
        )

    @classmethod
    def _forecast_answer(cls, evidence: EvidenceBundle) -> str:
        days = evidence.forecast
        if not days:
            return "No forecast data is available right now."
        day = days[min(evidence.day_offset, len(days) - 1)]
        when = cls._when_phrase(day, evidence)
        bits = [
            f"high {day.tmax_c:.0f}°" if day.tmax_c is not None else "",
            f"low {day.tmin_c:.0f}°" if day.tmin_c is not None else "",
            f"rain {day.rainfall_mm:g} mm" if day.rainfall_mm is not None else "",
            day.condition_text or "",
        ]
        bits = [b for b in bits if b]
        if not bits:
            return f"No forecast detail is available for {when}."
        return f"{when}: {', '.join(bits)}."

    @staticmethod
    def _when_phrase(day: ForecastDay, evidence: EvidenceBundle) -> str:
        """'Tomorrow evening (Mon 8 Sep) in Mumbai', 'This morning in Delhi', …"""
        place = evidence.location_name or "your location"
        part = evidence.part_of_day or ""
        offset = evidence.day_offset
        try:
            parsed = datetime.strptime(day.date, "%Y-%m-%d")
            # Portable day formatting (%-d is not available on Windows).
            label = f"{parsed.strftime('%a')} {parsed.day} {parsed.strftime('%b')}"
        except ValueError:
            label = day.date
        if offset == 0:
            when = {"evening": "This evening", "morning": "This morning"}.get(
                part, "Today"
            )
            return f"{when} in {place}"
        if offset == 1:
            when = "tomorrow" if not part else f"tomorrow {part}"
            return f"{when.capitalize()} ({label}) in {place}"
        return f"On {label} in {place}"

    @staticmethod
    def _alerts_answer(evidence: EvidenceBundle) -> str:
        alerts = sorted(
            evidence.alerts,
            key=lambda a: _SEVERITY_RANK.get(a.severity or "", 0),
            reverse=True,
        )
        place = evidence.location_name or "your area"
        top = alerts[0]
        severity = f" ({top.severity})" if top.severity else ""
        if len(alerts) == 1:
            return (
                f"There is an official warning for {place}: {top.event}{severity}. "
                "Follow the instructions in the official warning below."
            )
        return (
            f"There are {len(alerts)} official warnings for {place}. "
            f"The most severe: {top.event}{severity}. Follow the instructions "
            "in the official warnings below."
        )

    @staticmethod
    def _no_alerts_answer(evidence: EvidenceBundle) -> str:
        place = evidence.location_name or "your area"
        return (
            f"No official warnings near {place} right now. "
            "I'll keep checking the official feed."
        )

    @staticmethod
    def _gap_answer(evidence: EvidenceBundle) -> str:
        if evidence.gaps and "alerts" in evidence.gaps[0]:
            return (
                "Official warnings are temporarily unavailable. Please check "
                "the NDMA SACHET portal or try again in a moment."
            )
        return (
            "I don't have live data for that right now. Please try again in a "
            "moment."
        )