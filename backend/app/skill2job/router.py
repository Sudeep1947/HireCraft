from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.logging import get_logger
from app.db.session import get_db
from app.domain.models import User
from app.skill2job.adapters.candidate_adapter import CandidateAdapter
from app.skill2job.perception.pipeline import PerceptionValidationError
from app.skill2job.profile.schemas import ReviewRequest, ReviewResult
from app.skill2job.jobs.schemas import (
    CuratedJobCounts,
    CuratedJobFilters,
    CuratedJobPage,
    JobSeedResponse,
    SkillDemandResponse,
)
from app.skill2job.matching.schemas import (
    JobMatchDetail,
    JobMatchRequest,
    JobMatchResponse,
)
from app.skill2job.gap.schemas import SkillGapAnalysis, SkillGapRequest, SkillGapSummary
from app.skill2job.opportunity.schemas import (
    OpportunityDashboard,
    OpportunityImpactResponse,
    SimulationRequest,
    SimulationResult,
)
from app.skill2job.training.schemas import ModuleProgressRequest, TrainingPlan, TimeToReadyRequest, WhatIfRequest
from app.skill2job.learning.schemas import ResourceListResponse, ResourceMappingResponse
from app.skill2job.schemas import (
    InterestsUpdate,
    PerceptionListResponse,
    PerceptionStatusResponse,
    Skill2JobCapabilities,
    Skill2JobHealth,
    Skill2JobProfileResponse,
)
from app.skill2job.service import Skill2JobService

router = APIRouter(prefix="/skill2job", tags=["skill2job"])
logger = get_logger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> Skill2JobService:
    return Skill2JobService(candidate_adapter=CandidateAdapter(db), session=db)


@router.get("/health", response_model=Skill2JobHealth, summary="Skill2Job module availability")
async def skill2job_health(
    service: Skill2JobService = Depends(_get_service),
):
    return service.check_health()


@router.get("/capabilities", response_model=Skill2JobCapabilities, summary="Phase-aware capability & implementation-status report (admin)")
async def skill2job_capabilities(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("super_admin", "admin")),
):
    return await service.get_capabilities(current_user.id)


