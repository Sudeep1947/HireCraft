import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.domain.models import User
from app.domain.screening_schemas import (
    AdversarialTestResponse,
    CandidateFairnessResponse,
    FairnessMetricsResponse,
    FairnessOverviewResponse,
    FairnessReportResponse,
    JDAnalysisResponse,
)
from app.services.fairness.fairness_engine import FairnessEngine
from app.services.screening.access import (
    JobAccessDeniedError,
    JobNotFoundError,
    authorize_job_access,
    authorized_job_ids,
)

router = APIRouter(prefix="/fairness", tags=["fairness"])


def _get_fairness_engine(db: AsyncSession = Depends(get_db)) -> FairnessEngine:
    return FairnessEngine(db)


async def _scoped_job_ids(db: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """The jobs this caller may read fairness data for.

    ``None`` means unrestricted and is returned only for a platform admin.
    Everyone else gets an explicit list -- including an empty one, which yields
    empty results rather than platform-wide data. An empty list must never be
    treated as "no filter".
    """
    return await authorized_job_ids(db, user)


async def _require_job(db: AsyncSession, user: User, job_id: uuid.UUID) -> None:
    """Authorize a job-scoped fairness read.

    Raises the same 403/404 pair as the screening workflow, so an unauthorized
    caller cannot distinguish "exists but not yours" from "does not exist".
    """
    try:
        await authorize_job_access(db, job_id, user)
    except (NotFoundError, JobNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ForbiddenError, JobAccessDeniedError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))


# --- Fairness Overview ---

@router.get("/overview", response_model=FairnessOverviewResponse)
async def get_fairness_overview(
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """Platform overview, narrowed to the caller's authorized jobs."""
    return await engine.get_fairness_overview(
        job_ids=await _scoped_job_ids(db, current_user),
    )


# --- Fairness Metrics ---

@router.get("/metrics", response_model=FairnessMetricsResponse)
async def get_fairness_metrics(
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """Score-distribution metrics, narrowed to the caller's authorized jobs."""
    return await engine.get_fairness_metrics(
        job_ids=await _scoped_job_ids(db, current_user),
    )


# --- Fairness Report for Job ---

@router.get("/report/{job_id}", response_model=FairnessReportResponse)
async def get_fairness_report(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    await _require_job(db, current_user, job_id)
    result = await engine.get_fairness_report(job_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Analyze Fairness ---

@router.post("/analyze")
async def analyze_fairness(
    job_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """Analyze one job, or the caller's authorized jobs when ``job_id`` is absent."""
    if job_id is not None:
        await _require_job(db, current_user, job_id)
    result = await engine.analyze_fairness(
        job_id, job_ids=await _scoped_job_ids(db, current_user),
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Detect Ranking Bias ---

@router.get("/bias-detection/{job_id}")
async def detect_ranking_bias(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    await _require_job(db, current_user, job_id)
    return await engine.detect_ranking_bias(job_id)


# --- Adversarial Test ---

@router.post("/adversarial-test", response_model=AdversarialTestResponse)
async def run_adversarial_test(
    job_id: uuid.UUID = Query(...),
    candidate_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """Run an explicit adversarial test for a candidate against a job.

    The job is authorized first, then the engine requires a stored screening
    result for that exact (job, candidate) pair, so the candidate id cannot be
    pointed at someone outside the caller's jobs to expose their screening.

    This is the only route that starts a run. Viewing a screening never triggers
    one.
    """
    await _require_job(db, current_user, job_id)
    result = await engine.run_adversarial_test(job_id, candidate_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- JD Bias Analysis ---

@router.get("/jd-analysis/{job_id}", response_model=JDAnalysisResponse)
async def analyze_job_description(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    await _require_job(db, current_user, job_id)
    result = await engine.analyze_job_description(job_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Bias Alerts ---

@router.get("/bias-alerts")
async def get_bias_alerts(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    return await engine.get_bias_alerts(
        limit, job_ids=await _scoped_job_ids(db, current_user),
    )


# --- Candidate Fairness View ---

@router.get("/candidate/{candidate_id}", response_model=CandidateFairnessResponse)
async def get_candidate_fairness(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("hr", "recruiter", "admin")),
):
    """Fairness record for a candidate, limited to the caller's authorized jobs.

    A candidate with no screening inside the caller's scope returns 404, so this
    cannot be used to discover which candidates were screened elsewhere.
    """
    result = await engine.get_candidate_fairness(
        candidate_id, job_ids=await _scoped_job_ids(db, current_user),
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# --- Candidate Self Fairness View ---

@router.get("/my-fairness", response_model=CandidateFairnessResponse)
async def get_my_fairness(
    engine: FairnessEngine = Depends(_get_fairness_engine),
    current_user: User = Depends(require_role("candidate")),
):
    """The candidate's own transparency view.

    Already scoped by the authenticated identity, so no job filter applies and
    this must not be given one: the candidate is entitled to their own record
    across every job they applied to.
    """
    result = await engine.get_candidate_fairness(current_user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
