import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.domain.models import Role, User, UserRole
from app.main import app
from app.core.middleware import RateLimitMiddleware
from app.core.security import hash_password
from app.repositories.user import UserRepository
from app.services.auth import AuthService

TEST_DATABASE_URL = "sqlite+aiosqlite://"

DEFAULT_ROLES = [
    ("admin", "System administrator with full access"),
    ("super_admin", "Platform super administrator"),
    ("organization_admin", "Organization administrator"),
    ("hr", "Human resources personnel (legacy)"),
    ("hr_manager", "HR manager"),
    ("recruiter", "Recruitment specialist"),
    ("candidate", "Job applicant"),
]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for name, desc in DEFAULT_ROLES:
                session.add(Role(name=name, description=desc))
            await session.commit()
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def connection(engine):
    conn = await engine.connect()
    await conn.begin()
    yield conn
    await conn.rollback()
    await conn.close()


@pytest_asyncio.fixture
async def session(connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_repo(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest_asyncio.fixture
async def auth_service(user_repo: UserRepository) -> AuthService:
    return AuthService(user_repo)


@pytest_asyncio.fixture
async def _create_user_with_role(session: AsyncSession):
    """Helper factory to create a user with a specific role directly in DB.
    Returns (user, password) tuple."""

    async def _factory(full_name: str, email: str, password: str, role_name: str):
        user = User(
            id=uuid.uuid4(),
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()

        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role:
            ur = UserRole(user_id=user.id, role_id=role.id)
            session.add(ur)
            await session.commit()
            await session.refresh(user)
        return user, password

    return _factory


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    RateLimitMiddleware._requests.clear()
    yield
    RateLimitMiddleware._requests.clear()


@pytest.fixture(autouse=True)
def _block_external_services(monkeypatch):
    """Tests must never touch real SMTP servers or Redis brokers.

    - smtplib.SMTP is replaced with a mock so configured credentials from a
      developer's local .env can never cause outbound network calls.
    - Celery broker detection always reports unavailable, forcing the local
      synchronous fallback path inside tests.
    """
    from unittest.mock import MagicMock

    import app.notifications.email_tasks as email_tasks_mod
    import app.services.email_service as email_service_mod
    import app.services.applications.screening_scheduler as screening_scheduler_mod
    import app.services.simulation.scheduler as simulation_scheduler_mod

    monkeypatch.setattr(email_service_mod.smtplib, "SMTP", MagicMock(name="SMTPMock"))
    monkeypatch.setattr(email_tasks_mod, "_celery_available", lambda: False)
    monkeypatch.setattr(screening_scheduler_mod, "_celery_available", lambda: False)
    monkeypatch.setattr(simulation_scheduler_mod, "_celery_available", lambda: False)
    yield