@router.get("/profile", response_model=Skill2JobProfileResponse, summary="Existing candidate profile")
async def skill2job_profile(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_profile(current_user.id)


@router.get("/profile/interests", response_model=dict, summary="Candidate interests (persisted)")
async def skill2job_interests_get(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return {"interests": await service.get_interests(current_user.id)}


@router.put("/profile/interests", response_model=dict, summary="Save candidate interests")
async def skill2job_interests_put(
    payload: InterestsUpdate,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return {"interests": await service.set_interests(current_user.id, payload.interests)}


@router.get(
    "/perception/status",
    response_model=PerceptionStatusResponse,
    summary="Perception provider availability",
)
async def skill2job_perception_status(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_perception_status()


@router.post(
    "/perception/upload",
    response_model=dict,
    summary="Perceive a resume / document / image / audio upload",
)
async def skill2job_perception_upload(
    file: UploadFile = File(...),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    content = await file.read()
    try:
        result = await service.perceive_upload(current_user.id, file.filename or "upload", content)
        # Include skill count for frontend display
        result_data = result.get("result", {})
        result["skill_count"] = len(result_data.get("skills", []))
        result["processing_status"] = result_data.get("processing_status", "unknown")
        result["processing_message"] = result_data.get("processing_message")
        return result
    except PerceptionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Perception upload failed")
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {exc}"
        )


@router.post(
    "/perception/text",
    response_model=dict,
    summary="Perceive pasted free text",
)
async def skill2job_perception_text(
    text: str = Form(...),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    try:
        result = await service.perceive_text(current_user.id, text)
        # Include skill count for frontend display
        result_data = result.get("result", {})
        result["skill_count"] = len(result_data.get("skills", []))
        result["processing_status"] = result_data.get("processing_status", "unknown")
        result["processing_message"] = result_data.get("processing_message")
        return result
    except PerceptionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Text perception failed")
        raise HTTPException(
            status_code=500,
            detail=f"Text processing failed: {exc}"
        )


@router.get(
    "/perception",
    response_model=PerceptionListResponse,
    summary="List the candidate's perception history",
)
async def skill2job_perception_history(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_perceptions(current_user.id)


@router.get(
    "/perception/{perception_id}",
    response_model=dict,
    summary="Get full details of a perception record",
)
async def skill2job_perception_detail(
    perception_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    detail = await service.get_perception_detail(current_user.id, perception_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Perception record not found")
    return detail


@router.delete(
    "/perception/{perception_id}",
    response_model=dict,
    summary="Delete a perception record",
)
async def skill2job_perception_delete(
    perception_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    deleted = await service.delete_perception(current_user.id, perception_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Perception record not found")
    return {"deleted": True, "perception_id": perception_id}


@router.post(
    "/profile/agent/dossier",
    response_model=dict,
    summary="Build the candidate profile dossier (Phase 3 Profile Agent)",
)
async def skill2job_profile_dossier_build(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.build_profile_dossier(current_user.id)


@router.get(
    "/profile/agent/dossier",
    response_model=dict | None,
    summary="Get the last built candidate profile dossier",
)
async def skill2job_profile_dossier_get(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_profile_dossier(current_user.id)


@router.post(
    "/profile/agent/review",
    response_model=ReviewResult,
    summary="Accept / modify / reject profile suggestions (human-in-the-loop)",
)
async def skill2job_profile_review(
    request: ReviewRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.apply_profile_review(current_user.id, request)


@router.get(
    "/jobs/catalog",
    response_model=CuratedJobPage,
    summary="Browse the curated local job catalog (Phase 4)",
)
async def skill2job_jobs_catalog(
    location: str | None = None,
    remote_only: bool = False,
    keyword: str | None = None,
    role_keyword: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    filters = CuratedJobFilters(
        location=location,
        remote_only=remote_only,
        keyword=keyword,
        role_keyword=role_keyword,
        limit=limit,
        offset=offset,
    )
    return await service.list_local_jobs(filters)


@router.get(
    "/jobs/counts",
    response_model=CuratedJobCounts,
    summary="Curated job catalog counts for the dashboard",
)
async def skill2job_jobs_counts(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_local_job_counts(current_user.id)


@router.get(
    "/jobs/matched",
    response_model=list[dict],
    summary="Jobs fetched for the candidate's profile (Phase 4 local intelligence)",
)
async def skill2job_jobs_matched(
    location: str | None = None,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.fetch_jobs_for_profile(current_user.id, location=location)


@router.post(
    "/jobs/seed",
    response_model=JobSeedResponse,
    summary="Idempotently (re)seed the curated job catalog (admin)",
)
async def skill2job_jobs_seed(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("super_admin")),
):
    return await service.seed_local_jobs()


@router.post(
    "/jobs/match",
    response_model=list[JobMatchResponse],
    summary="Run the semantic job matching agent (Phase 5)",
)
async def skill2job_jobs_match_run(
    request: JobMatchRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.run_job_matching(current_user.id, request)


@router.get(
    "/jobs/match",
    response_model=list[JobMatchResponse],
    summary="Return the candidate's persisted job matches",
)
async def skill2job_jobs_match_get(
    limit: int = 20,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_job_matches(current_user.id, limit)


@router.post(
    "/skillgap/analyze",
    response_model=list[SkillGapAnalysis],
    summary="Analyze skill gaps with provenance + transfer-aware teaching plan (Phase 6)",
)
async def skill2job_skill_gap_analyze(
    request: SkillGapRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.analyze_skill_gaps(current_user.id, request)


@router.get(
    "/skillgap/analyze",
    response_model=list[SkillGapAnalysis],
    summary="Return stored skill-gap analyses",
)
async def skill2job_skill_gap_get(
    job_id: str | None = None,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_skill_gaps(current_user.id, job_id)


@router.get(
    "/skillgap/summary",
    response_model=SkillGapSummary,
    summary="Aggregated gap skills + teacher-style learning plan",
)
async def skill2job_skill_gap_summary(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_skill_gap_summary(current_user.id)


@router.post(
    "/opportunity/simulate",
    response_model=SimulationResult,
    summary="Run the what-if opportunity simulation (Phase 7)",
)
async def skill2job_opportunity_simulate(
    request: SimulationRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.run_simulation(current_user.id, request)


@router.get(
    "/opportunity/simulations",
    response_model=dict,
    summary="Simulation history for the candidate",
)
async def skill2job_opportunity_simulations(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_simulations(current_user.id)


@router.get(
    "/opportunity/dashboard",
    response_model=OpportunityDashboard,
    summary="Opportunity unlock dashboard (potential, unlocked, top roles)",
)
async def skill2job_opportunity_dashboard(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_opportunity_dashboard(current_user.id)


@router.get(
    "/training/plan",
    response_model=TrainingPlan,
    summary="Training agent learning plan (grounded resources) (Phase 8)",
)
async def skill2job_training_plan(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_training_plan(current_user.id)


@router.post(
    "/training/progress",
    response_model=dict,
    summary="Mark a training module complete (candidate-confirmed)",
)
async def skill2job_training_progress(
    request: ModuleProgressRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.complete_training_module(
        current_user.id, request.module_key, request.status
    )


@router.get(
    "/training/progress",
    response_model=dict,
    summary="Training progress history",
)
async def skill2job_training_progress_get(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_training_progress(current_user.id)


@router.post(
    "/training/run",
    response_model=dict,
    summary="Run the LangGraph orchestrated pipeline (perception → training)",
)
async def skill2job_training_run(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("super_admin", "admin", "candidate")),
):
    return await service.run_pipeline(current_user.id)


@router.get(
    "/training/traces",
    response_model=dict,
    summary="Recent LangGraph pipeline traces",
)
async def skill2job_training_traces(
    limit: int = 10,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("super_admin", "admin", "candidate")),
):
    user_role_names = {ur.role.name for ur in current_user.roles}
    is_admin = bool(user_role_names.intersection({"super_admin", "admin"}))
    return await service.list_pipeline_traces(current_user.id, limit=limit, is_admin=is_admin)


@router.get(
    "/training/traces/{run_id}",
    response_model=dict | None,
    summary="Fetch a specific LangGraph pipeline trace",
)
async def skill2job_training_trace(
    run_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("super_admin", "admin", "candidate")),
):
    user_role_names = {ur.role.name for ur in current_user.roles}
    is_admin = bool(user_role_names.intersection({"super_admin", "admin"}))
    return await service.get_pipeline_trace(current_user.id, run_id, is_admin=is_admin)

# --- Phase 9: Time-to-Ready Endpoints ---


@router.post(
    "/time-to-ready/calculate",
    response_model=dict,
    summary="Calculate time-to-ready for a target job",
)
async def skill2job_time_to_ready(
    request: TimeToReadyRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.calculate_time_to_ready(current_user.id, request)
    return result.model_dump(mode="json")


@router.post(
    "/time-to-ready/simulate",
    response_model=dict,
    summary="What-if learning simulator",
)
async def skill2job_what_if_simulate(
    request: WhatIfRequest,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.simulate_what_if(current_user.id, request)
    return result.model_dump(mode="json")


@router.get(
    "/time-to-ready/compare",
    response_model=list,
    summary="Compare time-to-ready across target jobs",
)
async def skill2job_compare_jobs(
    hours_per_week: float = 10.0,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    results = await service.compare_target_jobs(current_user.id, hours_per_week)
    return [r.model_dump(mode="json") for r in results]


@router.get(
    "/skill-graph",
    response_model=dict,
    summary="Aggregated candidate skill graph (reused SkillGraph + profile/gap data)",
)
async def skill2job_skill_graph(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_skill_graph(current_user.id)


@router.get(
    "/skill-proof",
    response_model=dict,
    summary="Aggregated skill evidence / proof from existing profile, perception and match data",
)
async def skill2job_skill_proof(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_skill_proof(current_user.id)


@router.get(
    "/skill-proof/{skill_id}",
    response_model=dict,
    summary="Detailed skill proof for a specific skill (LEARN/PROVE/VERIFIED status + plan)",
)
async def skill2job_skill_proof_detail(
    skill_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    detail = await service.get_skill_proof_detail(current_user.id, skill_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Skill not found in your profile or gaps")
    return detail


# --- Phase 3: Evidence-Aware Readiness ---


@router.get(
    "/readiness/{job_id}",
    response_model=dict,
    summary="Evidence-aware readiness calculation for a specific job",
)
async def skill2job_readiness(
    job_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    from app.skill2job.readiness.engine import ReadinessEngine

    engine = ReadinessEngine(service._session)
    result = await engine.calculate(current_user.id, job_id)
    return result.model_dump(mode="json")


# --- Phase 3: Per-Job Learning Plan ---


@router.get(
    "/learning/plan/{job_id}",
    response_model=dict,
    summary="Personalized learning plan for a specific target job",
)
async def skill2job_learning_plan_for_job(
    job_id: str,
    hours_per_week: float = Query(default=10.0, ge=1, le=60),
    free_only: bool = Query(default=False),
    optimization_mode: Literal["fastest", "cheapest", "free_only", "balanced"] = Query(
        default="balanced"
    ),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.get_learning_plan_for_job(
        current_user.id,
        job_id,
        hours_per_week=hours_per_week,
        free_only=free_only,
        mode=optimization_mode,
    )
    return result


@router.post(
    "/learning/plan",
    response_model=dict,
    summary="Generate a custom learning plan with specific parameters",
)
async def skill2job_learning_plan_custom(
    job_id: str = Form(...),
    hours_per_week: float = Form(default=10.0),
    free_only: bool = Form(default=False),
    optimization_mode: str = Form(default="balanced"),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    result = await service.get_learning_plan_for_job(
        current_user.id,
        job_id,
        hours_per_week=hours_per_week,
        free_only=free_only,
        mode=optimization_mode,
    )
    return result


# --- Phase 3: Multi-Job Comparison ---


@router.get(
    "/jobs/compare",
    response_model=list,
    summary="Compare time-to-ready across multiple target jobs",
)
async def skill2job_jobs_compare(
    hours_per_week: float = Query(default=10.0, ge=1, le=60),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    results = await service.compare_target_jobs(current_user.id, hours_per_week)
    return [r.model_dump(mode="json") for r in results]


# --- Phase 3: Learning Progress State Update ---


@router.post(
    "/learning/progress",
    response_model=dict,
    summary="Update learning progress state (7-state progression)",
)
async def skill2job_learning_progress_update(
    module_key: str = Form(...),
    evidence_state: str = Form(...),
    learning_hours: float = Form(default=0.0),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.update_learning_progress(
        current_user.id,
        module_key=module_key,
        evidence_state=evidence_state,
        learning_hours=learning_hours,
    )


@router.get(
    "/overview",
    response_model=dict,
    summary="Aggregated Career Intelligence Dashboard data",
)
async def skill2job_overview(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_overview(current_user.id)


@router.get("/jobs/{job_id}", response_model=dict, summary="Curated job detail")
async def skill2job_job_detail(
    job_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    job = await service.get_local_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found in the curated catalog")
    return job


@router.get(
    "/jobs/{job_id}/match",
    response_model=JobMatchDetail,
    summary="Explainable per-job semantic match detail",
)
async def skill2job_job_match_detail(
    job_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    detail = await service.get_job_match_detail(current_user.id, job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job not found in the curated catalog")
    return detail


@router.get(
    "/jobs/{job_id}/gaps",
    response_model=SkillGapAnalysis,
    summary="Per-job skill-gap analysis (skill gap vs evidence gap)",
)
async def skill2job_job_gap_detail(
    job_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    gap = await service.get_job_gap_detail(current_user.id, job_id)
    if gap is None:
        raise HTTPException(status_code=404, detail="Job not found in the curated catalog")
    return gap


@router.get(
    "/jobs/{job_id}/graph",
    response_model=dict,
    summary="Job-centric skill graph (job skills + match state + SkillGraph relations)",
)
async def skill2job_job_skill_graph(
    job_id: str,
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    graph = await service.get_job_skill_graph(current_user.id, job_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Job not found in the curated catalog")
    return graph


@router.get(
    "/skills/demand",
    response_model=SkillDemandResponse,
    summary="Dataset-wide skill demand derived from the curated catalog",
)
async def skill2job_skill_demand(
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_skill_demand()


# --- Phase 9: Learning Resource Intelligence ---


@router.get(
    "/learning/resources",
    response_model=ResourceListResponse,
    summary="Curated learning resource catalog with verification metadata",
)
async def skill2job_learning_resources(
    skill_filter: str | None = Query(default=None, description="Filter by skill / provider / title"),
    free_only: bool = Query(default=False, description="Only free resources"),
    limit: int = Query(default=50, ge=1, le=100),
    optimization_mode: Literal["fastest", "cheapest", "free_only", "balanced"] = Query(
        default="balanced"
    ),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.list_learning_resources(
        skill_filter=skill_filter, free_only=free_only, limit=limit, mode=optimization_mode
    )


@router.get(
    "/learning/resources/{skill}",
    response_model=ResourceMappingResponse,
    summary="Deterministic skill-to-learning-resource mapping (exact / synonym / fallback)",
)
async def skill2job_learning_resources_for_skill(
    skill: str,
    free_only: bool = Query(default=False),
    optimization_mode: Literal["fastest", "cheapest", "free_only", "balanced"] = Query(
        default="balanced"
    ),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.learning_resources_for_skill(
        skill=skill, mode=optimization_mode, free_only=free_only
    )


# --- Phase 9: Opportunity Impact ---


@router.get(
    "/opportunity/impact",
    response_model=OpportunityImpactResponse,
    summary="Per-skill opportunity impact analysis (in-memory, never persisted)",
)
async def skill2job_opportunity_impact(
    limit: int = Query(default=10, ge=1, le=30),
    service: Skill2JobService = Depends(_get_service),
    current_user: User = Depends(require_role("candidate")),
):
    return await service.get_opportunity_impact(current_user.id, limit=limit)
