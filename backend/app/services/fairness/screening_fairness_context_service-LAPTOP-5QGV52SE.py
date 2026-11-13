"""Application-centric fairness context for the screening workflow (Phase 7).

This service is a **presentation and authorization layer only**. It contains no
fairness calculation of its own: every metric, alert and job-description
finding is produced by the existing :class:`FairnessEngine` and mapped here into
the Phase 7 response contract. There is deliberately no second fairness engine.

Three properties are enforced structurally rather than by convention:

1. **Read-only.** Nothing in this module writes to screening results, match
   scores, rankings, application status or candidate profiles. Fairness is
   decision support; it never acts on a hiring outcome.
2. **Population-scoped.** The unit of analysis is the job's screened
   population. The application being viewed is reported as a *member* of that
   population, and no fairness value is attributed to the individual.
3. **Never a score.** Fairness is not combined with the match score anywhere, and
   the screening score is not re-read or re-derived here.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.domain.enums import AuditEventType, ScreeningStatus
from app.domain.fairness_context_schemas import (
    AdversarialContextView,
    ApplicationFairnessContextResponse,
    FairnessAlertView,
    FairnessCoverage,
    FairnessCrossGroupMetric,
    FairnessContextApplication,
    FairnessContextJob,
    FairnessFinding,
    FairnessGroupAnalysis,
    FairnessGroupOutcome,
    FairnessPopulation,
    FairnessScoreDistribution,
    FairnessScreeningState,
    FairnessSection,
    FairnessSuggestion,
    JobDescriptionBiasView,
)
from app.domain.models import Job, JobApplication, ScreeningResult, User
from app.repositories.screening.screening import ScreeningResultRepository
from app.services.audit_service import AuditService
from app.services.fairness.fairness_engine import (
    DEFAULT_MINIMUM_GROUP_SIZE,
    GROUP_METRIC_SCOPE,
    FairnessEngine,
)
from app.services.screening.access import authorize_job_access

logger = logging.getLogger(__name__)

POPULATION_NOTE = (
    "Fairness metrics describe this job's screened population as a whole. They "
    "are not a property of the individual candidate and are not combined with "
    "their match score."
)

SCORE_DISTRIBUTION_NOTE = (
    "These are descriptive statistics of this job's screening scores. They are "
    "not a comparison between candidate groups; see the protected-group "
    "comparison for that."
)

JD_BIAS_NOTE = (
    "These findings describe the job posting itself. The same findings apply to "
    "every applicant to this role and do not vary by candidate."
)

ADVERSARIAL_REASON = (
    "No stored adversarial test result is available for this job. The existing "
    "adversarial engine computes variants on demand and does not persist them, "
    "so opening a screening does not trigger a run. Run it explicitly from the "
    "fairness dashboard when a stability check is wanted."
)

ADVERSARIAL_ENDPOINT = "/api/v1/fairness/adversarial-test"

# Maps the engine's own group-analysis status onto the section availability
# vocabulary used by the response contract. No new status is introduced.
_GROUP_STATUS_TO_SECTION = {
    "available": "available",
    "insufficient_data": "insufficient_data",
    "no_demographic_data": "insufficient_data",
    "no_screening_data": "no_screening_data",
}

_JD_ISSUE_FIELDS = (
    ("gendered_language", "gendered_language"),
    ("age_biased_language", "age_biased_language"),
    ("discriminatory_terms", "discriminatory_terms"),
    ("exclusive_language", "exclusive_language"),
    ("unnecessary_requirements", "unnecessary_requirements"),
)


class ScreeningFairnessContextService:
    """Fairness context for one application, scoped to its job's population."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = FairnessEngine(session)
        self.audit = AuditService(session)
        self.screening_repo = ScreeningResultRepository(session)

    async def get_application_fairness_context(
        self,
        application_id: uuid.UUID,
        actor: User,
        minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
    ) -> dict[str, Any]:
        application = await self._load_application(application_id)
        # Authorization is derived from the application's own job, so there is no
        # job identifier in the path to substitute and no cross-tenant read.
        job = await authorize_job_access(self.session, application.job_id, actor)
        screening = await self._load_screening(application)

        report = await self.engine.get_job_fairness_report(
            job.id, minimum_group_size=minimum_group_size,
        )
        jd_bias = await self._load_jd_bias(job.id)
        application_count = await self._count_applications(job.id)

        projected = self._project(
            application=application,
            job=job,
            screening=screening,
            report=report,
            jd_bias=jd_bias,
            application_count=application_count,
            minimum_group_size=minimum_group_size,
        )
        await self._audit(
            actor=actor, application=application, job=job,
            screening=screening, group_status=report.get("group_fairness", {}).get(
                "metric_status",
            ),
        )
        return projected

    # ── Loading ─────────────────────────────────────────────────────

    async def _load_application(self, application_id: uuid.UUID) -> JobApplication:
        application = (
            await self.session.execute(
                select(JobApplication)
                .where(JobApplication.id == application_id)
                .options(selectinload(JobApplication.candidate))
            )
        ).scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found")
        return application

    async def _load_screening(
        self, application: JobApplication,
    ) -> ScreeningResult | None:
        """The screening result for this application, if one exists.

        Resolved by application id with the legacy ``(job_id, candidate_id)``
        fallback used elsewhere in the screening workflow, so the fairness
        population and the displayed screening result describe the same run.
        """
        by_application = await self.screening_repo.get_by_application(
            application.id,
        )
        if by_application is not None:
            return by_application
        return await self.screening_repo.get_by_job_and_candidate(
            application.job_id, application.candidate_id,
        )

    async def _load_jd_bias(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        """Job-description bias analysis, isolated from the rest of the context.

        JD analysis is a pure function of the job's own text, so a failure in it
        must not cost the recruiter the population metrics. An unexpected error
        degrades to "unavailable" rather than propagating.
        """
        try:
            result = await self.engine.analyze_job_description(job_id)
        except Exception:  # noqa: BLE001 - optional section isolation
            logger.warning("JD bias analysis failed for job %s", job_id, exc_info=True)
            return None
        if "error" in result:
            return None
        return result

    async def _count_applications(self, job_id: uuid.UUID) -> int:
        stmt = select(func.count(JobApplication.id)).where(
            JobApplication.job_id == job_id,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    # ── Projection ──────────────────────────────────────────────────

    def _screening_state(
        self, application: JobApplication, screening: ScreeningResult | None,
    ) -> FairnessScreeningState:
        """Screening state using the workflow's existing precedence rule.

        A stored screening result means the screening completed, whatever the
        application row still records. Mirrors the ``effective_status`` case
        expression used for applicant filtering.
        """
        if screening is not None:
            effective = ScreeningStatus.COMPLETED.value
        else:
            effective = (
                application.screening_status or ScreeningStatus.NOT_STARTED.value
            )
        screened = screening is not None
        if screened:
            message = (
                "This application's screening result is included in the fairness "
                "population below."
            )
        else:
            message = (
                "This application has no screening result, so it does not "
                "contribute to the fairness population below."
            )
        return FairnessScreeningState(
            effective_status=effective,
            screened=screened,
            message=message,
        )

    def _project(
        self,
        *,
        application: JobApplication,
        job: Job,
        screening: ScreeningResult | None,
        report: dict[str, Any],
        jd_bias: dict[str, Any] | None,
        application_count: int,
        minimum_group_size: int,
    ) -> dict[str, Any]:
        group_fairness = report.get("group_fairness") or {}
        screened_count = int(report.get("total_candidates") or 0)
        group_status = group_fairness.get("metric_status", "no_screening_data")

        sections: dict[str, FairnessSection] = {
            "group_analysis": FairnessSection(
                status=_GROUP_STATUS_TO_SECTION.get(group_status, "unavailable"),
                reason=group_fairness.get("status_reason"),
            ),
            "alerts": FairnessSection(
                status="available" if report.get("bias_alerts") else "available",
                reason=(
                    None
                    if report.get("bias_alerts")
                    else "No bias review alerts were raised for this job."
                ),
            ),
            "job_description_bias": FairnessSection(
                status="available" if jd_bias else "unavailable",
                reason=(
                    None
                    if jd_bias
                    else "Job description bias analysis is unavailable for this job."
                ),
            ),
            "adversarial": FairnessSection(
                status="unavailable", reason=ADVERSARIAL_REASON,
            ),
        }

        return ApplicationFairnessContextResponse(
            application=FairnessContextApplication(
                id=str(application.id),
                job_id=str(job.id),
                status=application.status,
                applied_at=(
                    application.created_at.isoformat() if application.created_at else None
                ),
            ),
            job=FairnessContextJob(
                id=str(job.id), title=job.title or "", company=job.company or "",
            ),
            screening_state=self._screening_state(application, screening),
            population=self._population(
                job=job,
                screening=screening,
                application_count=application_count,
                screened_count=screened_count,
            ),
            sections=sections,
            score_distribution=self._score_distribution(report),
            group_analysis=self._group_analysis(group_fairness),
            alerts=[
                FairnessAlertView(
                    type=a.get("type", "unknown"),
                    severity=a.get("severity", "info"),
                    message=a.get("message", ""),
                    recommendation=a.get("recommendation", ""),
                )
                for a in report.get("bias_alerts") or []
            ],
            job_description_bias=self._jd_bias(jd_bias),
            adversarial=AdversarialContextView(
                status="no_stored_result",
                tested=False,
                stability_score=None,
                sensitivity=None,
                reason=ADVERSARIAL_REASON,
                run_on_demand_endpoint=ADVERSARIAL_ENDPOINT,
            ),
            limitations=self._limitations(group_fairness, report),
        ).model_dump()

    def _population(
        self,
        *,
        job: Job,
        screening: ScreeningResult | None,
        application_count: int,
        screened_count: int,
    ) -> FairnessPopulation:
        return FairnessPopulation(
            job_id=str(job.id),
            job_title=job.title or "",
            applications=application_count,
            screened=screened_count,
            unscreened=max(0, application_count - screened_count),
            application_is_in_population=application_count > 0,
            application_screening_included=screening is not None,
            scope=GROUP_METRIC_SCOPE,
            note=POPULATION_NOTE,
        )

    def _score_distribution(
        self, report: dict[str, Any],
    ) -> FairnessScoreDistribution | None:
        distribution = report.get("score_distribution")
        if not distribution or not report.get("total_candidates"):
            return None
        coverage = (report.get("group_fairness") or {}).get("coverage") or {}
        return FairnessScoreDistribution(
            average=distribution.get("average", 0),
            minimum=distribution.get("min", 0),
            maximum=distribution.get("max", 0),
            median=distribution.get("median", 0),
            std_dev=distribution.get("std_dev", 0),
            positive_outcome_threshold=int(
                coverage.get("positive_outcome_threshold", 70)
            ),
            note=SCORE_DISTRIBUTION_NOTE,
        )

    def _group_analysis(
        self, group_fairness: dict[str, Any],
    ) -> FairnessGroupAnalysis | None:
        coverage = group_fairness.get("coverage")
        if not coverage:
            return None
        return FairnessGroupAnalysis(
            metric_status=group_fairness.get("metric_status", "unavailable"),
            status_reason=group_fairness.get("status_reason"),
            reference_group=group_fairness.get("reference_group"),
            coverage=FairnessCoverage(
                group_dimension=coverage.get("group_dimension", "gender"),
                attribute_source=coverage.get("attribute_source", "self_reported"),
                attributes_inferred=bool(coverage.get("attributes_inferred", False)),
                population=coverage.get("population", 0),
                candidates_with_demographic=coverage.get(
                    "candidates_with_demographic", 0,
                ),
                candidates_missing_demographic=coverage.get(
                    "candidates_missing_demographic", 0,
                ),
                demographic_coverage_pct=coverage.get("demographic_coverage_pct", 0.0),
                minimum_group_size=coverage.get("minimum_group_size", 0),
                positive_outcome_threshold=coverage.get(
                    "positive_outcome_threshold", 70,
                ),
            ),
            group_outcomes=[
                FairnessGroupOutcome(
                    group_value=g.get("group_value", "unknown"),
                    sample_size=g.get("sample_size", 0),
                    positive_outcome_count=g.get("positive_outcome_count"),
                    positive_outcome_rate=g.get("positive_outcome_rate"),
                    metric_status=g.get("metric_status", "unknown"),
                    status_reason=g.get("status_reason"),
                )
                for g in group_fairness.get("group_metrics") or []
            ],
            cross_group_metrics=[
                FairnessCrossGroupMetric(
                    metric_name=m.get("metric_name", ""),
                    metric_label=m.get("metric_label", ""),
                    value=m.get("value"),
                    reference_group=m.get("reference_group"),
                    groups_compared=m.get("groups_compared") or [],
                    metric_status=m.get("metric_status", "insufficient_data"),
                    status_reason=m.get("status_reason"),
                )
                for m in group_fairness.get("cross_group_metrics") or []
            ],
            methodology=group_fairness.get("methodology", ""),
            grouping_note=group_fairness.get("grouping_note", ""),
        )

    def _jd_bias(self, jd_bias: dict[str, Any] | None) -> JobDescriptionBiasView | None:
        if not jd_bias:
            return None
        findings: list[FairnessFinding] = []
        issue_counts: dict[str, int] = {}
        for field, category in _JD_ISSUE_FIELDS:
            items = jd_bias.get(field) or []
            issue_counts[field] = len(items)
            for item in items:
                findings.append(
                    FairnessFinding(
                        term=item.get("term", ""),
                        category=category,
                        suggestion=item.get("suggestion", ""),
                    )
                )
        return JobDescriptionBiasView(
            job_id=jd_bias.get("job_id", ""),
            bias_score=int(jd_bias.get("bias_score", 0)),
            overall_assessment=jd_bias.get("overall_assessment", "unknown"),
            total_issues=int(jd_bias.get("total_issues", 0)),
            issue_counts=issue_counts,
            findings=findings,
            suggestions=[
                FairnessSuggestion(
                    category=s.get("category", ""),
                    suggestion=s.get("suggestion", ""),
                    priority=s.get("priority", "info"),
                )
                for s in jd_bias.get("inclusive_suggestions") or []
            ],
            note=JD_BIAS_NOTE,
        )

    def _limitations(
        self, group_fairness: dict[str, Any], report: dict[str, Any],
    ) -> list[str]:
        """Stated limitations, assembled from what was actually observed.

        Every entry is a property of this response, not boilerplate, so a
        recruiter is not told "insufficient data" when the data was sufficient
        or vice versa.
        """
        limitations: list[str] = []
        coverage = group_fairness.get("coverage") or {}
        population = coverage.get("population", 0)
        missing = coverage.get("candidates_missing_demographic", 0)

        if population == 0:
            limitations.append(
                "This job has no screening results, so no fairness population "
                "could be analyzed."
            )
        else:
            if missing:
                limitations.append(
                    f"{missing} of {population} screened candidates have not "
                    "supplied a self-reported gender. They are excluded from "
                    "group comparison rather than assigned a value."
                )
            groups_available = sum(
                1 for g in group_fairness.get("group_metrics") or []
                if g.get("metric_status") == "available"
            )
            if groups_available < 2:
                limitations.append(
                    "Fewer than two demographic groups met the minimum sample "
                    f"size of {coverage.get('minimum_group_size')}, so no "
                    "cross-group metric is reported."
                )
            limitations.append(
                "The screened population is small. A disparity measured over a "
                "small number of candidates can change materially as more "
                "candidates are screened."
            )
        if not (report.get("bias_alerts") or []):
            limitations.append(
                "No bias review alerts were raised for this job."
            )
        limitations.append(
            "No hiring decision has been made for this application. Fairness "
            "analysis describes the screening population and does not evaluate "
            "any individual."
        )
        return limitations

    # ── Audit ──────────────────────────────────────────────────────

    async def _audit(
        self,
        *,
        actor: User,
        application: JobApplication,
        job: Job,
        screening: ScreeningResult | None,
        group_status: str | None,
    ) -> None:
        """Audit the read without recording protected-attribute data.

        Only identifiers, the population size and the analysis status are
        recorded. No group names, counts per group, demographic values, scores
        or alert contents are logged: an audit trail is a privileged store and
        must not become a secondary copy of the fairness data.
        """
        try:
            await self.audit.log(
                event_type=AuditEventType.APPLICATION_FAIRNESS_CONTEXT_VIEWED,
                action="application_fairness_context_viewed",
                user_id=actor.id,
                organization_id=job.organization_id,
                resource_type="job_application",
                resource_id=str(application.id),
                details={
                    "job_id": str(job.id),
                    "candidate_id": str(application.candidate_id),
                    "screening_result_id": (
                        str(screening.id) if screening else None
                    ),
                    "screened": screening is not None,
                    "group_analysis_status": group_status,
                },
            )
        except Exception:  # noqa: BLE001 - auditing must not fail the read
            logger.warning(
                "Failed to audit fairness context for application %s",
                application.id,
            )
