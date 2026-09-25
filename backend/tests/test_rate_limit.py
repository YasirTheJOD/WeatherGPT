"""Rate limiter tests — window behaviour, headers, fail-open, exemptions."""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RateLimitMiddleware
from app.core.rate_limit import RateLimiter


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, ttl):
        self.expires[key] = ttl
        return True

    async def ttl(self, key):
        return self.expires.get(key, -1)


class BrokenRedis:
    async def incr(self, key):
        raise ConnectionError("redis is down")

    async def expire(self, key, ttl):
        raise ConnectionError("redis is down")

    async def ttl(self, key):
        raise ConnectionError("redis is down")


def _app(limiter: RateLimiter) -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/thing")
    async def thing() -> dict:
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.add_middleware(
        RateLimitMiddleware, limiter=limiter, prefix="/api/v1", exempt_paths={"/api/v1/health"}
    )
    return TestClient(app)


async def test_allows_under_limit_and_counts_down():
    limiter = RateLimiter(limit=3, window_seconds=60, client=FakeRedis())
    first = await limiter.check("1.2.3.4")
    assert first.allowed is True
    assert first.remaining == 2
    second = await limiter.check("1.2.3.4")
    assert second.allowed is True
    assert second.remaining == 1


async def test_blocks_over_limit_with_retry_after():
    limiter = RateLimiter(limit=2, window_seconds=30, client=FakeRedis())
    assert (await limiter.check("ip")).allowed is True
    assert (await limiter.check("ip")).allowed is True
    blocked = await limiter.check("ip")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.reset_after == 30


async def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window_seconds=60, client=FakeRedis())
    assert (await limiter.check("a")).allowed is True
    assert (await limiter.check("b")).allowed is True
    assert (await limiter.check("a")).allowed is False


async def test_fails_open_when_redis_errors(caplog):
    limiter = RateLimiter(limit=1, window_seconds=60, client=BrokenRedis())
    with caplog.at_level(logging.WARNING):
        result = await limiter.check("ip")
    assert result.allowed is True
    assert result.degraded is True


async def test_fails_open_when_unconfigured():
    limiter = RateLimiter(limit=1, redis_url=None)
    result = await limiter.check("ip")
    assert result.allowed is True
    assert result.degraded is False  # unconfigured is by design, not degraded


async def test_disabled_always_allows():
    limiter = RateLimiter(limit=1, enabled=False, client=FakeRedis())
    assert (await limiter.check("ip")).allowed is True
    assert (await limiter.check("ip")).allowed is True


def test_middleware_returns_429_and_headers():
    client = _app(RateLimiter(limit=2, window_seconds=45, client=FakeRedis()))
    ok = client.get("/api/v1/thing")
    assert ok.status_code == 200
    assert ok.headers["x-ratelimit-limit"] == "2"
    assert ok.headers["x-ratelimit-remaining"] == "1"
    assert client.get("/api/v1/thing").status_code == 200
    blocked = client.get("/api/v1/thing")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "45"
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert "Too many requests" in blocked.json()["detail"]["message"]


def test_middleware_exempts_health():
    client = _app(RateLimiter(limit=1, window_seconds=60, client=FakeRedis()))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    # ... while the limited path still counts.
    assert client.get("/api/v1/thing").status_code == 200
    assert client.get("/api/v1/thing").status_code == 429


def test_middleware_ignores_non_api_paths():
    client = _app(RateLimiter(limit=1, window_seconds=60, client=FakeRedis()))
    # "/" does not match the /api/v1 prefix -> never limited (404 from routing).
    assert client.get("/").status_code == 404
    assert client.get("/").status_code == 404
