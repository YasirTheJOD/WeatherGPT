"""Google Gemini adapter (generateContent REST API).

Same contract and fail-closed behaviour as the OpenAI-compatible adapter:
no key → `is_configured()` False → ProviderUnavailable → deterministic
fallback path. The demo never dies on a missing key.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.domain.chat import EvidenceBundle
from app.providers.base import ProviderUnavailable
from app.providers.llm.prompting import build_grounding_prompt


class GeminiProvider:
    provider_id = "gemini"
    name = "Google Gemini"

    def __init__(self, settings: Settings, *, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=30.0)

    def is_configured(self) -> bool:
        return bool(self._api_key.strip())

    async def grounded_response(
        self,
        evidence: EvidenceBundle,
        user_message: str,
        language: str = "en",
    ) -> str:
        if not self.is_configured():
            raise ProviderUnavailable("gemini is not configured (missing API key).")
        system, user = build_grounding_prompt(evidence, user_message, language)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        try:
            resp = await self._client.post(
                url,
                params={"key": self._api_key},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": user}]}],
                    "generationConfig": {"temperature": 0.2},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"gemini request failed: {exc}") from exc
        except ValueError as exc:
            raise ProviderUnavailable(f"gemini returned non-JSON: {exc}") from exc

        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable(f"gemini returned no content: {exc}") from exc