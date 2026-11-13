"""Core middleware — request logging, rate limiting, correlation IDs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request_id to every request for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "[%s] %s %s -> %d (%.3fs)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter.

    NOTE: For multi-worker production deployments, replace with Redis-backed
    rate limiting (e.g., slowapi). This implementation is sufficient for
    single-worker development and testing.
    """

    _requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = settings.rate_limit_window_seconds
        max_requests = settings.rate_limit_requests

        timestamps = self._requests.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < window]

        if len(timestamps) >= max_requests:
            retry_after = int(window - (now - timestamps[0]))
            raise RateLimitError(
                detail="Too many requests",
                extra={"retry_after": retry_after, "limit": max_requests, "window": window},
            )

        timestamps.append(now)
        self._requests[client_ip] = timestamps

        # Periodic cleanup to prevent memory leak from stale IPs
        if len(self._requests) > 10000:
            self._cleanup(now, window)

        return await call_next(request)

    @classmethod
    def _cleanup(cls, now: float, window: float) -> None:
        """Remove IPs whose last request is older than the window."""
        stale = [
            ip for ip, ts in cls._requests.items()
            if not ts or now - ts[-1] > window * 2
        ]
        for ip in stale:
            del cls._requests[ip]


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
