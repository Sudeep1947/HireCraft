"""SimulationReportService — Phase 13 Simulation Reports & Decision Intelligence.

A READ-ONLY aggregation and presentation layer that consumes existing
simulation data (Phase 3-12) and produces structured, traceable,
exportable reports. It never reruns simulations, recalculates rankings,
or modifies live hiring data.

Architecture:
    Existing Simulation Data (Phases 3-12)
            ↓
    SimulationReportService (aggregation)
            ↓
    Structured Report (web / PDF / JSON / CSV)
"""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    SimulationReportFormat,
    SimulationReportStatus,
    SimulationReportType,
    SimulationStatus,
)
from app.domain.models import Job, User
from app.domain.simulation_models import (
    SimulationExecution,
    SimulationImpact,
    SimulationReport,
    SimulationResult,
    SimulationScenario,
)
from app.domain.simulation_report_schemas import (
    ReportAuditInfo,
    ReportCandidateImpact,
    ReportCandidateImpactTable,
    ReportCandidateMover,
    ReportComparisonMatrix,
    ReportConfigurationDiff,
    ReportData,
    ReportExecutiveSummary,
    ReportExplainabilityImpact,
    ReportFairnessImpact,
    ReportHeader,
    ReportLimitations,
    ReportRankingImpact,
    ReportRequirementChange,
    ReportRequirementImpact,
    ReportScalarDiff,
    ReportShortlistImpact,
    ReportSkillImpact,
    ReportThresholdImpact,
    ReportWeightDiff,
    SimulationReportCreate,
    SimulationReportListResponse,
    SimulationReportListItem,
    SimulationReportResponse,
    SimulationReportStatusResponse,
)
from app.domain.hiring_strategy_sandbox_models import HiringStrategySandbox, SandboxStrategy
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationImpactRepository,
    SimulationResultRepository,
)
from app.repositories.simulation_report import SimulationReportRepository
from app.repositories.sandbox import SandboxRepository, SandboxStrategyRepository
from app.services.audit_service import AuditService

logger = get_logger(__name__)

REPORT_VERSION = "1.0"

_WEIGHT_LABELS: dict[str, str] = {
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "certifications": "Certifications",
    "location": "Location",
    "employment_type": "Employment Type",
    "semantic": "Semantic Match",
}


def _safe_divide(num: float, denom: float, default: float = 0.0) -> float:
    return num / denom if denom else default


