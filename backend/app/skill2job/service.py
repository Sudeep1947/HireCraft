import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.skill2job_models import Skill2JobPerception
from app.skill2job.adapters.candidate_adapter import CandidateAdapter
from app.skill2job.perception.image_ocr import OcrAdapter
from app.skill2job.perception.pipeline import PerceptionPipeline
from app.skill2job.perception.speech import SpeechTranscriber
from app.skill2job.profile.agent import ProfileAgent
from app.skill2job.profile.schemas import ReviewRequest, ReviewResult
from app.skill2job.jobs.agent import LocalJobAgent
from app.skill2job.jobs.schemas import (
    CuratedJobCounts,
    CuratedJobFilters,
    CuratedJobPage,
    SkillDemandResponse,
)
from app.skill2job.matching.agent import JobMatchingAgent
from app.skill2job.matching.schemas import (
    JobMatchDetail,
    JobMatchRequest,
    JobMatchResponse,
)
from app.skill2job.gap.agent import SkillGapAgent
from app.skill2job.gap.schemas import SkillGapAnalysis, SkillGapRequest, SkillGapSummary
from app.skill2job.opportunity.agent import OpportunityUnlockAgent
from app.skill2job.opportunity.schemas import (
    OpportunityDashboard,
    OpportunityImpactResponse,
    SimulationRequest,
    SimulationResult,
)
from app.skill2job.training.agent import TrainingAgent
from app.skill2job.training.time_to_ready import TimeToReadyEngine
from app.skill2job.training.schemas import (
    TimeToReadyRequest,
    TimeToReadyResult,
    WhatIfRequest,
    WhatIfResult,
    TargetJobComparison,
)
from app.skill2job.training.agent import TrainingAgent
from app.skill2job.training.orchestrator import PipelineOrchestrator
from app.skill2job.training.schemas import TrainingPlan
from app.skill2job.schemas import (
    CapabilityItem,
    PerceptionInputStatus,
    PerceptionStatusResponse,
    Skill2JobCapabilities,
    Skill2JobHealth,
    Skill2JobProfileResponse,
)

logger = get_logger(__name__)

CAPABILITY_DEFINITIONS: list[dict] = [
    # Available from Phase 1 — foundation only, no fabricated intelligence.
    {"key": "module_foundation", "label": "Skill2Job module foundation", "status": "available", "phase": 1},
    {"key": "authentication_rbac", "label": "Authentication & role-based access", "status": "available", "phase": 1},
    {"key": "candidate_profile", "label": "Existing candidate profile (reused)", "status": "available", "phase": 1},
    {"key": "candidate_intelligence", "label": "Existing candidate intelligence (reused)", "status": "available", "phase": 1},
    {"key": "skill_graph", "label": "Existing skill graph (reused)", "status": "available", "phase": 1},
    # Phase 2 — perception.
    {"key": "perception", "label": "Voice / resume / image / document perception", "status": "available", "phase": 2},
    {"key": "perception_document", "label": "Resume & document perception (provenance-annotated)", "status": "available", "phase": 2},
    {"key": "perception_free_text", "label": "Free-text perception", "status": "available", "phase": 2},
    {"key": "perception_voice", "label": "Voice perception (provider-aware)", "status": "available", "phase": 2},
    {"key": "perception_image", "label": "Image OCR perception (provider-aware)", "status": "available", "phase": 2},
    # Phase 3 — candidate profile agent.
    {"key": "profile_agent", "label": "Advanced candidate profile agent", "status": "available", "phase": 3},
    # Phase 4 — local job intelligence.
    {"key": "local_jobs", "label": "Local job intelligence & curated jobs", "status": "available", "phase": 4},
    {"key": "local_jobs_catalog", "label": "Curated local job catalog (40 roles)", "status": "available", "phase": 4},
    # Phase 5 — semantic job matching agent.
    {"key": "job_matching", "label": "Semantic job matching agent", "status": "available", "phase": 5},
    # Phase 6 — advanced skill gap agent.
    {"key": "skill_gap", "label": "Advanced skill gap & skill graph reasoning", "status": "available", "phase": 6},
    {"key": "skill_gap_teaching_plan", "label": "Teacher-style learning plan (transfer-aware)", "status": "available", "phase": 6},
    # Phase 7 — opportunity unlock.
    {"key": "opportunity_unlock", "label": "Opportunity unlock & what-if simulator", "status": "available", "phase": 7},
    {"key": "opportunity_simulator", "label": "What-if skill learning simulator (persisted)", "status": "available", "phase": 7},
    {"key": "opportunity_impact", "label": "Per-skill opportunity impact analysis (in-memory, never persisted)", "status": "available", "phase": 9},
    # Phase 8 — training agent + LangGraph orchestration.
    {"key": "training_agent", "label": "Training agent & LangGraph orchestration", "status": "available", "phase": 8},
    {"key": "training_learning_plan", "label": "Grounded learning plan (official resources)", "status": "available", "phase": 8},
    {"key": "training_progress", "label": "Training progress tracking", "status": "available", "phase": 8},
    {"key": "pipeline_orchestrator", "label": "LangGraph pipeline orchestration with trace recording", "status": "available", "phase": 8},
    # Enhancement: interests intake + learning resource sources.
    {"key": "interests_intake", "label": "Candidate interests intake (persisted, non-scoring reasons)", "status": "available", "phase": 8},
    {"key": "learning_resource_sources", "label": "Verified learning resource sources (NPTEL / Skill India)", "status": "available", "phase": 8},
    # Phase 9 — career optimization.
    {"key": "learning_resources", "label": "Learning resource intelligence (consolidated catalog + skill mapping)", "status": "available", "phase": 9},
    {"key": "resource_verification", "label": "Resource verification metadata (host-audited, never fabricated)", "status": "available", "phase": 9},
]


