"""Registry cache tests — the Redis cache sits between the API and the chain."""

import pytest

from app.core.cache import CacheService
from app.domain.models import Provenance, ValidationReport, WeatherObservation
from app.providers.base import LocationQuery, ProviderRegistry
from datetime import datetime, timezone


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


class CountingProvider:
    provider_id = "counting"
    name = "Counting Provider"
    calls = 0

    def __init__(self):
        self.calls = 0

    def is_configured(self):
        return True

    async def current_weather(self, location):
        self.calls += 1
        return WeatherObservation(
            latitude=location.latitude,
            longitude=location.longitude,
            temperature_c=28.4,
            provenance=Provenance(
                source_id=self.provider_id, source_name=self.name, authoritative=False,
                fetched_at=datetime.now(timezone.utc), ttl_seconds=300,
            ),
        )

    async def daily_forecast(self, location, days=7):
        self.calls += 1
        return []


async def test_second_call_hits_cache():
    provider = CountingProvider()
    cache = CacheService(prefix="test", client=FakeRedis())
    registry = ProviderRegistry([provider], cache=cache)
    location = LocationQuery(latitude=22.57, longitude=88.36)

    first, provider_id, validation = await registry.current_weather(location)
    assert provider.calls == 1
    assert first.temperature_c == 28.4

    second, _, _ = await registry.current_weather(location)
    assert provider.calls == 1  # served from cache
    assert second.temperature_c == 28.4
    assert second.provenance.source_id == "counting"


async def test_use_cache_false_bypasses_cache():
    provider = CountingProvider()
    cache = CacheService(prefix="test", client=FakeRedis())
    registry = ProviderRegistry([provider], cache=cache)
    location = LocationQuery(latitude=22.57, longitude=88.36)

    await registry.current_weather(location)
    await registry.current_weather(location, use_cache=False)
    assert provider.calls == 2


async def test_no_cache_configured_still_works():
    provider = CountingProvider()
    registry = ProviderRegistry([provider])
    location = LocationQuery(latitude=22.57, longitude=88.36)

    first, provider_id, validation = await registry.current_weather(location)
    assert provider.calls == 1
    assert validation.valid is True
    assert provider_id == "counting"