"""Response assembler — outcome + grounded text → ChatResponse.

Cards (observation/forecast/alerts), location, candidates, source name and
follow-up suggestions all come from the evidence bundle, NOT from the LLM
text — so every provider path (fallback or LLM) yields identical structure.
"""

from __future__ import annotations

from app.domain.chat import ChatResponse, EvidenceBundle, ProvenanceCheck
from app.services.orchestrator.orchestrator import ChatOutcome

STARTER_SUGGESTIONS: list[str] = [
    "What's the weather in Kolkata?",
    "Will it rain tomorrow in Mumbai?",
    "Alerts near me",
    "Kal shaam Mumbai mein baarish hogi kya?",
]

SUGGESTIONS_BY_INTENT: dict[str, list[str]] = {
    "current_weather": [
        "Will it rain tomorrow?",
        "Any alerts nearby?",
        "7-day forecast",
    ],
    "forecast": ["What about the 7-day forecast?", "Alerts nearby"],
    "alerts": ["What should I do?", "What's the weather?"],
}


def assemble_chat_response(
    outcome: ChatOutcome,
    text: str,
    provenance_check: ProvenanceCheck | None = None,
) -> ChatResponse:
    spec = outcome.spec
    intent = spec.intent if spec is not None else "unknown"
    evidence: EvidenceBundle | None = outcome.evidence

    if outcome.kind == "not_found":
        place = spec.place_query if spec and spec.place_query else "that place"
        return ChatResponse(
            text=(
                f"I couldn't find a place called \"{place}\". Try a different "
                "spelling or pick a starter question below."
            ),
            intent=intent,
            suggestions=STARTER_SUGGESTIONS,
        )

    if outcome.kind == "needs_location":
        return ChatResponse(
            text=(
                "Which place are you asking about? Try \"weather in Kolkata\" "
                "or pick a starter question below."
            ),
            intent=intent,
            suggestions=STARTER_SUGGESTIONS,
        )

    if outcome.kind == "disambiguation":
        place = spec.place_query if spec and spec.place_query else "that place"
        return ChatResponse(
            text=(
                f"I found several places named \"{place}\". "
                "Which one do you mean?"
            ),
            intent=intent,
            candidates=outcome.candidates,
        )

    # answered
    return ChatResponse(
        text=text,
        intent=intent,
        observation=evidence.observation if evidence else None,
        forecast=evidence.forecast if evidence else [],
        alerts=evidence.alerts if evidence else [],
        location=spec.location if spec else None,
        suggestions=SUGGESTIONS_BY_INTENT.get(intent, STARTER_SUGGESTIONS),
        source_name=evidence.source_name if evidence else None,
        provenance_check=provenance_check,
    )