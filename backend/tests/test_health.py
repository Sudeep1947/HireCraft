import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    # May be 200 (all healthy) or 503 (Redis unavailable in test env)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "environment" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


@pytest.mark.asyncio
async def test_liveness_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_endpoint(client: AsyncClient, session) -> None:
    from unittest.mock import AsyncMock, patch
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_factory():
        yield session

    with patch("app.api.v1.health.async_session_factory", mock_session_factory):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data