class SimulationReportService:
    """Generates and manages simulation reports.

    READ-ONLY: never modifies live hiring data, simulation scenarios,
    or simulation results.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._report_repo = SimulationReportRepository(session)
        self._scenario_repo = SimulationRepository(session)
        self._exec_repo = SimulationExecutionRepository(session)
        self._result_repo = SimulationResultRepository(session)
        self._impact_repo = SimulationImpactRepository(session)
        self._sandbox_repo = SandboxRepository(session)
        self._strategy_repo = SandboxStrategyRepository(session)
        self._audit_service = AuditService(session)

    # ─── CRUD ─────────────────────────────────────────────────────

    async def create_report(
        self, user: User, request: SimulationReportCreate,
    ) -> SimulationReportResponse:
        """Create a report request and generate the report content."""
        # Validate and resolve references
        scenario = None
        execution = None
        sandbox = None
        job = None
        organization_id = None

        if request.simulation_id:
            scenario = await self._scenario_repo.get_with_details(request.simulation_id)
            if not scenario:
                raise NotFoundError(f"Simulation {request.simulation_id} not found")
            await self._require_view(user, scenario)
            organization_id = scenario.organization_id
            job = scenario.job

            # Resolve execution
            if request.execution_id:
                execution = await self._exec_repo.get_for_scenario(
                    scenario.id, request.execution_id,
                )
                if not execution:
                    raise NotFoundError(f"Execution {request.execution_id} not found")
            else:
                execution = await self._exec_repo.latest_completed(scenario.id)

        if request.sandbox_id:
            sandbox = await self._sandbox_repo.get_with_details(request.sandbox_id)
            if not sandbox:
                raise NotFoundError(f"Sandbox {request.sandbox_id} not found")
            organization_id = sandbox.organization_id
            job = sandbox.job

        # Validate report type requirements
        self._validate_report_type(request, scenario, execution, sandbox)

        # Generate title if not provided
        title = request.title or self._generate_title(request, scenario, sandbox)

        # Create the report record
        params = request.model_dump(exclude={"include"})
        # Convert any UUID values to strings for JSON serialization
        params = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()}
        if params.get("comparison_scenario_ids"):
            params["comparison_scenario_ids"] = [str(s) for s in params["comparison_scenario_ids"]]

        report = await self._report_repo.create(
            organization_id=organization_id,
            sandbox_id=request.sandbox_id,
            scenario_id=request.simulation_id,
            execution_id=execution.id if execution else None,
            job_id=job.id if job else None,
            created_by=user.id,
            report_type=request.report_type,
            title=title,
            description=request.description,
            status=SimulationReportStatus.GENERATING.value,
            format=request.format,
            parameters=params,
            report_version=REPORT_VERSION,
        )
        await self._session.flush()

        try:
            # Build the report data
            report_data = await self._build_report(
                request, report, scenario, execution, sandbox, job, user,
            )
            now = datetime.now(timezone.utc)
            report.status = SimulationReportStatus.COMPLETED.value
            report.report_data = report_data.model_dump()
            report.completed_at = now
            report.source_snapshot = {
                "scenario_id": str(scenario.id) if scenario else None,
                "execution_id": str(execution.id) if execution else None,
                "sandbox_id": str(sandbox.id) if sandbox else None,
                "generated_at": now.isoformat(),
            }
            await self._session.flush()

            await self._audit(
                AuditEventType.SIMULATION_REPORT_CREATED,
                "simulation_report_created",
                user, report,
            )

        except Exception as exc:
            logger.exception("Report generation failed: report=%s", report.id)
            report.status = SimulationReportStatus.FAILED.value
            report.error_message = str(exc)[:1000]
            await self._session.flush()
            await self._audit(
                AuditEventType.SIMULATION_REPORT_GENERATION_FAILED,
                "simulation_report_generation_failed",
                user, report,
                success=False,
            )
            raise

        return await self._load_report_response(report.id)

    async def get_report(
        self, user: User, report_id: uuid.UUID,
    ) -> SimulationReportResponse:
        """Retrieve a completed report."""
        report = await self._report_repo.get_with_details(report_id)
        if not report:
            raise NotFoundError("Report not found")
        await self._require_report_view(user, report)
        return SimulationReportResponse.model_validate(report)

    async def get_report_status(
        self, user: User, report_id: uuid.UUID,
    ) -> SimulationReportStatusResponse:
        """Check report generation status."""
        report = await self._report_repo.get(report_id)
        if not report:
            raise NotFoundError("Report not found")
        await self._require_report_view(user, report)
        return SimulationReportStatusResponse(
            report_id=report.id,
            status=report.status,
            error_message=report.error_message,
            completed_at=report.completed_at,
        )

    async def list_reports(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> SimulationReportListResponse:
        """List reports the user has access to."""
        org_ids = await self._get_user_org_ids(user)
        reports, total = await self._report_repo.list_by_user(
            user.id, org_ids, page=page, page_size=page_size,
        )
        items = []
        for r in reports:
            items.append(SimulationReportListItem(
                id=r.id,
                organization_id=r.organization_id,
                sandbox_id=r.sandbox_id,
                scenario_id=r.scenario_id,
                execution_id=r.execution_id,
                job_id=r.job_id,
                created_by=r.created_by,
                report_type=r.report_type,
                title=r.title,
                description=r.description,
                status=r.status,
                format=r.format,
                report_version=r.report_version,
                job_title=r.job.title if r.job else "",
                scenario_name=r.scenario.name if r.scenario else "",
                sandbox_name=r.sandbox.name if r.sandbox else "",
                created_by_name=r.creator.full_name if r.creator else "",
                created_at=r.created_at,
                updated_at=r.updated_at,
                completed_at=r.completed_at,
            ))
        return SimulationReportListResponse(
            items=items, total=total, page=page, page_size=page_size,
        )

    async def delete_report(
        self, user: User, report_id: uuid.UUID,
    ) -> None:
        """Delete a report."""
        report = await self._report_repo.get_with_details(report_id)
        if not report:
            raise NotFoundError("Report not found")
        await self._require_report_view(user, report)
        await self._audit(
            AuditEventType.SIMULATION_REPORT_DELETED,
            "simulation_report_deleted",
            user, report,
        )
        await self._report_repo.delete(report_id)

    async def get_report_json(
        self, user: User, report_id: uuid.UUID,
    ) -> dict:
        """Get report data as JSON."""
        report = await self._report_repo.get_with_details(report_id)
        if not report:
            raise NotFoundError("Report not found")
        await self._require_report_view(user, report)
        await self._audit(
            AuditEventType.SIMULATION_REPORT_EXPORTED,
            "simulation_report_exported",
            user, report,
            details={"format": "json"},
        )
        return report.report_data or {}

    # ─── Report Building ──────────────────────────────────────────

    async def _build_report(
        self,
        request: SimulationReportCreate,
        report: SimulationReport,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
        sandbox: HiringStrategySandbox | None,
        job: Job | None,
        user: User,
    ) -> ReportData:
        """Build the complete report data from existing simulation data."""
        includes = request.include

        # Build header
        header = self._build_header(report, scenario, execution, sandbox, job, user)

        # Build executive summary
        executive_summary = await self._build_executive_summary(
            request, scenario, execution, sandbox, job,
        )

        # Build configuration diff
        configuration_diff = self._build_configuration_diff(scenario, execution)

        # Build candidate impact
        candidate_impact = ReportCandidateImpact()
        candidate_impact_table = ReportCandidateImpactTable()
        if execution and includes.include_candidate_details:
            candidate_impact = await self._build_candidate_impact(execution)
            candidate_impact_table = await self._build_candidate_impact_table(execution)

        # Build ranking impact
        ranking_impact = ReportRankingImpact()
        if execution and includes.include_ranking:
            ranking_impact = await self._build_ranking_impact(execution)

        # Build requirement impact
        requirement_impact = ReportRequirementImpact()
        if execution and includes.include_requirements:
            requirement_impact = await self._build_requirement_impact(execution)

        # Build threshold impact
        threshold_impact = ReportThresholdImpact()
        if execution and includes.include_threshold:
            threshold_impact = await self._build_threshold_impact(execution)

        # Build shortlist impact
        shortlist_impact = ReportShortlistImpact()
        if execution and includes.include_shortlist:
            shortlist_impact = await self._build_shortlist_impact(execution)

        # Build fairness impact
        fairness_impact = ReportFairnessImpact()
        if execution and includes.include_fairness:
            fairness_impact = await self._build_fairness_impact(execution)

        # Build explainability impact
        explainability_impact = ReportExplainabilityImpact()
        if execution and includes.include_explainability:
            explainability_impact = await self._build_explainability_impact(execution)

        # Build skill impact
        skill_impact = ReportSkillImpact()
        if execution and includes.include_skill_impact:
            skill_impact = await self._build_skill_impact(execution)

        # Build comparison matrix (for comparison/sandbox reports)
        comparison_matrix = ReportComparisonMatrix()
        if request.report_type in ("comparison", "sandbox") and includes.include_comparison:
            comparison_matrix = await self._build_comparison_matrix(request, sandbox)

        # Build limitations
        limitations = self._build_limitations(
            scenario, execution, sandbox, candidate_impact, fairness_impact,
        )

        # Build audit info
        audit_info = ReportAuditInfo(
            report_id=str(report.id),
            generated_by=user.full_name if user else "",
            generated_at=report.created_at.isoformat() if report.created_at else "",
            simulation_id=str(scenario.id) if scenario else "",
            execution_id=str(execution.id) if execution else "",
            scenario_id=str(scenario.id) if scenario else "",
            sandbox_id=str(sandbox.id) if sandbox else "",
            report_type=request.report_type,
            report_version=REPORT_VERSION,
            engine_version=execution.engine_version if execution else "",
        )

        return ReportData(
            header=header,
            executive_summary=executive_summary,
            configuration_diff=configuration_diff,
            candidate_impact=candidate_impact,
            candidate_impact_table=candidate_impact_table,
            ranking_impact=ranking_impact,
            requirement_impact=requirement_impact,
            threshold_impact=threshold_impact,
            shortlist_impact=shortlist_impact,
            fairness_impact=fairness_impact,
            explainability_impact=explainability_impact,
            skill_impact=skill_impact,
            comparison_matrix=comparison_matrix,
            limitations=limitations,
            audit_info=audit_info,
        )

    # ─── Section Builders ─────────────────────────────────────────

    def _build_header(
        self,
        report: SimulationReport,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
        sandbox: HiringStrategySandbox | None,
        job: Job | None,
        user: User,
    ) -> ReportHeader:
        return ReportHeader(
            title=report.title,
            report_type=report.report_type,
            job_title=job.title if job else "",
            job_id=str(job.id) if job else "",
            sandbox_name=sandbox.name if sandbox else "",
            sandbox_id=str(sandbox.id) if sandbox else "",
            scenario_name=scenario.name if scenario else "",
            scenario_id=str(scenario.id) if scenario else "",
            simulation_id=str(scenario.id) if scenario else "",
            execution_id=str(execution.id) if execution else "",
            generated_by=user.full_name if user else "",
            generated_at=report.created_at.isoformat() if report.created_at else "",
            report_version=report.report_version,
            status=report.status,
        )

    async def _build_executive_summary(
        self,
        request: SimulationReportCreate,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
        sandbox: HiringStrategySandbox | None,
        job: Job | None,
    ) -> ReportExecutiveSummary:
        """Generate a factual executive summary from persisted data."""
        if not execution:
            return ReportExecutiveSummary(
                narrative="No completed execution available for this simulation.",
            )

        snapshot = execution.configuration_snapshot or {}
        baseline = snapshot.get("baseline") or {}
        simulation = snapshot.get("simulation") or {}
        job_info = snapshot.get("job") or {}
        summary = execution.summary or {}

        job_title = job_info.get("title", "the role")
        total = execution.total_candidates

        # Collect configuration changes
        changes = []
        base_weights = baseline.get("scoring_weights") or {}
        sim_weights = simulation.get("scoring_weights") or {}
        for key in ["skills", "experience", "education", "projects"]:
            b = base_weights.get(key, 0)
            s = sim_weights.get(key, 0)
            if b != s:
                changes.append(
                    f"{_WEIGHT_LABELS.get(key, key)} weight from {round(b * 100)}% to {round(s * 100)}%"
                )

        base_threshold = baseline.get("threshold", 70)
        sim_threshold = simulation.get("threshold", 70)
        if base_threshold != sim_threshold:
            changes.append(f"minimum score threshold from {base_threshold} to {sim_threshold}")

        base_shortlist = baseline.get("shortlist_size", 10)
        sim_shortlist = simulation.get("shortlist_size", 10)
        if base_shortlist != sim_shortlist:
            changes.append(f"shortlist size from {base_shortlist} to {sim_shortlist}")

        # Build narrative
        scenario_name = scenario.name if scenario else "the hypothetical configuration"
        if changes:
            changes_text = ", ".join(changes[:4])
            narrative = (
                f"This simulation evaluated {total} candidates for {job_title} "
                f"using '{scenario_name}' which changed {changes_text}."
            )
        else:
            narrative = (
                f"This simulation evaluated {total} candidates for {job_title} "
                f"using '{scenario_name}'."
            )

        # Candidate impact summary
        qualified_change = summary.get("qualified", {}).get("change", 0)
        shortlisted_change = summary.get("shortlisted", {}).get("change", 0)
        candidate_summary = (
            f"The simulation produced changes in candidate scores, rankings, "
            f"qualification status ({qualified_change:+d} qualified), "
            f"and shortlist membership ({shortlisted_change:+d} shortlisted)."
        )

        # Fairness summary
        fairness_summary = "Fairness data is not available for this execution."
        fairness_data = summary.get("fairness") or summary.get("fairness_metrics")
        if fairness_data:
            fairness_summary = "Fairness metrics were computed and are available in the Fairness section."

        # Major differences
        major = []
        top_changed = summary.get("top_candidate_changed", False)
        if top_changed:
            base_top = summary.get("baseline_top_candidate", "")
            sim_top = simulation.get("simulation_top_candidate", "") or summary.get("simulation_top_candidate", "")
            if base_top and sim_top:
                major.append(f"The top-ranked candidate changed from {base_top} to {sim_top}.")

        avg_change = summary.get("average_score", {}).get("change", 0)
        if avg_change != 0:
            major.append(f"Average candidate score changed by {avg_change:+.1f} points.")

        return ReportExecutiveSummary(
            narrative=narrative,
            total_candidates_evaluated=total,
            key_configuration_changes=changes,
            candidate_impact_summary=candidate_summary,
            fairness_summary=fairness_summary,
            major_observed_differences=major,
        )

    def _build_configuration_diff(
        self,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
    ) -> ReportConfigurationDiff:
        """Build baseline vs simulation configuration diff from snapshot."""
        if not execution:
            return ReportConfigurationDiff()

        snapshot = execution.configuration_snapshot or {}
        baseline = snapshot.get("baseline") or {}
        simulation = snapshot.get("simulation") or {}

        base_weights = baseline.get("scoring_weights") or {}
        sim_weights = simulation.get("scoring_weights") or {}

        weights = []
        for key in ["skills", "experience", "education", "projects", "certifications"]:
            b = base_weights.get(key, 0.0)
            s = sim_weights.get(key, 0.0)
            change = round(s - b, 4)
            change_pct = round(change * 100, 1)
            label = "unchanged"
            if change > 0:
                label = f"+{change_pct} pp"
            elif change < 0:
                label = f"{change_pct} pp"
            weights.append(ReportWeightDiff(
                weight_name=key,
                weight_label=_WEIGHT_LABELS.get(key, key),
                baseline=round(b, 4),
                simulation=round(s, 4),
                change=change,
                change_label=label,
            ))

        # Threshold diff
        base_threshold = baseline.get("threshold", 70)
        sim_threshold = simulation.get("threshold", 70)
        threshold = ReportScalarDiff(
            label="Minimum Score Threshold",
            baseline=base_threshold,
            simulation=sim_threshold,
            change=sim_threshold - base_threshold,
            change_label=f"{sim_threshold - base_threshold:+d}",
        ) if base_threshold != sim_threshold else None

        # Shortlist diff
        base_shortlist = baseline.get("shortlist_size", 10)
        sim_shortlist = simulation.get("shortlist_size", 10)
        shortlist_size = ReportScalarDiff(
            label="Shortlist Size",
            baseline=base_shortlist,
            simulation=sim_shortlist,
            change=sim_shortlist - base_shortlist,
            change_label=f"{sim_shortlist - base_shortlist:+d}",
        ) if base_shortlist != sim_shortlist else None

        # Requirement changes
        base_reqs = baseline.get("requirements") or {}
        sim_reqs = simulation.get("requirements") or {}
        req_changes = []

        base_mandatory = set(base_reqs.get("mandatory_skills") or [])
        sim_mandatory = set(sim_reqs.get("mandatory_skills") or [])
        base_preferred = set(base_reqs.get("preferred_skills") or [])
        sim_preferred = set(sim_reqs.get("preferred_skills") or [])

        all_skills = base_mandatory | sim_mandatory | base_preferred | sim_preferred
        for skill in sorted(all_skills):
            b_status = "mandatory" if skill in base_mandatory else ("preferred" if skill in base_preferred else "not_required")
            s_status = "mandatory" if skill in sim_mandatory else ("preferred" if skill in sim_preferred else "not_required")
            if b_status != s_status:
                req_changes.append(ReportRequirementChange(
                    skill=skill,
                    from_status=b_status,
                    to_status=s_status,
                ))

        return ReportConfigurationDiff(
            weights=weights,
            threshold=threshold,
            shortlist_size=shortlist_size,
            requirement_changes=req_changes,
        )

    async def _build_candidate_impact(
        self, execution: SimulationExecution,
    ) -> ReportCandidateImpact:
        """Build aggregate candidate impact from persisted results."""
        results = await self._result_repo.list_by_execution(execution.id)
        if not results:
            return ReportCandidateImpact()

        total = len(results)
        score_changes = [r.score_change for r in results]
        rank_changes = [r.rank_change for r in results]

        entering = sum(1 for r in results if r.simulation_shortlisted and not r.baseline_shortlisted)
        leaving = sum(1 for r in results if r.baseline_shortlisted and not r.simulation_shortlisted)
        retained = sum(1 for r in results if r.simulation_shortlisted and r.baseline_shortlisted)
        qual_changes = sum(1 for r in results if r.baseline_status != r.simulation_status)

        # Top movers
        sorted_by_score = sorted(results, key=lambda r: r.score_change, reverse=True)
        sorted_by_rank = sorted(results, key=lambda r: r.rank_change, reverse=True)

        def _to_mover(r: SimulationResult) -> ReportCandidateMover:
            return ReportCandidateMover(
                candidate_id=str(r.candidate_id),
                candidate_name=r.candidate_name,
                baseline_score=r.baseline_score,
                simulation_score=r.simulation_score,
                score_change=r.score_change,
                baseline_rank=r.baseline_rank,
                simulation_rank=r.simulation_rank,
                rank_change=r.rank_change,
                shortlisted=r.simulation_shortlisted,
            )

        return ReportCandidateImpact(
            total_candidates=total,
            candidates_with_score_changes=sum(1 for c in score_changes if c != 0),
            candidates_with_rank_changes=sum(1 for c in rank_changes if c != 0),
            candidates_entering_shortlist=entering,
            candidates_leaving_shortlist=leaving,
            retained_shortlist_candidates=retained,
            qualification_changes=qual_changes,
            largest_score_movement=max(abs(c) for c in score_changes) if score_changes else 0,
            largest_rank_movement=max(abs(c) for c in rank_changes) if rank_changes else 0,
            average_score_change=round(_safe_divide(sum(score_changes), total), 2),
            average_rank_change=round(_safe_divide(sum(rank_changes), total), 2),
            top_movers_increases=[_to_mover(r) for r in sorted_by_score[:5] if r.score_change > 0],
            top_movers_decreases=[_to_mover(r) for r in sorted_by_score[-5:] if r.score_change < 0],
            top_rank_improvements=[_to_mover(r) for r in sorted_by_rank[:5] if r.rank_change > 0],
            top_rank_declines=[_to_mover(r) for r in sorted_by_rank[-5:] if r.rank_change < 0],
        )

    async def _build_candidate_impact_table(
        self, execution: SimulationExecution,
    ) -> ReportCandidateImpactTable:
        """Build the paginated candidate impact table (first page for report)."""
        results = await self._result_repo.list_by_execution(execution.id)
        sorted_results = sorted(results, key=lambda r: abs(r.rank_change), reverse=True)

        items = []
        for r in sorted_results[:50]:  # Top 50 movers for report
            items.append(ReportCandidateMover(
                candidate_id=str(r.candidate_id),
                candidate_name=r.candidate_name,
                baseline_score=r.baseline_score,
                simulation_score=r.simulation_score,
                score_change=r.score_change,
                baseline_rank=r.baseline_rank,
                simulation_rank=r.simulation_rank,
                rank_change=r.rank_change,
                shortlisted=r.simulation_shortlisted,
            ))
        return ReportCandidateImpactTable(
            items=items,
            total=len(results),
        )

    async def _build_ranking_impact(
        self, execution: SimulationExecution,
    ) -> ReportRankingImpact:
        """Build ranking impact section from persisted results."""
        results = await self._result_repo.list_by_execution(execution.id)
        if not results:
            return ReportRankingImpact()

        scores = [r.simulation_score for r in results]
        rank_changes = [r.rank_change for r in results]
        score_changes = [r.score_change for r in results]

        improved = sum(1 for r in rank_changes if r > 0)
        declined = sum(1 for r in rank_changes if r < 0)
        unchanged = len(rank_changes) - improved - declined

        return ReportRankingImpact(
            overview={
                "total_candidates": len(results),
                "average_score_change": round(_safe_divide(sum(score_changes), len(results)), 2),
                "median_score_change": round(statistics.median(score_changes) if score_changes else 0, 2),
                "average_rank_change": round(_safe_divide(sum(rank_changes), len(results)), 2),
                "candidates_moved_up": improved,
                "candidates_moved_down": declined,
                "candidates_unchanged": unchanged,
            },
            score_movement={
                "average_change": round(_safe_divide(sum(score_changes), len(results)), 2),
                "minimum_change": min(score_changes) if score_changes else 0,
                "maximum_change": max(score_changes) if score_changes else 0,
                "positive_count": sum(1 for c in score_changes if c > 0),
                "negative_count": sum(1 for c in score_changes if c < 0),
            },
            distributions={
                "score_mean": round(statistics.mean(scores) if scores else 0, 2),
                "score_median": round(statistics.median(scores) if scores else 0, 2),
                "score_stdev": round(statistics.stdev(scores) if len(scores) > 1 else 0, 2),
            },
        )

    async def _build_requirement_impact(
        self, execution: SimulationExecution,
    ) -> ReportRequirementImpact:
        """Build requirement impact from persisted data."""
        results = await self._result_repo.list_by_execution(execution.id)
        snapshot = execution.configuration_snapshot or {}
        baseline = snapshot.get("baseline") or {}
        simulation = snapshot.get("simulation") or {}

        base_reqs = baseline.get("requirements") or {}
        sim_reqs = simulation.get("requirements") or {}

        base_mandatory = set(base_reqs.get("mandatory_skills") or [])
        sim_mandatory = set(sim_reqs.get("mandatory_skills") or [])
        base_preferred = set(base_reqs.get("preferred_skills") or [])
        sim_preferred = set(sim_reqs.get("preferred_skills") or [])

        added = list(sim_mandatory - base_mandatory)
        removed = list(base_mandatory - sim_mandatory)

        # Check promotions/demotions between preferred <-> mandatory
        promoted = list((sim_mandatory & base_preferred) - base_mandatory)
        demoted = list((base_mandatory & sim_preferred) - sim_mandatory)

        # Count affected candidates
        affected = 0
        for r in results:
            base_skills = set(r.baseline_matched_skills or [])
            sim_skills = set(r.simulation_matched_skills or [])
            if base_skills != sim_skills:
                affected += 1

        return ReportRequirementImpact(
            total_changed=len(added) + len(removed) + len(promoted) + len(demoted),
            added=added,
            removed=removed,
            promoted=promoted,
            demoted=demoted,
            candidates_affected=affected,
        )

    async def _build_threshold_impact(
        self, execution: SimulationExecution,
    ) -> ReportThresholdImpact:
        """Build threshold impact from persisted data."""
        results = await self._result_repo.list_by_execution(execution.id)
        snapshot = execution.configuration_snapshot or {}
        baseline = snapshot.get("baseline") or {}
        simulation = snapshot.get("simulation") or {}

        base_threshold = baseline.get("threshold", 70)
        sim_threshold = simulation.get("threshold", 70)

        qualified_base = sum(1 for r in results if r.baseline_status == "qualified")
        qualified_sim = sum(1 for r in results if r.simulation_status == "qualified")

        newly_qualified = sum(
            1 for r in results
            if r.simulation_status == "qualified" and r.baseline_status != "qualified"
        )
        newly_disqualified = sum(
            1 for r in results
            if r.simulation_status != "qualified" and r.baseline_status == "qualified"
        )

        # Boundary candidates (score near either threshold)
        boundary_range = 5
        boundary = [
            {
                "candidate_name": r.candidate_name,
                "baseline_score": r.baseline_score,
                "simulation_score": r.simulation_score,
                "baseline_status": r.baseline_status,
                "simulation_status": r.simulation_status,
            }
            for r in results
            if (abs(r.baseline_score - base_threshold) <= boundary_range
                or abs(r.simulation_score - sim_threshold) <= boundary_range)
            and r.baseline_status != r.simulation_status
        ]

        change = "unchanged"
        if qualified_sim > qualified_base:
            change = "more candidates qualified"
        elif qualified_sim < qualified_base:
            change = "fewer candidates qualified"

        return ReportThresholdImpact(
            baseline_threshold=base_threshold,
            simulation_threshold=sim_threshold,
            qualified_baseline=qualified_base,
            qualified_simulation=qualified_sim,
            newly_qualified=newly_qualified,
            newly_disqualified=newly_disqualified,
            boundary_candidates=boundary[:10],
            qualification_change=change,
        )

    async def _build_shortlist_impact(
        self, execution: SimulationExecution,
    ) -> ReportShortlistImpact:
        """Build shortlist impact from persisted data."""
        results = await self._result_repo.list_by_execution(execution.id)
        snapshot = execution.configuration_snapshot or {}
        baseline = snapshot.get("baseline") or {}
        simulation = snapshot.get("simulation") or {}

        base_size = baseline.get("shortlist_size", 10)
        sim_size = simulation.get("shortlist_size", 10)

        base_shortlisted = {r.candidate_id for r in results if r.baseline_shortlisted}
        sim_shortlisted = {r.candidate_id for r in results if r.simulation_shortlisted}

        retained = base_shortlisted & sim_shortlisted
        entering = sim_shortlisted - base_shortlisted
        leaving = base_shortlisted - sim_shortlisted

        union = base_shortlisted | sim_shortlisted
        overlap_pct = round(_safe_divide(len(retained), len(union)) * 100, 1) if union else 0

        return ReportShortlistImpact(
            baseline_shortlist_size=base_size,
            simulation_shortlist_size=sim_size,
            retained=len(retained),
            entering=len(entering),
            leaving=len(leaving),
            overlap_percentage=overlap_pct,
        )

    async def _build_fairness_impact(
        self, execution: SimulationExecution,
    ) -> ReportFairnessImpact:
        """Build fairness impact from persisted execution summary."""
        summary = execution.summary or {}
        fairness_data = summary.get("fairness") or summary.get("fairness_metrics")

        if not fairness_data or not isinstance(fairness_data, dict):
            return ReportFairnessImpact(
                available=False,
                unavailable_reason="Fairness analysis was not performed for this execution.",
            )

        return ReportFairnessImpact(
            available=True,
            groups=fairness_data.get("groups", []),
            cross_group_metrics=fairness_data.get("cross_group", []),
            limitations=["Fairness metrics are based on available demographic data."],
        )

    async def _build_explainability_impact(
        self, execution: SimulationExecution,
    ) -> ReportExplainabilityImpact:
        """Build explainability impact from persisted execution summary."""
        summary = execution.summary or {}
        xai_data = summary.get("explainability") or summary.get("xai")

        if not xai_data or not isinstance(xai_data, dict):
            return ReportExplainabilityImpact(
                available=False,
                unavailable_reason="Explainability analysis was not performed for this execution.",
            )

        return ReportExplainabilityImpact(
            available=True,
            feature_contribution_changes=xai_data.get("weight_changes", []),
            weight_changes=xai_data.get("weight_changes", []),
        )

    async def _build_skill_impact(
        self, execution: SimulationExecution,
    ) -> ReportSkillImpact:
        """Build skill impact from persisted execution summary."""
        summary = execution.summary or {}
        skill_data = summary.get("skill_impact") or summary.get("skills")

        if not skill_data or not isinstance(skill_data, dict):
            return ReportSkillImpact(
                available=False,
                unavailable_reason="Skill impact analysis was not performed for this execution.",
            )

        return ReportSkillImpact(
            available=True,
            candidates_affected=skill_data.get("candidates_affected", 0),
            skill_gaps=skill_data.get("top_gaps", []),
        )

    async def _build_comparison_matrix(
        self,
        request: SimulationReportCreate,
        sandbox: HiringStrategySandbox | None,
    ) -> ReportComparisonMatrix:
        """Build comparison matrix for multi-scenario or sandbox reports."""
        if request.comparison_scenario_ids:
            # Build from specified scenarios
            scenarios_data = []
            for sid in request.comparison_scenario_ids:
                scenario = await self._scenario_repo.get_with_details(sid)
                if scenario:
                    execution = await self._exec_repo.latest_completed(scenario.id)
                    snapshot = (execution.configuration_snapshot or {}) if execution else {}
                    sim_config = snapshot.get("simulation") or {}
                    scenarios_data.append({
                        "scenario_id": str(scenario.id),
                        "name": scenario.name,
                        "status": scenario.status,
                        "threshold": sim_config.get("threshold", 70),
                        "shortlist_size": sim_config.get("shortlist_size", 10),
                        "weights": sim_config.get("scoring_weights", {}),
                    })
            return ReportComparisonMatrix(scenarios=scenarios_data)

        if sandbox:
            strategies = await self._strategy_repo.list_by_sandbox(sandbox.id)
            scenarios_data = []
            for strategy in strategies:
                scenario = strategy.scenario
                if scenario:
                    execution = await self._exec_repo.latest_completed(scenario.id)
                    snapshot = (execution.configuration_snapshot or {}) if execution else {}
                    sim_config = snapshot.get("simulation") or {}
                    scenarios_data.append({
                        "strategy_id": str(strategy.id),
                        "scenario_id": str(scenario.id),
                        "name": strategy.name or scenario.name,
                        "status": scenario.status,
                        "threshold": sim_config.get("threshold", 70),
                        "shortlist_size": sim_config.get("shortlist_size", 10),
                        "weights": sim_config.get("scoring_weights", {}),
                        "parent_strategy_id": str(strategy.parent_strategy_id) if strategy.parent_strategy_id else None,
                    })
            return ReportComparisonMatrix(scenarios=scenarios_data)

        return ReportComparisonMatrix()

    def _build_limitations(
        self,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
        sandbox: HiringStrategySandbox | None,
        candidate_impact: ReportCandidateImpact,
        fairness_impact: ReportFairnessImpact,
    ) -> ReportLimitations:
        """Build limitations section."""
        items = []
        data_integrity = [
            "This report was generated from persisted simulation results.",
            "No live hiring data was modified during report generation.",
        ]

        if not execution:
            items.append("No completed execution available for this simulation.")
        elif execution.status != SimulationStatus.COMPLETED.value:
            items.append(f"Execution status is '{execution.status}', not 'completed'.")

        if not fairness_impact.available:
            items.append("Fairness metrics are unavailable for this execution.")

        if candidate_impact.total_candidates == 0:
            items.append("No candidate results are available.")

        if sandbox:
            items.append("Sandbox report includes all strategies in the sandbox.")

        return ReportLimitations(
            items=items,
            data_integrity_notes=data_integrity,
        )

    # ─── Helpers ──────────────────────────────────────────────────

    def _validate_report_type(
        self,
        request: SimulationReportCreate,
        scenario: SimulationScenario | None,
        execution: SimulationExecution | None,
        sandbox: HiringStrategySandbox | None,
    ) -> None:
        """Validate that the report type has required references."""
        if request.report_type in ("simulation", "candidate_impact", "fairness_impact", "executive", "technical"):
            if not scenario:
                raise ValidationError("simulation_id is required for this report type.")
        if request.report_type == "comparison":
            if not request.comparison_scenario_ids or len(request.comparison_scenario_ids) < 2:
                raise ValidationError("At least 2 scenario IDs are required for comparison reports.")
        if request.report_type == "sandbox":
            if not sandbox:
                raise ValidationError("sandbox_id is required for sandbox reports.")

    def _generate_title(
        self,
        request: SimulationReportCreate,
        scenario: SimulationScenario | None,
        sandbox: HiringStrategySandbox | None,
    ) -> str:
        """Auto-generate a report title."""
        type_labels = {
            "simulation": "Simulation Report",
            "candidate_impact": "Candidate Impact Report",
            "fairness_impact": "Fairness Impact Report",
            "comparison": "Strategy Comparison Report",
            "sandbox": "Sandbox Report",
            "executive": "Executive Summary",
            "technical": "Technical Report",
        }
        label = type_labels.get(request.report_type, "Report")
        if scenario:
            return f"{label} — {scenario.name}"
        if sandbox:
            return f"{label} — {sandbox.name}"
        return label

    async def _require_view(self, user: User, scenario: SimulationScenario) -> None:
        """Verify user can view the simulation."""
        # Allow if user is the creator
        if scenario.created_by == user.id:
            return
        # Allow if user has privileged role
        role_names = {ur.role.name for ur in user.roles}
        if role_names & {"super_admin", "organization_admin", "hr_manager", "recruiter"}:
            return
        raise NotFoundError("Simulation not found")

    async def _require_report_view(self, user: User, report: SimulationReport) -> None:
        """Verify user can view the report."""
        if report.created_by == user.id:
            return
        role_names = {ur.role.name for ur in user.roles}
        if role_names & {"super_admin", "organization_admin", "hr_manager", "recruiter"}:
            return
        raise NotFoundError("Report not found")

    async def _get_user_org_ids(self, user: User) -> list[uuid.UUID]:
        """Get organization IDs the user belongs to."""
        from app.domain.models import OrganizationMembership
        from sqlalchemy import select

        stmt = select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active",
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _load_report_response(self, report_id: uuid.UUID) -> SimulationReportResponse:
        """Load and return a report response."""
        report = await self._report_repo.get_with_details(report_id)
        if not report:
            raise NotFoundError("Report not found")
        return SimulationReportResponse.model_validate(report)

    async def _audit(
        self,
        event_type: AuditEventType,
        action: str,
        user: User,
        report: SimulationReport,
        details: dict | None = None,
        success: bool = True,
    ) -> None:
        try:
            await self._audit_service.log(
                event_type=event_type,
                action=action,
                user_id=user.id,
                organization_id=report.organization_id,
                resource_type="simulation_report",
                resource_id=str(report.id),
                details=details or {"report_type": report.report_type},
                success=success,
            )
        except Exception:
            pass
