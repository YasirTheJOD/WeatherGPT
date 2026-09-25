"""Pure-ASGI middlewares: request context (request IDs + access logs) and
rate limiting.

Deliberately raw ASGI rather than ``BaseHTTPMiddleware``: ``/chat`` streams
SSE, and ``BaseHTTPMiddleware`` wraps the response in a way that can buffer or
otherwise interfere with a long-lived stream. These middlewares only observe
``http.response.start`` and never touch the body.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.core.logging import (
    REQUEST_ID_HEADER,
    log_event,
    reset_request_id,
    set_request_id,
)
from app.core.rate_limit import RateLimiter

logger = logging.getLogger("app.http")

_RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
}


def _header(scope: dict, name: str) -> str | None:
    target = name.lower().encode()
    for key, value in scope.get("headers") or []:
        if key == target:
            return value.decode("latin-1")
    return None


def client_ip(scope: dict) -> str:
    """Best-effort client identity for rate limiting.

    Prefers the first ``X-Forwarded-For`` hop so the limit still works behind
    the deployment reverse proxy, and falls back to the socket peer.
    """
    forwarded = _header(scope, "X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    client = scope.get("client")
    if client:
        return str(client[0])
    return "unknown"


class RequestContextMiddleware:
    """Mint/propagate an ``X-Request-ID`` and emit a structured access log."""

    def __init__(self, app, header_name: str = REQUEST_ID_HEADER):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header(scope, self.header_name) or uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((self.header_name.lower().encode(), request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log_event(
                logger,
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status["code"],
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                client=client_ip(scope),
            )
            reset_request_id(token)


class RateLimitMiddleware:
    """Return 429 when a client exceeds the window; pass through when disabled."""

    def __init__(
        self,
        app,
        limiter: RateLimiter,
        prefix: str = "/api/v1",
        exempt_paths: set[str] | None = None,
    ):
        self.app = app
        self.limiter = limiter
        self.prefix = prefix
        self.exempt_paths = exempt_paths or set()

    def _applies(self, scope: dict) -> bool:
        if scope.get("type") != "http":
            return False
        if not self.limiter.enabled:
            return False
        path = scope.get("path", "")
        if not path.startswith(self.prefix):
            return False
        return path not in self.exempt_paths

    async def __call__(self, scope, receive, send):
        if not self._applies(scope):
            await self.app(scope, receive, send)
            return

        result = await self.limiter.check(client_ip(scope))
        if not result.allowed:
            log_event(
                logger,
                "rate_limited",
                level=logging.WARNING,
                path=scope.get("path"),
                client=client_ip(scope),
            )
            await self._reject(scope, receive, send, result)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and not result.degraded:
                headers = message.setdefault("headers", [])
                headers.extend(
                    [
                        (b"x-ratelimit-limit", str(result.limit).encode()),
                        (b"x-ratelimit-remaining", str(result.remaining).encode()),
                        (b"x-ratelimit-reset", str(result.reset_after).encode()),
                    ]
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _reject(self, scope, receive, send, result) -> None:
        body = (
            b'{"detail":{"message":"Too many requests. Please slow down.",'
            b'"retry_after_seconds":' + str(result.reset_after).encode() + b"}}"
        )
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(result.reset_after).encode()),
                    (b"x-ratelimit-limit", str(result.limit).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                    (b"x-ratelimit-reset", str(result.reset_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