class Skill2JobService:
    """Skill2Job orchestration across phases.

    Phase 1 exposed only foundation operations. Later phases add dedicated
    agents; none of them fabricate intelligence or duplicate recruiter data.
    """

    def __init__(
        self,
        *,
        candidate_adapter: CandidateAdapter | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._candidate_adapter = candidate_adapter
        self._session = session

    def check_health(self) -> Skill2JobHealth:
        logger.info("Skill2Job module initialized")
        return Skill2JobHealth(module="skill2job", status="available")

    async def get_capabilities(self, user_id: uuid.UUID) -> Skill2JobCapabilities:
        logger.info("Skill2Job capabilities request received: user=%s", user_id)
        connected = await self._candidate_adapter.profile_exists(user_id)
        logger.info("Skill2Job profile linkage check: user=%s connected=%s", user_id, connected)
        capabilities = [CapabilityItem(**item) for item in CAPABILITY_DEFINITIONS]
        return Skill2JobCapabilities(
            module="skill2job",
            profile_connected=connected,
            capabilities=capabilities,
        )

    async def get_profile(self, user_id: uuid.UUID) -> Skill2JobProfileResponse:
        logger.info("Skill2Job profile request received: user=%s", user_id)
        profile = await self._candidate_adapter.get_profile(user_id)
        logger.info("Existing candidate profile loaded: user=%s", user_id)
        try:
            intelligence = await self._candidate_adapter.get_intelligence(user_id)
        except NotFoundError:
            intelligence = None
        return Skill2JobProfileResponse(connected=True, profile=profile, intelligence=intelligence)

    # ─── Interests (candidate profile intake) ────────────────────────────

    async def get_interests(self, user_id: uuid.UUID) -> list[str]:
        return await self._candidate_adapter.get_interests(user_id)

    async def set_interests(self, user_id: uuid.UUID, interests: list[str]) -> list[str]:
        return await self._candidate_adapter.update_interests(user_id, interests)

    # ─── Phase 2: Perception ─────────────────────────────────────────────

    async def get_perception_status(self) -> PerceptionStatusResponse:
        speech_providers = SpeechTranscriber.available_providers()
        ocr_providers = OcrAdapter.available_providers()
        return PerceptionStatusResponse(
            document=PerceptionInputStatus(
                input_type="document", configured=True, providers=["resume_intelligence_engine"]
            ),
            free_text=PerceptionInputStatus(
                input_type="free_text", configured=True, providers=["resume_intelligence_engine"]
            ),
            voice=PerceptionInputStatus(
                input_type="voice", configured=bool(speech_providers), providers=speech_providers
            ),
            image=PerceptionInputStatus(
                input_type="image", configured=bool(ocr_providers), providers=ocr_providers
            ),
        )

    async def perceive_upload(self, user_id: uuid.UUID, filename: str, content: bytes) -> dict:
        pipeline = PerceptionPipeline(self._session)
        record = await pipeline.perceive_upload(user_id, filename, content)
        return {"perception_id": str(record.id), "result": record.result}

    async def perceive_text(self, user_id: uuid.UUID, text: str) -> dict:
        pipeline = PerceptionPipeline(self._session)
        record = await pipeline.perceive_text(user_id, text)
        return {"perception_id": str(record.id), "result": record.result}

    async def list_perceptions(self, user_id: uuid.UUID) -> dict:
        from sqlalchemy import select

        result = await self._session.execute(
            select(Skill2JobPerception)
            .where(Skill2JobPerception.user_id == user_id)
            .order_by(Skill2JobPerception.created_at.desc())
        )
        rows = result.scalars().all()
        items = []
        for r in rows:
            res = r.result or {}
            items.append({
                "id": str(r.id),
                "input_type": r.input_type,
                "original_filename": r.original_filename,
                "processing_status": r.processing_status,
                "processing_message": r.processing_message,
                "field_confidence": res.get("field_confidence"),
                "skills_count": len(res.get("skills", [])),
                "experience_count": len(res.get("experience", [])),
                "education_count": len(res.get("education", [])),
                "projects_count": len(res.get("projects", [])),
                "certifications_count": len(res.get("certifications", [])),
                "languages_count": len(res.get("languages", [])),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return {"items": items, "total": len(items)}

    async def get_perception_detail(self, user_id: uuid.UUID, perception_id: str) -> dict | None:
        from sqlalchemy import select

        try:
            pid = uuid.UUID(perception_id)
        except ValueError:
            return None

        record = (
            await self._session.execute(
                select(Skill2JobPerception).where(
                    Skill2JobPerception.id == pid,
                    Skill2JobPerception.user_id == user_id,
                )
            )
        ).scalars().first()

        if record is None:
            return None

        res = record.result or {}
        return {
            "id": str(record.id),
            "input_type": record.input_type,
            "original_filename": record.original_filename,
            "processing_status": record.processing_status,
            "processing_message": record.processing_message,
            "field_confidence": res.get("field_confidence"),
            "extracted_text": record.extracted_text,
            "result": res,
            "warnings": record.warnings or [],
            "parser_version": record.parser_version,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    async def delete_perception(self, user_id: uuid.UUID, perception_id: str) -> bool:
        from sqlalchemy import select

        try:
            pid = uuid.UUID(perception_id)
        except ValueError:
            return False

        record = (
            await self._session.execute(
                select(Skill2JobPerception).where(
                    Skill2JobPerception.id == pid,
                    Skill2JobPerception.user_id == user_id,
                )
            )
        ).scalars().first()

        if record is None:
            return False

        await self._session.delete(record)
        await self._session.flush()
        return True

    # ─── Phase 3: Candidate Profile Agent ────────────────────────────────

    def _profile_agent(self) -> ProfileAgent:
        return ProfileAgent(self._session, self._candidate_adapter)

    async def build_profile_dossier(self, user_id: uuid.UUID) -> dict:
        dossier = await self._profile_agent().build_dossier(user_id)
        return dossier.model_dump(mode="json")

    async def get_profile_dossier(self, user_id: uuid.UUID) -> dict | None:
        return await self._profile_agent().get_dossier(user_id)

    async def apply_profile_review(
        self, user_id: uuid.UUID, request: ReviewRequest
    ) -> ReviewResult:
        return await self._profile_agent().apply_review(user_id, request)

    # ─── Phase 4: Local Job Intelligence ─────────────────────────────────

    def _local_job_agent(self) -> LocalJobAgent:
        return LocalJobAgent(self._session)

    async def list_local_jobs(
        self, filters: CuratedJobFilters
    ) -> CuratedJobPage:
        return await self._local_job_agent().list_jobs(filters)

    async def get_local_job_counts(
        self, user_id: uuid.UUID | None = None
    ) -> CuratedJobCounts:
        return await self._local_job_agent().job_counts()

    async def get_local_job(self, job_id: str) -> dict | None:
        """Single curated job detail, or None when not found."""
        return await self._local_job_agent().get_job(job_id)

    async def get_skill_demand(self) -> SkillDemandResponse:
        """Dataset-wide skill demand derived from the curated catalog."""
        return await self._local_job_agent().skill_demand()

    async def seed_local_jobs(self) -> dict:
        return await self._local_job_agent().ensure_catalog()

    async def fetch_jobs_for_profile(
        self, user_id: uuid.UUID, location: str | None = None
    ) -> list[dict]:
        profile = None
        try:
            profile = await self._candidate_adapter.get_profile(user_id)
        except NotFoundError:
            profile = None
        return await self._local_job_agent().fetch_jobs(profile, location=location)

    # ─── Phase 5: Job Matching Agent ─────────────────────────────────────

    def _matching_agent(self) -> JobMatchingAgent:
        return JobMatchingAgent(self._session)

    async def run_job_matching(
        self, user_id: uuid.UUID, request: JobMatchRequest
    ) -> list[JobMatchResponse]:
        entries = await self._matching_agent().run_match(
            user_id,
            job_ids=request.job_ids,
            location=request.location,
            limit=request.limit or 10,
        )
        return [
            JobMatchResponse(
                job_id=e.job_id,
                title=e.title,
                company=e.company,
                location=e.location,
                remote_type=e.remote_type,
                overall_score=e.overall_score,
                recommendation=e.recommendation,
                strength_level=e.strength_level,
                matched_skills=e.matched_skills,
                missing_required=e.missing_required,
                suggested_skills=e.suggested_skills,
                reasons=e.reasons,
            )
            for e in entries
        ]

    async def get_job_matches(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> list[JobMatchResponse]:
        results = await self._matching_agent().get_results(user_id, limit)
        return [JobMatchResponse(**r) for r in results]

    async def get_job_match_detail(
        self, user_id: uuid.UUID, job_id: str
    ) -> JobMatchDetail | None:
        """Explainable per-job match detail (categories, per-skill evidence)."""
        return await self._matching_agent().get_match_detail(user_id, job_id)

    # ─── Phase 6: Skill Gap Agent ────────────────────────────────────────

    def _gap_agent(self) -> SkillGapAgent:
        return SkillGapAgent(self._session)

    async def analyze_skill_gaps(
        self, user_id: uuid.UUID, request: SkillGapRequest
    ) -> list[SkillGapAnalysis]:
        return await self._gap_agent().analyze_profile(
            user_id, job_ids=request.job_ids, limit=request.limit
        )

    async def get_skill_gaps(
        self, user_id: uuid.UUID, job_id: str | None = None
    ) -> list[SkillGapAnalysis]:
        return await self._gap_agent().get_analysis(user_id, job_id)

    async def get_skill_gap_summary(self, user_id: uuid.UUID) -> SkillGapSummary:
        return await self._gap_agent().get_summary(user_id)

    async def get_job_gap_detail(
        self, user_id: uuid.UUID, job_id: str
    ) -> SkillGapAnalysis | None:
        """Per-job gap analysis with skill-gap vs evidence-gap classification."""
        return await self._gap_agent().get_gap_detail(user_id, job_id)

    # ─── Phase 7: Opportunity Unlock ─────────────────────────────────────

    def _opportunity_agent(self) -> OpportunityUnlockAgent:
        return OpportunityUnlockAgent(self._session)

    async def run_simulation(
        self, user_id: uuid.UUID, request: SimulationRequest
    ) -> SimulationResult:
        return await self._opportunity_agent().simulate(user_id, request)

    async def list_simulations(self, user_id: uuid.UUID) -> dict:
        return await self._opportunity_agent().get_results(user_id)

    async def get_opportunity_dashboard(
        self, user_id: uuid.UUID
    ) -> OpportunityDashboard:
        return await self._opportunity_agent().dashboard(user_id)

    async def get_opportunity_impact(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> OpportunityImpactResponse:
        return await self._opportunity_agent().impact(user_id, limit)

    # ─── Phase 8: Training Agent + LangGraph ──────────────────────────────

    def _training_agent(self) -> TrainingAgent:
        return TrainingAgent(self._session)

    async def get_training_plan(self, user_id: uuid.UUID) -> TrainingPlan:
        return await self._training_agent().plan_training(user_id)

    async def complete_training_module(
        self, user_id: uuid.UUID, module_key: str, status: str = "completed"
    ) -> dict:
        return await self._training_agent().complete_module(user_id, module_key, status)

    async def get_training_progress(self, user_id: uuid.UUID) -> dict:
        return await self._training_agent().get_progress(user_id)

    async def run_pipeline(self, user_id: uuid.UUID) -> dict:
        return await PipelineOrchestrator(self._session).run(user_id)

    async def get_pipeline_trace(
        self, user_id: uuid.UUID, run_id: str, is_admin: bool = False
    ) -> dict | None:
        return await PipelineOrchestrator(self._session).get_trace(user_id, run_id, is_admin=is_admin)


    # --- Phase 9: Time-to-Ready Engine ---

    def _time_to_ready_engine(self) -> TimeToReadyEngine:
        return TimeToReadyEngine(self._session)

    async def calculate_time_to_ready(
        self, user_id: uuid.UUID, request: TimeToReadyRequest
    ) -> TimeToReadyResult:
        return await self._time_to_ready_engine().calculate(user_id, request)

    async def simulate_what_if(
        self, user_id: uuid.UUID, request: WhatIfRequest
    ) -> WhatIfResult:
        return await self._time_to_ready_engine().simulate(user_id, request)

    async def compare_target_jobs(
        self, user_id: uuid.UUID, hours_per_week: float = 10.0
    ) -> list:
        return await self._time_to_ready_engine().compare_jobs(user_id, hours_per_week)

    async def list_pipeline_traces(self, user_id: uuid.UUID, limit: int = 10, is_admin: bool = False) -> dict:
        return await PipelineOrchestrator(self._session).list_traces(user_id, limit, is_admin=is_admin)

    # --- Phase 9: Learning Resource Intelligence ---

    def _learning_resource_agent(self) -> "LearningResourceAgent":
        from app.skill2job.learning.agent import LearningResourceAgent

        return LearningResourceAgent(self._session)

    async def list_learning_resources(
        self,
        skill_filter: str | None = None,
        free_only: bool = False,
        limit: int = 50,
        mode: str = "balanced",
    ) -> "ResourceListResponse":
        from app.skill2job.learning.schemas import ResourceListResponse

        return self._learning_resource_agent().list_resources(
            skill_filter=skill_filter, free_only=free_only, limit=limit, mode=mode
        )

    async def learning_resources_for_skill(
        self,
        skill: str,
        mode: str = "balanced",
        free_only: bool = False,
        limit: int = 5,
    ) -> "ResourceMappingResponse":
        from app.skill2job.learning.schemas import ResourceMappingResponse

        return self._learning_resource_agent().resources_for_skill(
            skill=skill, mode=mode, free_only=free_only, limit=limit
        )

    # --- Phase 3: Per-Job Learning Plan ---

    async def get_learning_plan_for_job(
        self,
        user_id: uuid.UUID,
        job_id: str,
        hours_per_week: float = 10.0,
        free_only: bool = False,
        mode: str = "balanced",
    ) -> dict:
        """Generate a personalized learning plan for a specific target job."""
        from app.skill2job.readiness.engine import ReadinessEngine
        from app.skill2job.training.schemas import TimeToReadyRequest

        ttr_engine = self._time_to_ready_engine()
        readiness_engine = ReadinessEngine(self._session)

        job = await ttr_engine._find_job(job_id, "")
        if job is None:
            return {"error": "Job not found", "job_id": job_id}

        readiness = await readiness_engine.calculate(user_id, job_id)

        request = TimeToReadyRequest(
            job_id=job_id,
            hours_per_week=hours_per_week,
            free_only=free_only,
            optimization_mode=mode,
        )
        ttr_result = await ttr_engine.calculate(user_id, request)

        return {
            "job_id": job_id,
            "job_title": job.title,
            "current_readiness": readiness.overall_readiness,
            "skill_coverage": readiness.skill_coverage,
            "evidence_quality": readiness.evidence_quality,
            "critical_gaps": readiness.critical_gaps,
            "missing_skills": [
                {
                    "skill": s.skill,
                    "priority": s.priority,
                    "importance": s.importance,
                    "dependencies": s.dependencies,
                    "has_free_resource": s.has_free_resource,
                }
                for s in (ttr_result.missing_skills or [])
            ],
            "learning_plan": [
                {
                    "step_number": s.step_number,
                    "skill": s.skill,
                    "resource_title": s.resource.title,
                    "resource_provider": s.resource.provider,
                    "resource_url": s.resource.url,
                    "weeks": s.weeks,
                    "hours": s.hours,
                    "cost": s.cost,
                    "is_free": s.is_free,
                    "can_parallel": s.can_parallel,
                    "explanation": s.explanation,
                }
                for s in (ttr_result.learning_plan or [])
            ],
            "total_weeks": ttr_result.estimated_weeks,
            "total_hours": ttr_result.estimated_hours,
            "total_cost": ttr_result.estimated_cost,
            "currency": ttr_result.currency,
            "free_only_path": {
                "weeks": ttr_result.free_only.estimated_weeks if ttr_result.free_only else 0,
                "hours": ttr_result.free_only.estimated_hours if ttr_result.free_only else 0,
                "cost": ttr_result.free_only.estimated_cost if ttr_result.free_only else 0,
                "coverage_pct": ttr_result.free_only.coverage_pct if ttr_result.free_only else 0,
                "remaining_gaps": ttr_result.free_only.remaining_gaps if ttr_result.free_only else [],
            },
            "opportunity_unlock": {
                "current_jobs": ttr_result.opportunity_unlock.current_jobs if ttr_result.opportunity_unlock else 0,
                "projected_jobs": ttr_result.opportunity_unlock.projected_jobs if ttr_result.opportunity_unlock else 0,
                "potential_increase": ttr_result.opportunity_unlock.potential_increase if ttr_result.opportunity_unlock else 0,
            },
            "optimization_mode": mode,
            "hours_per_week": hours_per_week,
            "version": ttr_result.version,
        }

    # --- Phase 3: Learning Progress State Update ---

    VALID_EVIDENCE_STATES = {
        "not_started", "in_progress", "completed",
        "practiced", "assessed", "demonstrated", "verified",
    }

    async def update_learning_progress(
        self,
        user_id: uuid.UUID,
        module_key: str,
        evidence_state: str,
        learning_hours: float = 0.0,
    ) -> dict:
        """Update learning progress with a specific evidence state."""
        from sqlalchemy import select
        from app.domain.skill2job_models import Skill2JobTrainingProgress
        from datetime import datetime, timezone

        if evidence_state not in self.VALID_EVIDENCE_STATES:
            return {
                "ok": False,
                "reason": f"Invalid evidence_state: {evidence_state}. "
                f"Must be one of: {', '.join(sorted(self.VALID_EVIDENCE_STATES))}",
            }

        existing = (
            await self._session.execute(
                select(Skill2JobTrainingProgress).where(
                    Skill2JobTrainingProgress.user_id == user_id,
                    Skill2JobTrainingProgress.module_key == module_key,
                )
            )
        ).scalars().first()

        if existing is None:
            # Try to find module details from the training plan and create a record
            plan = await self._training_agent().plan_training(user_id, limit=50)
            module = next((m for m in plan.modules if m.module_key == module_key), None)
            if module is None:
                return {"ok": False, "reason": "Module not found", "module_key": module_key}
            existing = Skill2JobTrainingProgress(
                user_id=user_id,
                module_key=module.module_key,
                skill=module.skill,
                title=module.title,
                provider=module.provider,
                url=module.url,
                resource_type=module.resource_type,
                status=evidence_state if evidence_state != "not_started" else "in_progress",
                evidence_state=evidence_state,
                learning_hours=learning_hours,
                completed_at=datetime.now(timezone.utc) if evidence_state == "completed" else None,
            )
            self._session.add(existing)
            await self._session.flush()
            return {
                "ok": True,
                "module_key": module_key,
                "evidence_state": evidence_state,
                "learning_hours": learning_hours,
            }

        existing.evidence_state = evidence_state
        if learning_hours > 0:
            existing.learning_hours = (existing.learning_hours or 0) + learning_hours
        if evidence_state == "completed" and not existing.completed_at:
            existing.completed_at = datetime.now(timezone.utc)
        if evidence_state != "in_progress":
            existing.status = evidence_state

        await self._session.flush()
        return {
            "ok": True,
            "module_key": module_key,
            "evidence_state": evidence_state,
            "learning_hours": existing.learning_hours,
        }

    # --- Skill Graph & Skill Proof aggregation (reused existing engines) ---

    async def _collect_skill_names(self, user_id: uuid.UUID) -> list[str]:
        """Reuse the existing candidate intelligence skill summary (no duplication)."""
        skill_names: list[str] = []
        try:
            profile_data = await self.get_profile(user_id)
            intelligence = getattr(profile_data, "intelligence", None)
            summary = getattr(intelligence, "skill_summary", None) if intelligence else None
            if summary:
                for item in summary:
                    name = getattr(item, "name", None)
                    if isinstance(item, dict):
                        name = item.get("name")
                    if name:
                        skill_names.append(str(name))
            elif intelligence and getattr(intelligence, "skills_by_category", None):
                for names in intelligence.skills_by_category.values():
                    skill_names.extend(names or [])
        except Exception:
            skill_names = []
        seen: set = set()
        out: list[str] = []
        for name in skill_names:
            key = str(name).strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(str(name).strip())
        return out

    async def get_skill_graph(self, user_id: uuid.UUID) -> dict:
        """Aggregate a deterministic skill graph for the candidate.

        Nodes and edges are derived only from the existing SkillGraph, the
        candidate's real profile skills, and persisted gap skills. Nothing is
        invented and nothing new is stored.
        """
        from app.services.screening.skill_graph import SkillGraph

        skills = await self._collect_skill_names(user_id)

        gap_rows: list[dict] = []
        try:
            summary = await self.get_skill_gap_summary(user_id)
            raw = summary.model_dump() if hasattr(summary, "model_dump") else dict(summary)
            gap_rows = raw.get("gap_skills", []) or []
        except Exception:
            gap_rows = []

        nodes: list[dict] = []
        edges: list[dict] = []
        node_index: dict[str, int] = {}

        def add_node(node_id: str, label: str, kind: str, category: str | None = None, count: int = 0) -> int:
            existing = node_index.get(node_id)
            if existing is not None:
                return existing
            idx = len(nodes)
            nodes.append(
                {
                    "id": node_id,
                    "label": label,
                    "kind": kind,
                    "category": category,
                    "count": count,
                }
            )
            node_index[node_id] = idx
            return idx

        candidate_ids: set = set()
        for name in skills:
            idx = add_node(name.lower(), name, "candidate")
            candidate_ids.add(name.lower())
            canonical = SkillGraph.find_canonical(name)
            if canonical and canonical.lower() != name.lower():
                c_idx = add_node(canonical.lower(), canonical, "candidate")
                edges.append({"source": idx, "target": c_idx, "relation": "synonym"})
            for related in SkillGraph.get_related_skills(name):
                r_idx = add_node(related.lower(), related, "related")
                edges.append({"source": idx, "target": r_idx, "relation": "related"})

        for gap in gap_rows:
            gname = str(gap.get("skill", "")).strip()
            if not gname:
                continue
            g_idx = add_node(gname.lower(), gname, "gap", count=int(gap.get("count", 0) or 0))
            for related in SkillGraph.get_related_skills(gname):
                r_idx = add_node(related.lower(), related, "related")
                edges.append({"source": g_idx, "target": r_idx, "relation": "related"})
            for name in skills:
                if SkillGraph.is_transferable(gname, name) or SkillGraph.are_synonyms(gname, name):
                    c_idx = node_index.get(name.lower())
                    if c_idx is not None:
                        edges.append({"source": g_idx, "target": c_idx, "relation": "transferable"})

        return {
            "nodes": nodes,
            "edges": edges,
            "generated_from": {
                "candidate_skills": len(skills),
                "gap_skills": len(gap_rows),
            },
        }

    async def get_job_skill_graph(self, user_id: uuid.UUID, job_id: str) -> dict | None:
        """Job-centric skill graph.

        Nodes and edges come only from the persisted job (required/preferred
        skills), the candidate's real matched/missing state for that job, and the
        existing SkillGraph relations. Returns None when the job is unknown.
        """
        from app.services.screening.skill_graph import SkillGraph

        job = await self.get_local_job(job_id)
        if job is None:
            return None

        entry = None
        try:
            results = await self._matching_agent().run_match(
                user_id, job_ids=[job_id], limit=1
            )
            entry = results[0] if results else None
        except Exception:
            entry = None

        matched = {str(s).strip().lower() for s in (entry.matched_skills if entry else [])}
        missing = {
            str(s).strip().lower() for s in (entry.missing_required if entry else [])
        }
        candidate_skills = {s.strip().lower() for s in await self._collect_skill_names(user_id)}

        nodes: list[dict] = []
        edges: list[dict] = []
        node_index: dict[str, int] = {}

        def add_node(node_id: str, label: str, kind: str) -> int:
            existing = node_index.get(node_id)
            if existing is not None:
                return existing
            idx = len(nodes)
            nodes.append({"id": node_id, "label": label, "kind": kind})
            node_index[node_id] = idx
            return idx

        job_idx = add_node("job", job["title"], "job")
        for skill in list(job["required_skills"] or []) + list(job["preferred_skills"] or []):
            key = str(skill).strip().lower()
            if key in matched:
                kind = "matched"
            elif key in missing:
                kind = "gap"
            else:
                kind = "required"
            if skill in (job["preferred_skills"] or []) and kind == "required":
                kind = "preferred"
            idx = add_node(key, skill, kind)
            relation = "prefers" if kind == "preferred" else "requires"
            edges.append({"source": job_idx, "target": idx, "relation": relation})
            for related in SkillGraph.get_related_skills(skill):
                r_idx = add_node(related.lower(), related, "related")
                edges.append({"source": idx, "target": r_idx, "relation": "related"})

        for gap_skill in missing:
            g_idx = node_index.get(gap_skill)
            if g_idx is None:
                continue
            for name in candidate_skills:
                if SkillGraph.is_transferable(gap_skill, name) or SkillGraph.are_synonyms(
                    gap_skill, name
                ):
                    c_idx = add_node(name, name, "candidate")
                    edges.append({"source": g_idx, "target": c_idx, "relation": "transferable"})

        return {
            "job": job,
            "nodes": nodes,
            "edges": edges,
            "match": {
                "overall_score": entry.overall_score if entry else None,
                "matched_skills": list(entry.matched_skills) if entry else [],
                "missing_required": list(entry.missing_required) if entry else [],
            },
            "generated_from": {"job_skills": len(job["required_skills"]) + len(job["preferred_skills"])},
        }

    async def get_skill_proof(self, user_id: uuid.UUID) -> dict:
        """Aggregate evidence for each of the candidate's real skills.

        Evidence comes only from existing data: the candidate profile skill
        record, perceived skills from resume/text/or voice, matched-job skill
        demand, and persisted skill-gap demand.

        Phase 3 enhancement: each skill now includes a ``proof_status`` field
        that classifies it as ``LEARN`` (skill gap — needs to be learned) or
        ``PROVE`` (skill claimed but lacks strong evidence).
        """
        skill_names = await self._collect_skill_names(user_id)

        perceived: dict[str, int] = {}
        try:
            from sqlalchemy import select
            from app.domain.skill2job_models import Skill2JobPerception

            rows = (
                await self._session.execute(
                    select(Skill2JobPerception.result).where(Skill2JobPerception.user_id == user_id)
                )
            ).scalars().all()
            for res in rows:
                for item in res.get("skills", []) if isinstance(res, dict) else (res or {}).get("skills", []):
                    name = item.get("name") if isinstance(item, dict) else None
                    if name:
                        key = str(name).strip().lower()
                        perceived[key] = perceived.get(key, 0) + 1
        except Exception:
            perceived = {}

        matched_skills: set = set()
        try:
            matches = await self.get_job_matches(user_id, 50)
            for m in matches:
                for s in (getattr(m, "matched_skills", None) or []):
                    matched_skills.add(str(s).strip().lower())
        except Exception:
            matched_skills = set()

        gap_demand: dict[str, dict] = {}
        try:
            summary = await self.get_skill_gap_summary(user_id)
            raw = summary.model_dump() if hasattr(summary, "model_dump") else dict(summary)
            for g in raw.get("gap_skills", []) or []:
                key = str(g.get("skill", "")).strip().lower()
                if key:
                    gap_demand[key] = {
                        "count": int(g.get("count", 0) or 0),
                        "jobs": list(g.get("jobs_demanding", []) or []),
                    }
        except Exception:
            gap_demand = {}

        # Collect training progress for evidence classification
        training_completed: set = set()
        try:
            from sqlalchemy import select
            from app.domain.skill2job_models import Skill2JobTrainingProgress

            progress_rows = (
                await self._session.execute(
                    select(Skill2JobTrainingProgress.skill).where(
                        Skill2JobTrainingProgress.user_id == user_id,
                        Skill2JobTrainingProgress.status == "completed",
                    )
                )
            ).scalars().all()
            for s in progress_rows:
                training_completed.add(str(s).strip().lower())
        except Exception:
            training_completed = set()

        # Collect gap skills (skills the candidate is missing)
        gap_skill_names: set = set()
        for key in gap_demand:
            gap_skill_names.add(key)

        skills: list[dict] = []
        for name in skill_names:
            key = name.strip().lower()
            evidence: list[dict] = []
            supported_by: list[str] = []
            entry_profile = None
            try:
                intelligence = getattr(await self.get_profile(user_id), "intelligence", None)
                summary_items = getattr(intelligence, "skill_summary", None) if intelligence else None
                for item in summary_items or []:
                    if str(getattr(item, "name", item.get("name") if isinstance(item, dict) else "")).strip().lower() == key:
                        entry_profile = item
                        break
            except Exception:
                entry_profile = None

            category = getattr(entry_profile, "category", None)
            proficiency = getattr(entry_profile, "proficiency", None)
            years = getattr(entry_profile, "years", None)
            if isinstance(entry_profile, dict):
                category = entry_profile.get("category")
                proficiency = entry_profile.get("proficiency")
                years = entry_profile.get("years")

            if proficiency or years is not None:
                evidence.append(
                    {
                        "source": "profile",
                        "note": f"Profile skill record (proficiency: {proficiency or 'n/a'}, years: {years if years is not None else 0})",
                    }
                )
                supported_by.append("profile")
            if key in perceived:
                evidence.append(
                    {
                        "source": "perception",
                        "note": f"Extracted from your resume/document/text perceptions ({perceived[key]} record(s))",
                    }
                )
                supported_by.append("perception")
            if key in matched_skills:
                evidence.append({"source": "matched_jobs", "note": "Matched against local job requirements"})
                supported_by.append("matched_jobs")
            if key in gap_demand:
                demand = gap_demand[key]
                evidence.append(
                    {"source": "gap_demand", "note": f"Connected to {demand['count']} job(s) as a learning target"}
                )
                supported_by.append("gap_demand")
            if key in training_completed:
                evidence.append(
                    {"source": "training", "note": "Training module completed for this skill"}
                )
                supported_by.append("training")

            # Phase 3: Classify proof_status as LEARN or PROVE
            # LEARN = skill is missing entirely (gap skill, not in candidate's vocabulary)
            # PROVE = skill is claimed but evidence is weak (only profile claim, no perception/match/training)
            proof_status = self._classify_proof_status(
                key, supported_by, proficiency, years
            )

            # Phase 3: Generate skill proof plan
            proof_plan = self._generate_skill_proof_plan(
                name, proof_status, supported_by, gap_demand.get(key)
            )

            skills.append(
                {
                    "name": name,
                    "category": category,
                    "proficiency": proficiency,
                    "years": years,
                    "evidence": evidence,
                    "supported_by": supported_by,
                    "proof_status": proof_status,
                    "proof_plan": proof_plan,
                }
            )

        # Also add gap skills that the candidate doesn't have yet
        all_candidate_keys = {s["name"].lower().strip() for s in skills}
        for gap_key in gap_skill_names:
            if gap_key not in all_candidate_keys:
                demand = gap_demand.get(gap_key, {})
                skills.append(
                    {
                        "name": gap_key,
                        "category": None,
                        "proficiency": None,
                        "years": None,
                        "evidence": [],
                        "supported_by": [],
                        "proof_status": "LEARN",
                        "proof_plan": self._generate_skill_proof_plan(
                            gap_key, "LEARN", [], demand
                        ),
                    }
                )

        return {
            "skills": skills,
            "sources": {
                "profile": len([s for s in skills if "profile" in s["supported_by"]]),
                "perception": len(perceived),
                "matched_jobs": len(matched_skills),
                "gap_demand": len(gap_demand),
                "training": len(training_completed),
            },
        }

    def _classify_proof_status(
        self,
        skill_key: str,
        supported_by: list[str],
        proficiency: str | None,
        years: int | float | None,
    ) -> str:
        """Classify whether a skill needs LEARN or PROVE.

        LEARN: skill is entirely missing — candidate doesn't have it.
        PROVE: candidate claims the skill but evidence is weak.
        """
        # Strong evidence sources that indicate the skill is real
        strong_sources = {"perception", "matched_jobs", "training"}

        has_strong_evidence = bool(strong_sources & set(supported_by))

        if has_strong_evidence:
            return "VERIFIED"

        if proficiency or (years is not None and years > 0):
            # Has profile data but no external verification
            return "PROVE"

        if "profile" in supported_by and len(supported_by) == 1:
            # Only profile claim — weak evidence
            return "PROVE"

        return "PROVE"

    def _generate_skill_proof_plan(
        self,
        skill_name: str,
        proof_status: str,
        supported_by: list[str],
        gap_demand: dict | None,
    ) -> dict:
        """Generate a skill proof plan for a given skill.

        For LEARN skills: full learning → practice → challenge → assessment → evidence path.
        For PROVE skills: practice → challenge → assessment → evidence path.
        For VERIFIED skills: maintenance/keep-current path.
        """
        if proof_status == "LEARN":
            return {
                "action": "LEARN",
                "steps": [
                    {"step": 1, "phase": "learn", "description": f"Learn {skill_name} fundamentals"},
                    {"step": 2, "phase": "practice", "description": f"Practice {skill_name} with hands-on exercises"},
                    {"step": 3, "phase": "challenge", "description": f"Complete a practical {skill_name} challenge"},
                    {"step": 4, "phase": "assessment", "description": f"Take a {skill_name} assessment"},
                    {"step": 5, "phase": "evidence", "description": f"Add project evidence demonstrating {skill_name}"},
                ],
                "estimated_effort": "high",
                "demand_context": gap_demand.get("count", 0) if gap_demand else 0,
            }

        if proof_status == "PROVE":
            return {
                "action": "PROVE",
                "steps": [
                    {"step": 1, "phase": "practice", "description": f"Practice {skill_name} in a project context"},
                    {"step": 2, "phase": "challenge", "description": f"Complete a practical {skill_name} challenge"},
                    {"step": 3, "phase": "assessment", "description": f"Take a {skill_name} assessment"},
                    {"step": 4, "phase": "evidence", "description": f"Add project evidence demonstrating {skill_name}"},
                ],
                "estimated_effort": "medium",
                "demand_context": gap_demand.get("count", 0) if gap_demand else 0,
            }

        # VERIFIED
        return {
            "action": "MAINTAIN",
            "steps": [
                {"step": 1, "phase": "maintain", "description": f"Keep {skill_name} skills current with latest developments"},
            ],
            "estimated_effort": "low",
            "demand_context": gap_demand.get("count", 0) if gap_demand else 0,
        }

    async def get_skill_proof_detail(
        self, user_id: uuid.UUID, skill_id: str
    ) -> dict | None:
        """Get detailed skill proof for a specific skill.

        Returns the skill's evidence, proof status, proof plan, and
        relevant learning resources.
        """
        proof = await self.get_skill_proof(user_id)
        skill_lower = skill_id.lower().strip()

        for skill in proof.get("skills", []):
            if skill["name"].lower().strip() == skill_lower:
                # Enrich with learning resources for LEARN/PROVE skills
                resources = []
                if skill.get("proof_status") in ("LEARN", "PROVE"):
                    try:
                        mapping = await self.learning_resources_for_skill(
                            skill["name"], limit=3
                        )
                        if hasattr(mapping, "resources"):
                            resources = [
                                {
                                    "title": r.resource.title,
                                    "provider": r.resource.provider,
                                    "url": r.resource.url,
                                    "duration_hours": r.resource.duration_hours,
                                    "cost": r.resource.cost,
                                    "is_free": r.resource.is_free,
                                    "coverage": r.coverage_pct,
                                }
                                for r in mapping.resources
                            ]
                    except Exception:
                        resources = []

                return {
                    "skill": skill["name"],
                    "category": skill.get("category"),
                    "proficiency": skill.get("proficiency"),
                    "years": skill.get("years"),
                    "proof_status": skill.get("proof_status"),
                    "evidence": skill.get("evidence", []),
                    "supported_by": skill.get("supported_by", []),
                    "proof_plan": skill.get("proof_plan", {}),
                    "learning_resources": resources,
                }

        return None

    # --- Overview Aggregation ---

    async def get_overview(self, user_id: uuid.UUID) -> dict:
        """Aggregate all data needed for the candidate Career Intelligence Dashboard.

        Returns a single response with profile, readiness, skills, jobs, gaps,
        opportunity unlock, time-to-ready, learning progress, career insight,
        and next best action. All data comes from existing agents/services.
        """
        from datetime import datetime, timezone

        profile_data: dict = {}
        matches: list = []
        gap_summary: dict = {}
        opportunity: dict = {}
        training_progress: dict = {}
        perceptions_total = 0

        # Fetch sequentially — SQLAlchemy async sessions cannot share concurrent queries
        try:
            profile_data = await self.get_profile(user_id)
        except Exception:
            profile_data = {"connected": False, "profile": None, "intelligence": None}

        try:
            matches = await self.get_job_matches(user_id, limit=20)
        except Exception:
            matches = []

        try:
            gap_summary_raw = await self.get_skill_gap_summary(user_id)
            gap_summary = gap_summary_raw.model_dump() if hasattr(gap_summary_raw, 'model_dump') else gap_summary_raw
        except Exception:
            gap_summary = {"total_analyses": 0, "analyzed_jobs": 0, "gap_skills": [], "teaching_plan": []}

        try:
            opp_raw = await self.get_opportunity_dashboard(user_id)
            opportunity = opp_raw.model_dump() if hasattr(opp_raw, 'model_dump') else opp_raw
        except Exception:
            opportunity = {"top_opportunity": None, "potential": 0, "unlocked_count": 0, "top_roles": []}

        try:
            training_progress = await self.get_training_progress(user_id)
        except Exception:
            training_progress = {"items": [], "total": 0}

        # Real time-to-ready comparisons for the candidate's top matched jobs.
        time_to_ready_items: list[dict] = []
        try:
            comparisons = await self.compare_target_jobs(user_id, hours_per_week=10.0)
            for c in list(comparisons)[:3]:
                payload = c.model_dump(mode="json") if hasattr(c, "model_dump") else dict(c)
                time_to_ready_items.append(payload)
        except Exception:
            time_to_ready_items = []

        try:
            from sqlalchemy import select, func
            from app.domain.skill2job_models import Skill2JobPerception
            count = (await self._session.execute(
                select(func.count()).select_from(Skill2JobPerception).where(
                    Skill2JobPerception.user_id == user_id
                )
            )).scalar()
            perceptions_total = count or 0
        except Exception:
            perceptions_total = 0

        # Extract profile data
        connected = getattr(profile_data, "connected", False) if profile_data else False
        profile = getattr(profile_data, "profile", None) if connected else None
        intelligence = getattr(profile_data, "intelligence", None) if profile_data else None

        # Compute profile completeness
        completeness_score = 0
        if intelligence and hasattr(intelligence, "completeness"):
            comp = intelligence.completeness
            completeness_score = comp.get("score", 0) if isinstance(comp, dict) else getattr(comp, "score", 0)
        elif profile:
            # Estimate completeness from available fields
            fields = ["location", "current_role", "phone", "bio"]
            filled = sum(1 for f in fields if getattr(profile, f, None))
            completeness_score = int((filled / len(fields)) * 100) if fields else 0

        # Extract skills
        skills_list = []
        if intelligence and hasattr(intelligence, "skills"):
            for s in (intelligence.skills or []):
                if isinstance(s, dict):
                    skills_list.append(s.get("name", ""))
                else:
                    skills_list.append(getattr(s, "name", str(s)))
        elif profile and hasattr(profile, "skills"):
            for s in (profile.skills or []):
                if isinstance(s, str):
                    skills_list.append(s)
                elif isinstance(s, dict):
                    skills_list.append(s.get("name", ""))

        # Compute readiness from matches
        readiness_score = 0
        if matches:
            scores = [m.get("overall_score", 0) if isinstance(m, dict) else getattr(m, "overall_score", 0) for m in matches]
            readiness_score = max(scores) if scores else 0

        # Gap analysis
        gap_skills = gap_summary.get("gap_skills", [])
        critical_count = sum(1 for g in gap_skills if g.get("priority") == "high" or g.get("count", 0) >= 5)

        # Skill gap items for display
        gap_items_display = []
        for g in gap_skills[:10]:
            gap_items_display.append({
                "skill": g.get("skill", ""),
                "count": g.get("count", 0),
                "priority": g.get("priority", "medium"),
                "jobs_demanding": g.get("jobs_demanding", []),
            })

        # Top matches for display
        top_matches = []
        for m in matches[:5]:
            if isinstance(m, dict):
                top_matches.append({
                    "job_id": m.get("job_id", ""),
                    "title": m.get("title", ""),
                    "company": m.get("company", ""),
                    "location": m.get("location", ""),
                    "overall_score": m.get("overall_score", 0),
                    "matched_skills": m.get("matched_skills", []),
                    "missing_required": m.get("missing_required", []),
                    "recommendation": m.get("recommendation", ""),
                })
            else:
                top_matches.append({
                    "job_id": str(getattr(m, "job_id", "")),
                    "title": getattr(m, "title", ""),
                    "company": getattr(m, "company", ""),
                    "location": getattr(m, "location", ""),
                    "overall_score": getattr(m, "overall_score", 0),
                    "matched_skills": getattr(m, "matched_skills", []),
                    "missing_required": getattr(m, "missing_required", []),
                    "recommendation": getattr(m, "recommendation", ""),
                })

        # Learning progress
        progress_items = training_progress.get("items", [])
        completed_count = sum(1 for p in progress_items if p.get("status") == "completed")
        total_modules = training_progress.get("total", 0)

        # Generate career insight (deterministic, grounded in data)
        career_insight = self._generate_career_insight(
            skills_list, gap_skills, top_matches, completeness_score
        )

        # Generate next best action
        next_action = self._determine_next_action(
            connected, skills_list, gap_skills, top_matches, completed_count, total_modules
        )

        return {
            "profile": {
                "connected": connected,
                "completeness": completeness_score,
                "skills_count": len(skills_list),
                "skills": skills_list[:20],
                "has_perceptions": perceptions_total > 0,
                "perceptions_count": perceptions_total,
            },
            "readiness": {
                "score": readiness_score,
            },
            "skills": {
                "total": len(skills_list),
                "items": skills_list[:30],
            },
            "skill_gaps": {
                "total": len(gap_skills),
                "critical": critical_count,
                "items": gap_items_display,
            },
            "jobs": {
                "relevant_count": len(matches),
                "top_matches": top_matches,
            },
            "opportunity_unlock": opportunity,
            "learning_progress": {
                "total_modules": total_modules,
                "completed": completed_count,
                "items": progress_items[:10],
            },
            "time_to_ready": {
                "items": time_to_ready_items,
                "source": "time-to-ready-comparison",
            },
            "career_insight": career_insight,
            "next_action": next_action,
            "last_analyzed": datetime.now(timezone.utc).isoformat() if matches else None,
        }

    def _generate_career_insight(
        self, skills: list[str], gap_skills: list[dict], matches: list[dict], completeness: int
    ) -> dict:
        """Generate a deterministic career insight grounded in actual data."""
        if not skills and not matches:
            return {
                "text": "Complete your profile and upload your resume to get personalized career insights.",
                "type": "onboarding",
                "evidence": [],
            }

        insight_parts = []
        evidence = []

        if skills:
            top_skills = skills[:5]
            insight_parts.append(
                f"Your {', '.join(top_skills[:3])} skills align with relevant opportunities."
            )
            evidence.append(f"Identified {len(skills)} skills from your profile")

        if gap_skills:
            top_gap = gap_skills[0]
            skill_name = top_gap.get("skill", "key skill")
            count = top_gap.get("count", 0)
            if count > 3:
                insight_parts.append(
                    f"'{skill_name}' is required by {count} relevant jobs and could significantly expand your opportunities."
                )
                evidence.append(f"'{skill_name}' demanded by {count} jobs")
            else:
                insight_parts.append(
                    f"Learning '{skill_name}' would help you match more opportunities."
                )

        if matches:
            best = matches[0]
            title = best.get("title", "role") if isinstance(best, dict) else getattr(best, "title", "role")
            score = best.get("overall_score", 0) if isinstance(best, dict) else getattr(best, "overall_score", 0)
            insight_parts.append(
                f"Your strongest match is '{title}' at {score}%."
            )
            evidence.append(f"Best match: {title} ({score}%)")

        return {
            "text": " ".join(insight_parts) if insight_parts else "Analyze your profile to discover opportunities.",
            "type": "analysis",
            "evidence": evidence,
        }

    def _determine_next_action(
        self,
        connected: bool,
        skills: list[str],
        gap_skills: list[dict],
        matches: list[dict],
        completed: int,
        total: int,
    ) -> dict:
        """Determine the best next action based on candidate state."""
        if not connected:
            return {
                "action": "Complete your profile",
                "description": "Add your skills and experience to unlock job matching.",
                "type": "profile",
                "priority": "high",
            }

        if not skills:
            return {
                "action": "Upload your resume",
                "description": "Let the AI extract your skills and experience.",
                "type": "perception",
                "priority": "high",
            }

        if not matches:
            return {
                "action": "Explore local jobs",
                "description": "Browse curated opportunities in your area.",
                "type": "jobs",
                "priority": "high",
            }

        if gap_skills:
            top_gap = gap_skills[0]
            return {
                "action": f"Learn {top_gap.get('skill', 'a skill')}",
                "description": f"This skill is required by {top_gap.get('count', 0)} relevant jobs.",
                "type": "learning",
                "priority": "medium",
            }

        if total > 0 and completed < total:
            return {
                "action": "Continue your learning plan",
                "description": f"{completed}/{total} modules completed.",
                "type": "training",
                "priority": "low",
            }

        return {
            "action": "Analyze your career readiness",
            "description": "Get an updated view of your job market position.",
            "type": "analysis",
            "priority": "low",
        }