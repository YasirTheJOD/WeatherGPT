"""Cache service tests — happy path and fail-open behaviour."""

import pytest

from app.core.cache import CacheService


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


class BrokenRedis:
    async def get(self, key):
        raise ConnectionError("redis is down")

    async def setex(self, key, ttl, value):
        raise ConnectionError("redis is down")

    async def delete(self, key):
        raise ConnectionError("redis is down")


async def test_set_get_roundtrip():
    cache = CacheService(prefix="test", client=FakeRedis())
    await cache.set("a:b", {"temperature_c": 28.4}, ttl=120)
    value = await cache.get("a:b")
    assert value == {"temperature_c": 28.4}


async def test_miss_returns_none():
    cache = CacheService(prefix="test", client=FakeRedis())
    assert await cache.get("missing") is None


async def test_fails_open_when_redis_down():
    cache = CacheService(prefix="test", client=BrokenRedis())
    assert await cache.get("a:b") is None  # no exception
    await cache.set("a:b", {"x": 1}, ttl=120)  # no exception
    await cache.delete("a:b")  # no exception


async def test_disabled_without_url_or_client():
    cache = CacheService(prefix="test", redis_url=None)
    assert await cache.get("a:b") is None
    await cache.set("a:b", {"x": 1}, ttl=120)  # no-op, no exception