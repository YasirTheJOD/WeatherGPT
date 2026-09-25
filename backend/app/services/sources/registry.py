"""Curated source registry — the machine-readable form of docs/DATA-SOURCES.md.

``GET /api/v1/sources`` serves this: the demo's "source transparency tour"
(ARCHITECTURE §10 scenario 7). Static metadata (name, role, status, auth,
evidence link) is curated here and must stay in sync with DATA-SOURCES.md;
``available`` is resolved at request time from the live ``Settings`` so the
registry tells the truth about what is *configured and usable without
authorization* (e.g. IMD reports unavailable until a key is granted — never
hidden). It is deliberately **not** a live reachability probe: this endpoint is
O(1) and must never fail or block on a third party, so an upstream that is
merely offline still reads as available. Reachability is evidenced per answer
instead, by the source card on each response and by the "no live data" gap.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.domain.models import SourceInfo


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    role: str
    status: str
    official: bool
    auth: str
    url: str
    evidence_url: str | None = None
    notes: str | None = None


# Order = narrative order for the transparency drawer: primary first, then
# fallbacks, then sources that are explicitly not in the MVP.
KNOWN_SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="imd",
        name="IMD — India Meteorological Department",
        role="Primary authoritative observations, 7-day forecasts and district warnings",
        status="requires_authorization",
        official=True,
        auth="API key (api.imd.gov.in) + IP whitelisting",
        url="https://api.imd.gov.in",
        evidence_url="https://api.imd.gov.in/public/api_reference.html",
        notes="Verified 2026-09-06: live probe returns \"API key missing\". "
        "See docs/IMD-ACCESS.md for the application checklist.",
    ),
    SourceDefinition(
        source_id="open_meteo",
        name="Open-Meteo (GFS-derived)",
        role="Fallback + resilience layer for current weather and forecasts; not an IMD substitute",
        status="prototype",
        official=False,
        auth="None (free, keyless)",
        url="https://open-meteo.com",
        evidence_url="https://open-meteo.com/en/docs",
        notes="Used until the IMD key/whitelist is granted. GFS-derived point forecasts.",
    ),
    SourceDefinition(
        source_id="met_no",
        name="MET Norway (Locationforecast)",
        role="Second keyless weather fallback, independent of Open-Meteo's per-IP rate limit",
        status="prototype",
        official=False,
        auth="None (free, keyless — descriptive User-Agent required)",
        url="https://www.met.no",
        evidence_url="https://api.met.no/weatherapi/locationforecast/2.0/documentation",
        notes="Added 2026-09-25 after measuring Open-Meteo return HTTP 429 to the "
        "public deploy's shared egress IP (0/18 requests over ~110s). Global model "
        "output — never presented as authoritative or as IMD data.",
    ),
    SourceDefinition(
        source_id="sachet",
        name="SACHET — NDMA National Disaster Alert Portal",
        role="Secondary official source of disaster warnings (CAP 1.2), with ETag caching",
        status="prototype",
        official=True,
        auth="None (public CAP feed)",
        url="https://sachet.ndma.gov.in",
        evidence_url="https://sachet.ndma.gov.in/docs/Integration_Guide_For_Agencies.pdf",
        notes="Verified live 2026-09-06. Alerts pass through untouched — severity/urgency are never altered.",
    ),
    SourceDefinition(
        source_id="geocoding_open_meteo",
        name="Open-Meteo Geocoding",
        role="Forward geocoding for typed city search",
        status="implemented",
        official=False,
        auth="None (keyless)",
        url="https://geocoding-api.open-meteo.com",
        evidence_url="https://open-meteo.com/en/docs/geocoding-api",
    ),
    SourceDefinition(
        source_id="bigdatacloud",
        name="BigDataCloud Reverse Geocoding",
        role="Reverse geocoding for \"near me\" lookups (after the offline nearest-city index)",
        status="implemented",
        official=False,
        auth="None (keyless free tier)",
        url="https://api.bigdatacloud.net",
        evidence_url="https://www.bigdatacloud.com/docs/api/free-reverse-geocode-to-city-api",
    ),
    SourceDefinition(
        source_id="openstreetmap",
        name="OpenStreetMap",
        role="Base map tiles for the location/alert map",
        status="implemented",
        official=False,
        auth="None (tile usage policy)",
        url="https://www.openstreetmap.org",
        evidence_url="https://operations.osmfoundation.org/policies/tiles/",
    ),
    SourceDefinition(
        source_id="llm",
        name="LLM response provider",
        role="Explains the evidence bundle in natural language — never a forecast model",
        status="implemented",
        official=False,
        auth="None in fallback mode; provider key when configured",
        url="https://freebuff.com",
        notes="Default is the deterministic fallback responder, so the demo runs with zero keys.",
    ),
    SourceDefinition(
        source_id="mosdac",
        name="MOSDAC (ISRO/SAC)",
        role="Satellite imagery layers (future cyclone/imagery demos)",
        status="requires_authorization",
        official=True,
        auth="MOSDAC account (registration + approval)",
        url="https://mosdac.gov.in",
        evidence_url="https://mosdac.gov.in/downloadapi-manual",
        notes="Bulk download tool, not a chat-friendly REST API. Future scope — not in the MVP.",
    ),
    SourceDefinition(
        source_id="noaa_gfs",
        name="NOAA GFS (NOMADS / AWS Open Data)",
        role="Raw model output for future NWP map layers",
        status="planned",
        official=False,
        auth="None (public)",
        url="https://registry.opendata.aws/noaa-gfs-bdp-pds/",
        notes="Open-Meteo already serves GFS-derived point forecasts; raw GRIB ingestion is out of MVP.",
    ),
)


def _availability(settings: Settings) -> dict[str, tuple[bool, str | None]]:
    """Resolve runtime availability per source from the live settings."""
    llm_provider = (settings.llm_provider or "fallback").strip().lower()
    llm_keyed = any(
        key.strip()
        for key in (settings.openai_api_key, settings.gemini_api_key, settings.groq_api_key)
    )
    return {
        "imd": (
            settings.imd_configured,
            None if settings.imd_configured else "IMD_API_KEY not set — running on the Open-Meteo fallback",
        ),
        "open_meteo": (True, None),
        "met_no": (True, None),
        "sachet": (True, None),
        "geocoding_open_meteo": (True, None),
        "bigdatacloud": (True, None),
        "openstreetmap": (True, None),
        "llm": (
            llm_provider == "fallback" or llm_keyed,
            None
            if llm_provider == "fallback" or llm_keyed
            else f"LLM_PROVIDER={llm_provider} has no key — falling back to the deterministic responder",
        ),
        "mosdac": (False, "Requires authorization — not in the MVP"),
        "noaa_gfs": (False, "Planned — raw GRIB ingestion is out of MVP scope"),
    }


def build_sources_report(settings: Settings) -> list[SourceInfo]:
    """Static registry + live availability, ready for ``GET /api/v1/sources``."""
    availability = _availability(settings)
    report: list[SourceInfo] = []
    for definition in KNOWN_SOURCES:
        available, message = availability.get(definition.source_id, (True, None))
        report.append(
            SourceInfo(
                source_id=definition.source_id,
                name=definition.name,
                role=definition.role,
                status=definition.status,  # type: ignore[arg-type]
                official=definition.official,
                auth=definition.auth,
                url=definition.url,
                evidence_url=definition.evidence_url,
                available=available,
                available_message=message,
                notes=definition.notes,
            )
        )
    return report
