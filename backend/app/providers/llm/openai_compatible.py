"""OpenAI-compatible chat-completions adapter (OpenAI, Groq, and any vendor
with the same API shape).

Unconfigured (no API key) → `is_configured()` False; calling it raises
ProviderUnavailable, which the /chat endpoint turns into an `error` SSE event
and the frontend falls back to the deterministic typed endpoints. The demo
never dies on a missing key.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.domain.chat import EvidenceBundle
from app.providers.base import ProviderUnavailable
from app.providers.llm.prompting import build_grounding_prompt


class OpenAICompatibleProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider_id: str,
        name: str,
    ):
        self.provider_id = provider_id
        self.name = name
        self._base_url = base_url.rstrip("/")
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
            raise ProviderUnavailable(
                f"{self.provider_id} is not configured (missing API key)."
            )
        system, user = build_grounding_prompt(evidence, user_message, language)
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"{self.provider_id} request failed: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise ProviderUnavailable(
                f"{self.provider_id} returned an unexpected response: {exc}"
            ) from exc

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable(
                f"{self.provider_id} returned no content: {exc}"
            ) from exc


def build_openai_compatible(settings: Settings) -> OpenAICompatibleProvider:
    """Groq (fast, free tier, Llama) is the default OpenAI-compatible vendor."""
    return OpenAICompatibleProvider(
        settings,
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model="llama-3.3-70b-versatile",
        provider_id="groq",
        name="Groq (Llama 3.3 70B)",
    )