"""LLM provider contract.

Design intent (from the architecture baseline):
  - The LLM only ever receives a validated EvidenceBundle produced by the
    orchestrator; it NEVER calls weather APIs directly.
  - Providers: OpenAI-compatible (OpenAI/Groq), Google Gemini, and a
    deterministic template responder (fallback) so the demo survives key
    outages — that is the default (`llm_provider=fallback`).
  - Grounding rules: evidence-only claims, number-provenance post-check (in
    services/response), OFFICIAL WARNING vs AI interpretation separation.
  - The contract returns TEXT ONLY. Cards, suggestions and provenance checks
    are assembled by the response layer from the evidence bundle, so every
    provider path gets identical structure.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.chat import EvidenceBundle


class LLMProvider(Protocol):
    provider_id: str
    name: str

    def is_configured(self) -> bool:
        """Config-level readiness (does not touch the network)."""
        ...

    async def grounded_response(
        self,
        evidence: EvidenceBundle,
        user_message: str,
        language: str = "en",
    ) -> str:
        """Return a natural-language answer grounded strictly in `evidence`."""
        ...