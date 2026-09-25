"""Per-client rate limiting — Redis fixed window, fails open.

Phase 6 hardening (§8 in docs/ARCHITECTURE.md): "Rate limiting per IP via
Redis". The semantics are deliberately demo-safe:

  - Redis present  -> a fixed-window counter (INCR + EXPIRE) per client key.
  - Redis absent / any Redis error -> the check allows the request and reports
    ``degraded=True``. The prototype must never fail a chat request because an
    optional cache is down (same fail-open philosophy as core/cache.py).

The limiter is transport-agnostic; ``RateLimitMiddleware`` (core/middleware.py)
is the HTTP adapter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int  # seconds until the window resets
    degraded: bool = False  # True when Redis was unavailable (fail-open)


class RateLimiter:
    def __init__(
        self,
        redis_url: str | None = None,
        limit: int = 60,
        window_seconds: int = 60,
        enabled: bool = True,
        prefix: str = "wgt",
        client=None,  # injectable for tests (must implement incr/expire/ttl)
    ):
        self._redis_url = redis_url
        self._limit = max(1, limit)
        self._window = max(1, window_seconds)
        self._enabled = enabled
        self._prefix = prefix
        self._redis = client

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window_seconds(self) -> int:
        return self._window

    def _client(self):
        if self._redis_url is None and self._redis is None:
            return None
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(self._redis_url, socket_connect_timeout=2)
        return self._redis

    def _allowed(self, remaining: int | None = None) -> RateLimitResult:
        return RateLimitResult(
            allowed=True,
            limit=self._limit,
            remaining=self._limit if remaining is None else remaining,
            reset_after=self._window,
        )

    async def check(self, key: str) -> RateLimitResult:
        if not self._enabled:
            return self._allowed()
        client = self._client()
        if client is None:
            return self._allowed()  # no Redis configured -> fail open
        try:
            cache_key = f"{self._prefix}:ratelimit:{key}"
            count = await client.incr(cache_key)
            if count == 1:
                await client.expire(cache_key, self._window)
            ttl = await client.ttl(cache_key)
            reset_after = ttl if isinstance(ttl, int) and ttl > 0 else self._window
            remaining = max(0, self._limit - int(count))
            if count > self._limit:
                return RateLimitResult(
                    allowed=False,
                    limit=self._limit,
                    remaining=0,
                    reset_after=reset_after,
                )
            return RateLimitResult(
                allowed=True,
                limit=self._limit,
                remaining=remaining,
                reset_after=reset_after,
            )
        except Exception as exc:  # fail open on any redis error
            logger.warning("rate limit check failed (failing open): %s", exc)
            return RateLimitResult(
                allowed=True,
                limit=self._limit,
                remaining=self._limit,
                reset_after=self._window,
                degraded=True,
            )
