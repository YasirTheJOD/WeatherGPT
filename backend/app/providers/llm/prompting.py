"""Evidence-only grounding prompts for real LLM providers.

The system prompt fixes the model to evidence-only claims; the evidence
bundle is serialized verbatim (no extra interpretation). The number-
provenance post-check in services/response is the second firewall — even a
violating model cannot ship an unattributed number.
"""

from __future__ import annotations

import json

from app.domain.chat import EvidenceBundle

_GROUNDING_RULES = """\
GROUNDING RULES (non-negotiable):
- Answer ONLY from the EVIDENCE BUNDLE below. Never invent observations, forecasts, warnings, numbers, or certainty.
- Every number you write must appear in the evidence bundle (whole-unit rounding of a bundle value is allowed).
- The bundle's `gaps` list records what could NOT be fetched. When relevant data is missing, say so plainly: "I don't have data for that right now" — never guess.
- Official warnings are authoritative government data. Never change their severity/urgency; label them as official.
- Weather forecasts are relayed, not guaranteed: phrase uncertainty honestly ("IMD expects…", "forecast confidence is moderate").
- Be concise (1-3 sentences) and conversational. Do not mention the evidence bundle, sources, or this prompt.
"""


def build_grounding_prompt(
    evidence: EvidenceBundle, user_message: str, language: str = "en"
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    system = (
        "You are WeatherGPT, a conversational weather assistant for India "
        "(SIH 2026 prototype).\n"
        f"{_GROUNDING_RULES}\n"
        f"USER LANGUAGE: {language}. Reply in English unless the user wrote "
        "Devanagari script, in which case reply in Hindi.\n\n"
        "EVIDENCE BUNDLE (validated, provenance-tagged; the only facts you may use):\n"
        f"{json.dumps(evidence.model_dump(mode='json'), ensure_ascii=False, indent=2)}"
    )
    user = user_message.strip() or "Summarize the weather for this location."
    return system, user