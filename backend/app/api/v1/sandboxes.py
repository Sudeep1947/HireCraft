"""Hiring Strategy Sandbox API (Phase 12).

Provides CRUD for sandboxes and strategy management within sandboxes.
Reuses existing simulation infrastructure for scenario creation and comparison.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.logging import get_logger
from app.db.session import get_db
from app.domain.hiring_strategy_sandbox_schemas import (
    SandboxCompareRequest,
    SandboxCreate,
    SandboxListResponse,
    SandboxResponse,
    SandboxUpdate,
    StrategyCreate,
    StrategyDuplicate,
    StrategyListResponse,
    StrategyResponse,
    StrategyUpdate,
    SandboxActivityResponse,
)
from app.domain.models import User
from app.services.sandbox.hiring_strategy_sandbox_service import HiringStrategySandboxService

logger = get_logger(__name__)

router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])


def _get_service(db: AsyncSession = Depends(get_db)) -> HiringStrategySandboxService:
    return HiringStrategySandboxService(db)


# ─── Sandbox CRUD ───────────────────────────────────────────────────


@router.post("", response_model=SandboxResponse, status_code=201)
async def create_sandbox(
    body: SandboxCreate,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Create a new Hiring Strategy Sandbox with a baseline snapshot."""
    return await service.create_sandbox(current_user, body)


@router.get("", response_model=SandboxListResponse)
async def list_sandboxes(
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """List sandboxes the user has access to."""
    return await service.list_sandboxes(current_user)


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get a sandbox with full details."""
    import uuid
    return await service.get_sandbox(current_user, uuid.UUID(sandbox_id))


@router.patch("/{sandbox_id}", response_model=SandboxResponse)
async def update_sandbox(
    sandbox_id: str,
    body: SandboxUpdate,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Update sandbox name or description."""
    import uuid
    return await service.update_sandbox(current_user, uuid.UUID(sandbox_id), body)


@router.delete("/{sandbox_id}", status_code=204)
async def delete_sandbox(
    sandbox_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Delete a sandbox and all its strategies."""
    import uuid
    await service.delete_sandbox(current_user, uuid.UUID(sandbox_id))


@router.post("/{sandbox_id}/archive", response_model=SandboxResponse)
async def archive_sandbox(
    sandbox_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Archive a sandbox."""
    import uuid
    return await service.archive_sandbox(current_user, uuid.UUID(sandbox_id))


# ─── Strategy Management ────────────────────────────────────────────


@router.post("/{sandbox_id}/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    sandbox_id: str,
    body: StrategyCreate,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Create a new strategy inside a sandbox."""
    import uuid
    return await service.create_strategy(current_user, uuid.UUID(sandbox_id), body)


@router.get("/{sandbox_id}/strategies", response_model=StrategyListResponse)
async def list_strategies(
    sandbox_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """List all strategies in a sandbox."""
    import uuid
    return await service.list_strategies(current_user, uuid.UUID(sandbox_id))


@router.get("/{sandbox_id}/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    sandbox_id: str,
    strategy_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get a single strategy."""
    import uuid
    return await service.get_strategy(current_user, uuid.UUID(sandbox_id), uuid.UUID(strategy_id))


@router.patch("/{sandbox_id}/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    sandbox_id: str,
    strategy_id: str,
    body: StrategyUpdate,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Update strategy name, tags, or notes."""
    import uuid
    return await service.update_strategy(
        current_user, uuid.UUID(sandbox_id), uuid.UUID(strategy_id), body,
    )


@router.post(
    "/{sandbox_id}/strategies/{strategy_id}/duplicate",
    response_model=StrategyResponse,
    status_code=201,
)
async def duplicate_strategy(
    sandbox_id: str,
    strategy_id: str,
    body: StrategyDuplicate,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Duplicate or branch an existing strategy."""
    import uuid
    return await service.duplicate_strategy(
        current_user, uuid.UUID(sandbox_id), uuid.UUID(strategy_id), body,
    )


@router.delete("/{sandbox_id}/strategies/{strategy_id}", status_code=204)
async def remove_strategy(
    sandbox_id: str,
    strategy_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Remove a strategy from the sandbox."""
    import uuid
    await service.remove_strategy(current_user, uuid.UUID(sandbox_id), uuid.UUID(strategy_id))


# ─── Comparison ──────────────────────────────────────────────────────


@router.post("/{sandbox_id}/compare")
async def compare_strategies(
    sandbox_id: str,
    body: SandboxCompareRequest,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Compare selected strategies using Phase 10 multi-scenario comparison."""
    import uuid
    return await service.compare_strategies(current_user, uuid.UUID(sandbox_id), body)


# ─── Activity ────────────────────────────────────────────────────────


@router.get("/{sandbox_id}/activity", response_model=SandboxActivityResponse)
async def get_activity(
    sandbox_id: str,
    service: HiringStrategySandboxService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get recent activity for a sandbox."""
    import uuid
    return await service.get_activity(current_user, uuid.UUID(sandbox_id))
