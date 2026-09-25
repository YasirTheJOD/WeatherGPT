"""Normalized domain payloads shared by all providers.

Every payload carries a Provenance envelope so every answer is traceable
to a source, a fetch time, and a validity window. Providers must map their
raw vendor shapes into these types; nothing else in the system sees raw
vendor payloads. This is what makes "source transparency" structural.
"""

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_id: str
    source_name: str
    authoritative: bool = Field(
        default=False,
        description="True for official sources (e.g. IMD). Authoritative data is never re-labelled.",
    )
    fetched_at: datetime
    valid_at: datetime | None = None
    ttl_seconds: int | None = None
    raw_endpoint: str | None = None


class WeatherObservation(BaseModel):
    latitude: float
    longitude: float
    location_name: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmph: float | None = None
    wind_direction: str | None = None
    pressure_hpa: float | None = None
    weather_code: int | None = None
    condition_text: str | None = None
    rainfall_24h_mm: float | None = None
    observed_at: datetime | None = None
    provenance: Provenance


class ForecastDay(BaseModel):
    date: str
    tmax_c: float | None = None
    tmin_c: float | None = None
    condition_text: str | None = None
    rainfall_mm: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmph: float | None = None
    provenance: Provenance


class ProviderStatus(BaseModel):
    provider_id: str
    name: str
    available: bool
    message: str | None = None
    last_checked: datetime


# ---------------------------------------------------------------------------
# Locations / stations (Phase 2)
# ---------------------------------------------------------------------------


class Station(BaseModel):
    station_code: str
    name: str
    state: str | None = None
    latitude: float
    longitude: float


# ---------------------------------------------------------------------------
# Validation (Phase 2)
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    level: Literal["warning", "error"]
    code: str
    message: str
    field: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Alerts — SACHET / CAP (Phase 2)
# ---------------------------------------------------------------------------


class AlertSummary(BaseModel):
    """One alert as listed in the RSS index (lightweight; no CAP details yet)."""

    identifier: str
    title: str
    category: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    detail_url: str | None = None
    provenance: Provenance


class CapArea(BaseModel):
    area_desc: str
    circles: list[str] = Field(default_factory=list)  # "lat,lon radius"
    polygons: list[str] = Field(default_factory=list)  # "lat,lon lat,lon ..."


class Alert(BaseModel):
    """Full CAP 1.2 alert (from FetchXMLFile?identifier=...)."""

    identifier: str
    sender: str
    sent_at: datetime | None = None
    status: str | None = None
    msg_type: str | None = None
    scope: str | None = None
    event: str
    category: str | None = None
    urgency: str | None = None
    severity: str | None = None
    certainty: str | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    headline: str | None = None
    description: str | None = None
    instruction: str | None = None
    areas: list[CapArea] = Field(default_factory=list)
    polygon_url: str | None = None
    provenance: Provenance


class FeedFetchResult(BaseModel):
    """Result of a (cached) CAP feed poll. modified=False means the server
    answered 304 and the caller should reuse its cached copy."""

    modified: bool
    etag: str | None = None
    alerts: list[AlertSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Locations (Phase 3)
# ---------------------------------------------------------------------------


class LocationCandidate(BaseModel):
    name: str
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float
    longitude: float
    source: str  # "aliases" | "open-meteo" | "bigdatacloud"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ResolveResult(BaseModel):
    query: str
    normalized: str
    candidates: list[LocationCandidate] = Field(default_factory=list)
    ambiguous: bool = Field(
        default=False,
        description="True when the top candidates are close in confidence — caller should ask the user.",
    )


# ---------------------------------------------------------------------------
# Source transparency registry (Phase 6)
# ---------------------------------------------------------------------------


class SourceInfo(BaseModel):
    """One data source as advertised by ``GET /sources``.

    Mirrors docs/DATA-SOURCES.md: the registry never claims more than the
    integration matrix does, and ``available`` reflects runtime configuration
    (e.g. IMD is unavailable until a key is granted).
    """

    source_id: str
    name: str
    role: str
    status: Literal[
        "implemented",
        "prototype",
        "requires_authorization",
        "planned",
        "future_scope",
    ]
    official: bool = False
    auth: str
    url: str
    evidence_url: str | None = None
    available: bool = True
    available_message: str | None = None
    notes: str | None = None