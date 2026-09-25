"""LLM provider factory — `llm_provider` env var selects the implementation.

  - "fallback" (default): deterministic template responder. Zero keys, demo-proof.
  - "groq": OpenAI-compatible adapter against Groq (free tier, Llama 3.3).
  - "openai": OpenAI-compatible adapter against OpenAI.
  - "gemini": Google Gemini adapter.

Unknown values fall back to the deterministic responder so a typo in `.env`
can never kill the demo.
"""

from app.core.config import Settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.fallback import FallbackLLMProvider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.openai_compatible import (
    OpenAICompatibleProvider,
    build_openai_compatible,
)


def build_llm_provider(settings: Settings) -> LLMProvider:
    name = settings.llm_provider.strip().lower()
    if name == "groq":
        return build_openai_compatible(settings)
    if name == "openai":
        return OpenAICompatibleProvider(
            settings,
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            provider_id="openai",
            name="OpenAI (GPT-4o mini)",
        )
    if name == "gemini":
        return GeminiProvider(
            settings,
            api_key=settings.gemini_api_key,
            model="gemini-1.5-flash",
        )
    return FallbackLLMProvider()


__all__ = [
    "LLMProvider",
    "FallbackLLMProvider",
    "GeminiProvider",
    "OpenAICompatibleProvider",
    "build_llm_provider",
]