"""Provider contracts — the seam that keeps vendors replaceable.

  - WeatherProvider: implemented by IMD (authoritative) and Open-Meteo (fallback).
  - LLMProvider:     implemented in Phase 5 (OpenAI-compatible / Gemini /
                     deterministic fallback). Defined in providers/llm/base.py.

Providers must never leak vendor payloads: they normalize into
app.domain.models before returning. Nothing else calls vendor APIs.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.models import (
    ForecastDay,
    ProviderStatus,
    ValidationReport,
    WeatherObservation,
)

_CACHE_TTL_CURRENT_S = 120
_CACHE_TTL_FORECAST_S = 600


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderUnavailable(ProviderError):
    """The provider cannot serve this request (not configured, unreachable,
    auth failure, required data not yet available...)."""


class LocationQuery:
    """Location for a provider request.

    latitude/longitude are the primary key; station_id and city_name are
    provider-specific hints (IMD station codes are resolved in Phase 2/3).
    """

    def __init__(
        self,
        latitude: float,
        longitude: float,
        station_id: str | None = None,
        city_name: str | None = None,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.station_id = station_id
        self.city_name = city_name


class WeatherProvider(Protocol):
    provider_id: str
    name: str

    def is_configured(self) -> bool:
        """Config-level readiness (does not touch the network)."""
        ...

    async def current_weather(self, location: LocationQuery) -> WeatherObservation:
        ...

    async def daily_forecast(self, location: LocationQuery, days: int = 7) -> list[ForecastDay]:
        ...


class ProviderRegistry:
    """Ordered provider chain; the first validated success wins.

    Construction order encodes preference ("IMD primary, Open-Meteo
    fallback"), so switching providers is a config/build decision, not
    a code change. When a validator is attached, payloads that fail hard
    validation (impossible values) are discarded and the next provider
    is tried — that is the data-validation gate of the pipeline.
    """

    def __init__(
        self,
        providers: list[WeatherProvider],
        validator: "ValidationService | None" = None,
        cache: "CacheService | None" = None,
    ):
        self.providers = providers
        self._validator = validator
        self._cache = cache

    async def current_weather(
        self, location: LocationQuery, use_cache: bool = True
    ) -> tuple[WeatherObservation, str, ValidationReport]:
        key = f"weather:current:{location.latitude:.4f}:{location.longitude:.4f}"
        cached = await self._read_cache(key, use_cache)
        if cached is not None:
            return cached

        errors: list[str] = []
        for provider in self.providers:
            try:
                payload = await provider.current_weather(location)
            except ProviderError as exc:
                errors.append(f"{provider.provider_id}: {exc}")
                continue
            report = self._validate_observation(payload)
            if not report.valid:
                errors.append(
                    f"{provider.provider_id}: validation failed: "
                    + "; ".join(i.message for i in report.issues)
                )
                continue
            result = (payload, provider.provider_id, report)
            await self._write_cache(
                key,
                {
                    "observation": payload.model_dump(mode="json"),
                    "provider_used": provider.provider_id,
                    "validation": report.model_dump(mode="json"),
                },
                ttl=_CACHE_TTL_CURRENT_S,
            )
            return result
        raise ProviderUnavailable("All weather providers failed: " + "; ".join(errors))

    async def daily_forecast(
        self, location: LocationQuery, days: int = 7, use_cache: bool = True
    ) -> tuple[list[ForecastDay], str, ValidationReport]:
        key = f"weather:forecast:{location.latitude:.4f}:{location.longitude:.4f}:{days}"
        cached = await self._read_forecast_cache(key, use_cache)
        if cached is not None:
            return cached

        errors: list[str] = []
        for provider in self.providers:
            try:
                payload = await provider.daily_forecast(location, days=days)
            except ProviderError as exc:
                errors.append(f"{provider.provider_id}: {exc}")
                continue
            report = self._validate_forecast(payload)
            if not report.valid:
                errors.append(
                    f"{provider.provider_id}: validation failed: "
                    + "; ".join(i.message for i in report.issues)
                )
                continue
            result = (payload, provider.provider_id, report)
            await self._write_cache(
                key,
                {
                    "forecast": [d.model_dump(mode="json") for d in payload],
                    "provider_used": provider.provider_id,
                    "validation": report.model_dump(mode="json"),
                },
                ttl=_CACHE_TTL_FORECAST_S,
            )
            return result
        raise ProviderUnavailable("All weather providers failed: " + "; ".join(errors))

    async def _read_cache(self, key: str, use_cache: bool):
        if not use_cache or self._cache is None:
            return None
        cached = await self._cache.get(key)
        if not cached:
            return None
        try:
            return (
                WeatherObservation.model_validate(cached["observation"]),
                cached["provider_used"],
                ValidationReport.model_validate(cached["validation"]),
            )
        except (KeyError, ValueError):
            return None  # corrupt cache entry -> refetch live

    async def _read_forecast_cache(self, key: str, use_cache: bool):
        if not use_cache or self._cache is None:
            return None
        cached = await self._cache.get(key)
        if not cached:
            return None
        try:
            return (
                [ForecastDay.model_validate(d) for d in cached["forecast"]],
                cached["provider_used"],
                ValidationReport.model_validate(cached["validation"]),
            )
        except (KeyError, ValueError):
            return None

    async def _write_cache(self, key: str, value: dict, ttl: int) -> None:
        if self._cache is None:
            return
        await self._cache.set(key, value, ttl=ttl)

    def _validate_observation(self, payload: WeatherObservation) -> ValidationReport:
        if self._validator is None:
            return ValidationReport(valid=True)
        return self._validator.validate_observation(payload)

    def _validate_forecast(self, payload: list[ForecastDay]) -> ValidationReport:
        if self._validator is None:
            return ValidationReport(valid=True)
        return self._validator.validate_forecast(payload)

    def statuses(self) -> list[ProviderStatus]:
        """Config-level availability for /health (no network pings)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result: list[ProviderStatus] = []
        for provider in self.providers:
            configured = provider.is_configured()
            result.append(
                ProviderStatus(
                    provider_id=provider.provider_id,
                    name=provider.name,
                    available=configured,
                    message=None if configured else "not configured",
                    last_checked=now,
                )
            )
        return result