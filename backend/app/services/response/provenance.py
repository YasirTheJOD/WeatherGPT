"""Number-provenance post-check — the hallucination firewall.

Every number in the final answer text must trace back to a value in the
evidence bundle (whole-unit rounding of an evidence value is allowed). Any
number that matches nothing is reported as unverified — for LLM-generated
text the response layer can then drop or regenerate it; the deterministic
fallback passes by construction because it interpolates evidence values only.

Benign non-data numbers (calendar labels like "Mon 8 Sep") are stripped
before extraction so date phrasing never trips the firewall.
"""

from __future__ import annotations

import re

from app.domain.chat import EvidenceBundle, ProvenanceCheck

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
# "Mon 8 Sep" / "Tue 28 Nov" — calendar labels carry no data meaning.
_CALENDAR_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+\w{3}\b"
)

_ROUND_TOLERANCE = 0.05


def _evidence_numbers(evidence: EvidenceBundle) -> list[float]:
    values: list[float] = []
    o = evidence.observation
    if o is not None:
        values += [
            v
            for v in [
                o.temperature_c,
                o.humidity_pct,
                o.wind_speed_kmph,
                o.pressure_hpa,
                o.rainfall_24h_mm,
            ]
            if v is not None
        ]
    for day in evidence.forecast:
        values += [
            v
            for v in [
                day.tmax_c,
                day.tmin_c,
                day.rainfall_mm,
                day.humidity_pct,
                day.wind_speed_kmph,
            ]
            if v is not None
        ]
    return values


def _matches(value: float, evidence_values: list[float]) -> bool:
    return any(
        abs(value - ev) <= _ROUND_TOLERANCE or abs(round(ev) - value) <= _ROUND_TOLERANCE
        for ev in evidence_values
    )


def check_provenance(text: str, evidence: EvidenceBundle) -> ProvenanceCheck:
    """Verify every data number in `text` exists in `evidence`."""
    stripped = _CALENDAR_RE.sub(" ", text)
    numbers = [
        float(m) for m in _NUMBER_RE.findall(stripped) if m not in ("0", "-0")
    ]
    evidence_values = _evidence_numbers(evidence)
    unverified = [
        m
        for m in _NUMBER_RE.findall(stripped)
        if m not in ("0", "-0") and not _matches(float(m), evidence_values)
    ]
    return ProvenanceCheck(
        verified=not unverified,
        checked_numbers=len(numbers),
        unverified_numbers=unverified,
    )