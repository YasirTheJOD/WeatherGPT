"""Orchestrator — maps a QuerySpec to a retrieval plan and fetches evidence.

Stages, per request:
  1. Query understanding → QuerySpec (or take an explicit candidate pick).
  2. Location resolution: explicit candidate → current location ("near me") →
     resolver.search(place) → top candidate; ambiguous → clarifying question;
     empty → "I couldn't find that place"; none → ask for a place.
  3. Evidence fetch by intent, through the SAME registry/alerts/resolver the
     typed endpoints use (so caching + validation apply identically).
  4. Data gaps are recorded, never hidden: the responder says "I don't have
     data for that" instead of guessing.

The orchestrator reads `request.app.state.*` at call time — the same seam the
endpoint tests already use to stub providers.
"""

from __future__ import annotations

from fastapi import Request

from app.domain.chat import EvidenceBundle, QuerySpec
from app.domain.models import Alert, AlertSummary, LocationCandidate
from app.providers.base import LocationQuery, ProviderUnavailable
from app.services.query_understanding.parser import QueryUnderstandingService

_DETAIL_FETCH_CAP = 3


class ChatOutcome:
    """One of: answered / needs_location / not_found / disambiguation."""

    def __init__(
        self,
        *,
        kind: str,
        spec: QuerySpec | None = None,
        candidates: list[LocationCandidate] | None = None,
        evidence: EvidenceBundle | None = None,
    ):
        self.kind = kind  # "answered" | "needs_location" | "not_found" | "disambiguation"
        self.spec = spec
        self.candidates = candidates or []
        self.evidence = evidence


class ChatOrchestrator:
    def __init__(self, query_understanding: QueryUnderstandingService | None = None):
        self._query = query_understanding or QueryUnderstandingService()

    async def run(
        self,
        request: Request,
        message: str,
        language: str,
        current_location: LocationCandidate | None = None,
    ) -> ChatOutcome:
        spec = self._query.parse(message, language=language)
        return await self._resolve_and_fetch(request, spec, current_location)

    async def run_for_candidate(
        self,
        request: Request,
        candidate: LocationCandidate,
        intent: str,
        language: str,
        current_location: LocationCandidate | None = None,
    ) -> ChatOutcome:
        spec = self._query.parse(
            "", candidate=candidate, explicit_intent=intent, language=language
        )
        return await self._resolve_and_fetch(request, spec, current_location)

    # ------------------------------------------------------------------
    # Location resolution
    # ------------------------------------------------------------------

    async def _resolve_and_fetch(
        self,
        request: Request,
        spec: QuerySpec,
        current_location: LocationCandidate | None,
    ) -> ChatOutcome:
        location = await self._resolve_location(request, spec, current_location)
        if location is None:
            if spec.place_query:
                return ChatOutcome(kind="not_found", spec=spec)
            return ChatOutcome(kind="needs_location", spec=spec)
        if isinstance(location, list):
            return ChatOutcome(kind="disambiguation", spec=spec, candidates=location)

        spec.location = location
        evidence = await self._fetch_evidence(request, spec)
        return ChatOutcome(kind="answered", spec=spec, evidence=evidence)

    async def _resolve_location(
        self,
        request: Request,
        spec: QuerySpec,
        current_location: LocationCandidate | None,
    ) -> LocationCandidate | list[LocationCandidate] | None:
        """Returns the resolved candidate, a list when ambiguous, or None."""
        # 1. Explicit pick (disambiguation follow-up).
        if spec.location is not None:
            return spec.location

        # 2. "near me" → the browser's location.
        if spec.wants_current_location:
            return current_location

        # 3. No place named anywhere → fall back to the browser's location.
        if spec.place_query is None:
            return current_location

        # 4. Forward search.
        resolver = request.app.state.location_resolver
        result = await resolver.search(spec.place_query, limit=8)
        if not result.candidates:
            return None
        if result.ambiguous:
            return result.candidates
        return result.candidates[0]

    # ------------------------------------------------------------------
    # Evidence fetch
    # ------------------------------------------------------------------

    async def _fetch_evidence(self, request: Request, spec: QuerySpec) -> EvidenceBundle:
        location = spec.location
        assert location is not None
        query = LocationQuery(
            latitude=location.latitude,
            longitude=location.longitude,
            city_name=location.name,
        )

        if spec.intent == "alerts":
            return await self._fetch_alerts_evidence(request, location)

        if spec.intent == "forecast":
            try:
                forecast, provider, _ = await request.app.state.registry.daily_forecast(
                    query, days=7
                )
            except ProviderUnavailable as exc:
                return EvidenceBundle(
                    gaps=[f"forecast unavailable: {exc}"],
                    location_name=location.name,
                    intent=spec.intent,
                    day_offset=spec.day_offset,
                    part_of_day=spec.part_of_day,
                )
            return EvidenceBundle(
                forecast=forecast,
                provider_used=provider,
                source_name=forecast[0].provenance.source_name if forecast else None,
                location_name=location.name,
                intent=spec.intent,
                day_offset=spec.day_offset,
                part_of_day=spec.part_of_day,
            )

        # current_weather (default)
        try:
            observation, provider, _ = await request.app.state.registry.current_weather(
                query
            )
        except ProviderUnavailable as exc:
            return EvidenceBundle(
                gaps=[f"observation unavailable: {exc}"],
                location_name=location.name,
                intent=spec.intent,
                day_offset=spec.day_offset,
                part_of_day=spec.part_of_day,
            )
        return EvidenceBundle(
            observation=observation,
            provider_used=provider,
            source_name=observation.provenance.source_name,
            location_name=location.name,
            intent=spec.intent,
            day_offset=spec.day_offset,
            part_of_day=spec.part_of_day,
        )

    async def _fetch_alerts_evidence(
        self, request: Request, location: LocationCandidate
    ) -> EvidenceBundle:
        alerts_provider = request.app.state.alerts
        try:
            summaries = await alerts_provider.fetch_nearby(
                location.latitude, location.longitude, radius_km=20
            )
        except ProviderUnavailable as exc:
            return EvidenceBundle(
                gaps=[f"alerts unavailable: {exc}"],
                source_name="SACHET — NDMA National Disaster Alert Portal",
                location_name=location.name,
                intent="alerts",
            )

        alerts: list[Alert] = []
        for summary in summaries[:_DETAIL_FETCH_CAP]:
            alerts.append(await self._with_detail(alerts_provider, summary))
        return EvidenceBundle(
            alerts=alerts,
            provider_used="sachet",
            source_name="SACHET — NDMA National Disaster Alert Portal",
            location_name=location.name,
            intent="alerts",
        )

    @staticmethod
    async def _with_detail(
        alerts_provider, summary: AlertSummary
    ) -> Alert:
        """Full CAP detail when available; the summary-shaped fallback (event =
        title) keeps alerts working when the detail fetch fails."""
        try:
            return await alerts_provider.fetch_alert_detail(summary.identifier)
        except ProviderUnavailable:
            return Alert(
                identifier=summary.identifier,
                sender=summary.author or "NDMA",
                event=summary.title or "Weather alert",
                category=summary.category,
                provenance=summary.provenance,
            )