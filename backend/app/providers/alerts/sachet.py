"""SACHET — NDMA National Disaster Alert Portal (CAP feed).

All endpoints below were verified live on 2026-09-06:
  - Feed index:  GET {base}/cap_public_website/rss/rss_india.xml
                 (state feeds live at rss/rss_<state>.xml) -> RSS 2.0, one
                 <item> per alert, ETag + Last-Modified response headers.
  - Alert detail: GET {base}/cap_public_website/FetchXMLFile?identifier=<guid>
                 -> full CAP 1.2 XML (event, severity, urgency, certainty,
                 headline, description, instruction, area, polygon URL).
  - Nearby alerts: POST {base}/cap_public_website/FetchLocationWiseAlerts
                 with query-encoded lat/long/radius (JSON body -> 400).
                 Returns {"alerts": [...], "responseMessage": "Success"}.
  - Weather (discovered, secondary): POST {base}/cap_public_website/GetWeatherInfo?lat&lng.

Mandatory caching (per the official Integration Guide for Agencies):
ETag-based. Send If-None-Match on every request after the first; on 304 the
caller MUST reuse its cached copy without re-fetching.
Guide: https://sachet.ndma.gov.in/docs/Integration_Guide_For_Agencies.pdf
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import Settings
from app.domain.models import (
    Alert,
    AlertSummary,
    CapArea,
    FeedFetchResult,
    Provenance,
)
from app.providers.base import ProviderUnavailable


def _local(tag: str) -> str:
    """Local name of an (optionally namespaced) XML tag."""
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _text(element: ET.Element, name: str) -> str | None:
    child = _child(element, name)
    if child is None or not child.text:
        return None
    return child.text.strip()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_rfc2822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return None


def _provenance(source_name: str, ttl: int) -> Provenance:
    return Provenance(
        source_id="sachet",
        source_name=source_name,
        authoritative=True,
        fetched_at=datetime.now(timezone.utc),
        ttl_seconds=ttl,
    )


def parse_rss(xml_text: str, ttl: int = 600) -> list[AlertSummary]:
    """Parse the RSS 2.0 feed index into lightweight alert summaries."""
    root = ET.fromstring(xml_text)
    channel = _child(root, "channel")
    items = _children(channel, "item") if channel is not None else []
    alerts: list[AlertSummary] = []
    for item in items:
        guid = _text(item, "guid") or _text(item, "link") or ""
        alerts.append(
            AlertSummary(
                identifier=guid,
                title=_text(item, "title") or "",
                category=_text(item, "category"),
                author=_text(item, "author"),
                published_at=_parse_rfc2822(_text(item, "pubDate")),
                detail_url=_text(item, "link"),
                provenance=_provenance("SACHET — NDMA National Disaster Alert Portal", ttl),
            )
        )
    return alerts


def parse_cap(xml_text: str, ttl: int = 3600) -> Alert:
    """Parse a CAP 1.2 alert document into the normalized Alert model."""
    root = ET.fromstring(xml_text)
    info = _child(root, "info")

    areas: list[CapArea] = []
    for area_el in _children(info, "area") if info is not None else []:
        areas.append(
            CapArea(
                area_desc=_text(area_el, "areaDesc") or "",
                circles=[c.text.strip() for c in _children(area_el, "circle") if c.text],
                polygons=[p.text.strip() for p in _children(area_el, "polygon") if p.text],
            )
        )

    polygon_url: str | None = None
    if info is not None:
        for param in _children(info, "parameter"):
            if (_text(param, "valueName") or "").lower() == "polygon url":
                polygon_url = _text(param, "value")

    def info_text(name: str) -> str | None:
        return _text(info, name) if info is not None else None

    return Alert(
        identifier=_text(root, "identifier") or "",
        sender=_text(root, "sender") or "",
        sent_at=_parse_iso(_text(root, "sent")),
        status=_text(root, "status"),
        msg_type=_text(root, "msgType"),
        scope=_text(root, "scope"),
        event=info_text("event") or "",
        category=info_text("category"),
        urgency=info_text("urgency"),
        severity=info_text("severity"),
        certainty=info_text("certainty"),
        effective_at=_parse_iso(info_text("effective")),
        expires_at=_parse_iso(info_text("expires")),
        headline=info_text("headline"),
        description=info_text("description"),
        instruction=info_text("instruction"),
        areas=areas,
        polygon_url=polygon_url,
        provenance=_provenance("SACHET — NDMA National Disaster Alert Portal", ttl),
    )


class SachetAlertProvider:
    provider_id = "sachet"
    name = "SACHET — NDMA National Disaster Alert Portal"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.sachet_base_url, timeout=15.0
        )

    async def fetch_feed(self, etag: str | None = None) -> FeedFetchResult:
        """Poll the all-India CAP feed; send If-None-Match when we hold an ETag."""
        headers = {"If-None-Match": etag} if etag else None
        try:
            resp = await self._client.get(f"/{self._settings.sachet_feed_path}", headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"SACHET feed request failed: {exc}") from exc
        if resp.status_code == 304:
            return FeedFetchResult(modified=False, etag=etag, alerts=[])
        if resp.status_code != 200:
            raise ProviderUnavailable(f"SACHET feed returned HTTP {resp.status_code}")
        try:
            alerts = parse_rss(resp.text)
        except ET.ParseError as exc:
            raise ProviderUnavailable(f"SACHET feed unparseable: {exc}") from exc
        return FeedFetchResult(
            modified=True, etag=resp.headers.get("etag") or etag, alerts=alerts
        )

    async def fetch_alert_detail(self, identifier: str) -> Alert:
        try:
            resp = await self._client.get(
                "/cap_public_website/FetchXMLFile", params={"identifier": identifier}
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"SACHET alert detail request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderUnavailable(
                f"SACHET alert detail returned HTTP {resp.status_code}"
            )
        try:
            return parse_cap(resp.text)
        except ET.ParseError as exc:
            raise ProviderUnavailable(f"SACHET alert detail unparseable: {exc}") from exc

    async def fetch_nearby(self, lat: float, lng: float, radius_km: int = 20) -> list[AlertSummary]:
        """Location-scoped alerts, exactly as the SACHET portal's own app calls it."""
        try:
            resp = await self._client.post(
                "/cap_public_website/FetchLocationWiseAlerts",
                params={"lat": lat, "long": lng, "radius": str(radius_km)},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"SACHET nearby-alerts request failed: {exc}") from exc
        except ValueError as exc:
            raise ProviderUnavailable(f"SACHET nearby-alerts returned non-JSON: {exc}") from exc
        if not isinstance(data, dict) or "alerts" not in data:
            raise ProviderUnavailable(
                f"Unexpected nearby-alerts shape: {type(data).__name__}"
            )

        # Observed response shape is {"alerts": [], "responseMessage": "Success"}
        # at the probed location; non-empty entries map defensively until a
        # populated capture is stored in fixtures/.
        summaries: list[AlertSummary] = []
        for entry in data.get("alerts") or []:
            if not isinstance(entry, dict):
                continue
            summaries.append(
                AlertSummary(
                    identifier=str(
                        entry.get("guid") or entry.get("identifier") or entry.get("id") or ""
                    ),
                    title=str(entry.get("title") or entry.get("headline") or ""),
                    category=entry.get("category"),
                    author=entry.get("author") or entry.get("sender"),
                    published_at=_parse_iso(entry.get("pubDate") or entry.get("sent")),
                    detail_url=entry.get("link"),
                    provenance=_provenance(self.name, 300),
                )
            )
        return summaries