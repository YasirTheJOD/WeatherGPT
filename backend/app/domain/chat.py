"""Chat domain — the /chat contract between the frontend and the pipeline.

The pipeline is: ChatRequest → QueryUnderstanding → QuerySpec → Orchestrator →
EvidenceBundle → LLM (grounded text) → provenance post-check → ChatResponse.
Every payload is typed so the SSE `done` event is the exact JSON the Flutter
adapter maps into its `ChatReply` model (no UI-side guessing).
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.models import (
    Alert,
    ForecastDay,
    LocationCandidate,
    WeatherObservation,
)

ChatIntent = Literal["current_weather", "forecast", "alerts", "unknown"]


class ChatRequest(BaseModel):
    """POST /chat body. `candidate` + `intent` are used when the user picks a
    disambiguation option (the frontend's `answerForLocation`); otherwise the
    place is extracted from `message`."""

    message: str = ""
    language: str = "en"
    current_location: LocationCandidate | None = None
    candidate: LocationCandidate | None = None
    intent: Literal["current_weather", "forecast", "alerts"] | None = None

    @model_validator(mode="after")
    def _requires_message_or_candidate(self):
        if not self.message.strip() and self.candidate is None:
            raise ValueError("Provide a message or an explicit candidate location.")
        return self


class QuerySpec(BaseModel):
    """Typed output of query understanding — what the user actually asked."""

    intent: ChatIntent = "current_weather"
    place_query: str | None = None
    location: LocationCandidate | None = None
    wants_current_location: bool = False
    day_offset: int = Field(
        default=0, ge=0, le=6, description="0 = today, 1 = tomorrow (kal)…"
    )
    part_of_day: Literal["morning", "evening"] | None = None
    language: str = "en"


class EvidenceBundle(BaseModel):
    """The ONLY thing the LLM ever sees. Validated, normalized, provenance-
    tagged records; `gaps` explicitly marks anything that could not be
    fetched so the responder says "I don't have that" instead of guessing."""

    observation: WeatherObservation | None = None
    forecast: list[ForecastDay] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    provider_used: str | None = None
    source_name: str | None = None
    location_name: str | None = None
    intent: ChatIntent = "current_weather"
    day_offset: int = 0
    part_of_day: Literal["morning", "evening"] | None = None
    gaps: list[str] = Field(default_factory=list)


class ProvenanceCheck(BaseModel):
    """Hallucination firewall result: every number in the final text must
    trace back to a value in the evidence bundle."""

    verified: bool
    checked_numbers: int = 0
    unverified_numbers: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """The `done` SSE event payload — mirrors the frontend `ChatReply`."""

    text: str
    intent: ChatIntent = "unknown"
    observation: WeatherObservation | None = None
    forecast: list[ForecastDay] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    location: LocationCandidate | None = None
    candidates: list[LocationCandidate] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    source_name: str | None = None
    provenance_check: ProvenanceCheck | None = None