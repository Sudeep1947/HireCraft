"""Health and readiness endpoints for production monitoring.

/health        — full health report (DB + Redis + version)
/health/live   — liveness probe (process is running)
/health/ready  — readiness probe (can serve traffic)
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import async_session_factory

router = APIRouter(tags=["health"])
logger = get_logger(__name__)
settings = get_settings()


async def _check_database() -> tuple[bool, str]:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        logger.error("Health check DB failure: %s", exc)
        return False, f"error: {type(exc).__name__}"


async def _check_redis() -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(str(settings.redis_url), socket_timeout=1)
        await r.ping()
        await r.aclose()
        return True, "connected"
    except Exception as exc:
        logger.warning("Health check Redis failure: %s", exc)
        return False, f"error: {type(exc).__name__}"


@router.get("/health")
async def health_check():
    """Full health report - checks all critical dependencies."""
    db_ok, db_msg = await _check_database()
    redis_ok, redis_msg = await _check_redis()

    is_healthy = db_ok
    status_code = 200 if is_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "version": settings.app_version,
            "environment": settings.environment,
            "checks": {
                "database": {"status": "ok" if db_ok else "fail", "message": db_msg},
                "redis": {
                    "status": "ok" if (redis_ok or settings.environment == "development") else "degraded",
                    "message": redis_msg if redis_ok else "in-memory fallback (active)",
                },
            },
            "timestamp": time.time(),
        },
    )


@router.get("/health/live")
async def liveness_check():
    """Liveness probe — process is running and responsive."""
    return {"status": "alive", "timestamp": time.time()}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — can serve traffic (DB required, Redis recommended)."""
    db_ok, db_msg = await _check_database()

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {
                    "database": {"status": "fail", "message": db_msg},
                },
                "timestamp": time.time(),
            },
        )

    redis_ok, redis_msg = await _check_redis()
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": {
                "database": {"status": "ok", "message": db_msg},
                "redis": {"status": "ok" if redis_ok else "degraded", "message": redis_msg},
            },
            "timestamp": time.time(),
        },
    )
