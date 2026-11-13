"""Centralized error handlers with request correlation IDs.

Every error response includes a deterministic request_id so frontend and
operators can trace failures across services.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_request_id(request: Request) -> str:
    """Return the correlation ID attached by CorrelationIdMiddleware, or generate one."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.warning(
            "AppError [%s] %s: %s | request_id=%s",
            exc.status_code,
            exc.code,
            exc.detail,
            request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.detail,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _get_request_id(request)
        errors = []
        for err in exc.errors():
            loc = err.get("loc", [])
            field = ".".join(str(part) for part in loc if part != "body")
            errors.append({
                "field": field,
                "message": err.get("msg", "Invalid value"),
            })
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "request_id": request_id,
                    "details": errors,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _get_request_id(request)
        if exc.status_code >= 500:
            logger.error(
                "HTTPException %d: %s | request_id=%s",
                exc.status_code,
                exc.detail,
                request_id,
            )
        else:
            logger.info(
                "HTTPException %d: %s | request_id=%s",
                exc.status_code,
                exc.detail,
                request_id,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": exc.detail if exc.status_code != 500 else "Internal server error",
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.exception(
            "Unhandled exception [%s] request_id=%s path=%s",
            type(exc).__name__,
            request_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal server error",
                    "request_id": request_id,
                }
            },
        )
