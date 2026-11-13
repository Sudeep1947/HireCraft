"""Database session management with connection pooling and health checks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

is_sqlite = "sqlite" in str(settings.database_url)

# Production-grade engine configuration
engine_kwargs: dict = {
    "echo": settings.database_echo,
}

if is_sqlite:
    engine_kwargs["poolclass"] = NullPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pool tuning
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,  # seconds to wait for a connection
        "pool_recycle": 1800,  # recycle connections after 30 min
        "pool_pre_ping": True,  # detect stale connections
    })

engine = create_async_engine(str(settings.database_url), **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            logger.debug("Rolling back session due to exception")
            try:
                await session.rollback()
            except Exception:
                logger.warning("Session rollback itself failed")
            raise
        finally:
            await session.close()


async def check_database_health() -> tuple[bool, str]:
    """Check database connectivity. Returns (ok, message)."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False, f"disconnected: {type(exc).__name__}"
