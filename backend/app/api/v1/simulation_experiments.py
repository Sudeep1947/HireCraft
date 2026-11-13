"""Phase 14: Advanced Simulation & Research Intelligence API.

Endpoints for controlled parameter experiments, sensitivity analysis,
robustness testing, and stability analysis. All analysis is READ-ONLY
with respect to live hiring data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.logging import get_logger
from app.db.session import get_db
from app.domain.enums import AuditEventType
from app.domain.models import User
from app.domain.simulation_experiment_schemas import (
    ExperimentComparisonRequest,
    ExperimentComparisonResponse,
    ExperimentCreate,
    ExperimentExecuteRequest,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentStatusResponse,
    ExperimentUpdate,
    ExperimentResultsResponse,
    FairnessSensitivityResponse,
    RobustnessAnalysisResponse,
    SensitivityAnalysisResponse,
    StabilityAnalysisResponse,
)
from app.services.simulation.experiment_service import ExperimentService

logger = get_logger(__name__)

router = APIRouter(prefix="/simulation-experiments")


def _get_experiment_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    return ExperimentService(db)


@router.post("", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Create a new controlled parameter experiment."""
    return await svc.create_experiment(current_user, body)


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """List experiments for the current user's organization."""
    return await svc.list_experiments(current_user, page=page, page_size=page_size)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get experiment details including results and analysis."""
    return await svc.get_experiment(experiment_id, current_user)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentUpdate,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Update an experiment (only DRAFT status)."""
    return await svc.update_experiment(experiment_id, current_user, body)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Delete an experiment."""
    await svc.delete_experiment(experiment_id, current_user)


@router.post("/{experiment_id}/execute", response_model=ExperimentStatusResponse)
async def execute_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentExecuteRequest | None = None,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Execute an experiment — generates configurations and queues execution."""
    return await svc.execute_experiment(experiment_id, current_user)


@router.post("/{experiment_id}/cancel", response_model=ExperimentStatusResponse)
async def cancel_experiment(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Cancel a running or queued experiment."""
    return await svc.cancel_experiment(experiment_id, current_user)


@router.get("/{experiment_id}/status", response_model=ExperimentStatusResponse)
async def get_experiment_status(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get experiment execution status with progress."""
    return await svc.get_status(experiment_id, current_user)


@router.get("/{experiment_id}/results", response_model=ExperimentResultsResponse)
async def get_experiment_results(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get all configuration results for an experiment."""
    return await svc.get_results(experiment_id, current_user)


@router.get("/{experiment_id}/sensitivity", response_model=SensitivityAnalysisResponse)
async def get_sensitivity_analysis(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get parameter sensitivity analysis."""
    return await svc.get_sensitivity(experiment_id, current_user)


@router.get("/{experiment_id}/robustness", response_model=RobustnessAnalysisResponse)
async def get_robustness_analysis(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get robustness analysis profile."""
    return await svc.get_robustness(experiment_id, current_user)


@router.get("/{experiment_id}/stability", response_model=StabilityAnalysisResponse)
async def get_stability_analysis(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get ranking and shortlist stability analysis."""
    return await svc.get_stability(experiment_id, current_user)


@router.get(
    "/{experiment_id}/fairness-sensitivity",
    response_model=FairnessSensitivityResponse,
)
async def get_fairness_sensitivity(
    experiment_id: uuid.UUID,
    svc: ExperimentService = Depends(_get_experiment_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get fairness metric sensitivity across parameter values."""
    return await svc.get_fairness_sensitivity(experiment_id, current_user)
