"""Redis-backed JSON cache.

Fails open by design: if Redis is down (or not installed on a demo machine),
`get` returns None and `set` is a no-op — the provider chain serves live data
and nothing breaks. TTLs come from the caller (weather obs ~2 min, forecasts
~10 min, feed etag stays in app state).
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(
        self,
        redis_url: str | None = None,
        prefix: str = "wgt",
        client=None,  # injectable for tests (must implement get/setex/delete)
    ):
        self._redis_url = redis_url
        self._prefix = prefix
        self._redis = client
        self._disabled = redis_url is None and client is None

    def _client(self):
        if self._disabled:
            return None
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(self._redis_url, socket_connect_timeout=2)
        return self._redis

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> dict | None:
        client = self._client()
        if client is None:
            return None
        try:
            raw = await client.get(self._key(key))
            if not raw:
                return None
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except Exception as exc:  # fail open on any redis error
            logger.warning("cache get failed (failing open): %s", exc)
            return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        client = self._client()
        if client is None:
            return
        try:
            await client.setex(self._key(key), ttl, json.dumps(value))
        except Exception as exc:  # fail open
            logger.warning("cache set failed (failing open): %s", exc)

    async def delete(self, key: str) -> None:
        client = self._client()
        if client is None:
            return
        try:
            await client.delete(self._key(key))
        except Exception as exc:
            logger.warning("cache delete failed (failing open): %s", exc)