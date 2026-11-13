"""Security middleware — audit logging, request validation, security headers."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        # HSTS only when not in development (HTTPS expected in staging/production)
        if settings.environment != "development":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Log security-sensitive operations for audit trail."""

    _SENSITIVE_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/password/change",
        "/api/v1/auth/password/reset",
    }

    _SENSITIVE_PREFIXES = (
        "/api/v1/organizations",
        "/api/v1/invitations",
    )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        path = request.url.path
        is_sensitive = path in self._SENSITIVE_PATHS or any(
            path.startswith(prefix) for prefix in self._SENSITIVE_PREFIXES
        )

        if is_sensitive:
            client_ip = request.client.host if request.client else "unknown"
            request_id = getattr(request.state, "request_id", "-")
            logger.info(
                "[AUDIT] [%s] %s %s -> %d (%.3fs) ip=%s",
                request_id,
                request.method,
                path,
                response.status_code,
                elapsed,
                client_ip,
            )
        return response


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    _MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._MAX_BODY_SIZE:
            return Response(
                content='{"error":{"code":"payload_too_large","message":"Request body too large"}}',
                status_code=413,
                media_type="application/json",
            )

        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.body()
                if b"\x00" in body:
                    return Response(
                        content='{"error":{"code":"invalid_body","message":"Invalid request body"}}',
                        status_code=400,
                        media_type="application/json",
                    )

        return await call_next(request)


def register_security_middleware(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditLoggingMiddleware)
    app.add_middleware(InputSanitizationMiddleware)
