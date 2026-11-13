"""HR organization-level oversight service (Revised Phase 14).

Why this exists
---------------
The audit found that the platform had no HR *oversight* surface. What existed
instead was two unrelated things:

1. ``/dashboard/hr`` in ``api/v1/dashboard.py``, which counts jobs and
   applications with **no organization filter at all** -- an HR user in Org A
   would see Org B's hiring funnel.
2. ``HRAnalyticsService`` in ``services/analytics/hr_analytics.py``, which is
   largely hardcoded placeholder data (fixed department/gender distributions,
   named "Recruiter A/B/C", a fixed 12.0-day time-to-hire) and which also
   derives ``acceptance_rate`` from an average *screening score*, which is not
   an acceptance rate at all.

Neither can back a trustworthy HR screen. This service provides the minimum
real surface the brief asks for, without inventing a parallel data model.

Core rules
----------
- **The organization scope comes from the request user's memberships, never from
  a client-supplied org id.** It reuses ``authorized_job_ids`` from
  ``services/screening/access.py`` -- the same helper the fairness endpoints
  already use for exactly this cross-tenant reason. That helper returns ``None``
  for a platform admin (unrestricted) and a list of job ids otherwise, so
  tenant isolation is one code path, not two.
- **Every row is read through the existing services where one exists.** Job and
  application authorization is delegated to ``authorize_job_access`` and
  ``ApplicationLifecycleService.authorize_staff_access``; the interview,
  assessment, explainability and fairness payloads are the *already-projected*
  outputs of their own services, so HR can never see a field a recruiter could
  not, and cannot drift from the rules those modules enforce.
- **HR is read-only here.** There is no transition, decision, or write method on
  this service. HR oversight is a read projection, so HR cannot bypass the
  recruiter-owned write surface.
- **Sub-payloads degrade to ``None`` rather than raising.** An application with
  no interview, assessment, screening run or fairness cohort still renders; the
  missing piece is simply absent. The only thing that raises is authorization.
- **Real data only.** Every number is a ``COUNT`` over live tables scoped to
  authorized jobs. Nothing is faked, defaulted to a plausible number, or
  back-filled.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.domain.enums import (
    ApplicationStatus,
    AttemptStatus,
    AuditEventType,
    JobStatus,
    ScreeningStatus,
)
from app.domain.hr_oversight_schemas import (
    HRAttentionItem,
    HRAttentionResponse,
    HRCandidateView,
    HRApplicationDetail,
    HRApplicationListResponse,
    HRApplicationSummary,
    HRDecisionView,
    HRFairnessAlert,
    HRHiringQualityResponse,
    HRJobListResponse,
    HRJobSummary,
    HROverviewCounts,
    HROverviewResponse,
    HRQualityCoverage,
    HRRecruiterDetail,
    HRRecruiterListResponse,
    HRRecruiterSummary,
    HRScreeningSummary,
    HRStageDrilldownResponse,
    HRStageJobCount,
    HRTimelineEvent,
    HRInterviewItem,
    HRInterviewListResponse,
)
from app.domain.models import (
    CandidateProfile,
    CandidateSkill,
    ParsedResumeData,
    Resume,
    Skill,
    ApplicationStatusHistory,
    CandidateAssessment,
    Interview,
    InterviewScorecard,
    Job,
    JobApplication,
    OrganizationMembership,
)
from app.domain.enums import MembershipStatus
from app.domain.models import User
from app.repositories.jobs.job import (
    ApplicationStatusHistoryRepository,
    JobApplicationRepository,
)
from app.repositories.membership import OrganizationMembershipRepository
from app.services.applications.application_lifecycle_service import (
    TERMINAL_STATUSES,
    ApplicationLifecycleService,
)
from app.services.assessment.application_assessment_service import (
    ApplicationAssessmentIntegrationService,
)
from app.services.audit_service import AuditService
from app.services.fairness.fairness_engine import FairnessEngine
from app.services.fairness.screening_fairness_context_service import (
    ScreeningFairnessContextService,
)
from app.services.interview.application_interview_service import (
    ApplicationInterviewIntegrationService,
)
from app.services.screening.access import (
    authorized_job_ids,
    authorize_job_access,
)
from app.services.screening.application_explanation_service import (
    ApplicationExplanationService,
)

logger = logging.getLogger(__name__)

# Statuses that mean the application is still live in the funnel. Used for the
# "open applications" count on a job, so HR can tell an active pipeline from a
# finished one without re-deriving the terminal set.
_OPEN_STATUSES = tuple(
    s.value
    for s in ApplicationStatus
    if s not in TERMINAL_STATUSES
)

# Statuses that mean the recruiter has not acted yet: the application is either
# untouched or sitting in early review. ``withdrawn`` is excluded from this set
# on purpose -- a withdrawal is the candidate's action, so counting it as
# "not advanced" would be right, but it is also terminal, so it never appears
# in a live funnel; it is listed explicitly to keep the intent obvious.
_NOT_ADVANCED_STATUSES = frozenset(
    {
        ApplicationStatus.APPLIED.value,
        ApplicationStatus.UNDER_REVIEW.value,
        ApplicationStatus.WITHDRAWN.value,
    }
)

# Frozen set form of the same terminal set, for membership tests in the
# attention rules (a closed application is never "stale").
_TERMINAL_STATUS_VALUES = frozenset(s.value for s in TERMINAL_STATUSES)


class HROversightService:
    """Read-only, organization-scoped HR view over existing application data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.application_repo = JobApplicationRepository(session)
        self.history_repo = ApplicationStatusHistoryRepository(session)
        self.membership_repo = OrganizationMembershipRepository(session)
        self.lifecycle = ApplicationLifecycleService(session)
        self.audit = AuditService(session)
        self.interviews = ApplicationInterviewIntegrationService(session)
        self.assessments = ApplicationAssessmentIntegrationService(session)
        self.explanations = ApplicationExplanationService(session)
        self.fairness = ScreeningFairnessContextService(session)

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------
    async def _scope(
        self, actor: User,
    ) -> tuple[list[uuid.UUID] | None, list[uuid.UUID]]:
        """Return (authorized job ids or None for platform scope, org ids).

        Delegates entirely to the existing ``authorized_job_ids`` helper. The
        org id list is only used to tag the response and to stamp
        ``organization_id`` on audit rows; it is never used to widen access.
        """
        job_ids = await authorized_job_ids(self.session, actor)
        if job_ids is None:
            # Platform admin: unrestricted by design, and the response says so.
            return None, []
        org_ids = list(
            (
                await self.session.execute(
                    select(OrganizationMembership.organization_id).where(
                        OrganizationMembership.user_id == actor.id,
                        OrganizationMembership.status
                        == MembershipStatus.ACTIVE.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        return job_ids, org_ids

    def _scope_filter(self, job_ids: list[uuid.UUID] | None) -> list:
        """A ``WHERE`` fragment restricting a job query to the caller's scope.

        A platform admin gets a literal ``True`` (no restriction). Everyone else
        gets an explicit ``Job.id IN (...)``, and an empty list becomes
        ``IN ()`` -> no rows, which is the safe answer for a user who can read
        no jobs.
        """
        from sqlalchemy import literal

        if job_ids is None:
            return [literal(True)]
        return [Job.id.in_(job_ids)]

    async def _organization_ids_for(
        self, job_ids: list[uuid.UUID] | None,
        scoped_org_ids: list[uuid.UUID] | None = None,
    ) -> list[uuid.UUID]:
        """Report which organizations a response covers.

        For an org-scoped caller this is the active-membership list that
        ``_scope`` already resolved, *not* ``Job.organization_id``. That column
        is nullable and the real job-creation path never sets it (see
        ``app/tools/job_tools.py``), so deriving scope from it would report an
        empty organization list for a user who genuinely belongs to
        organizations -- and the UI would claim "your organizations" while
        showing none.

        The platform case keeps the job-derived list because a platform admin
        has no memberships to read, and the field is only a label there:
        ``is_platform_scope`` is what actually conveys the wider access.
        """
        if job_ids is not None and scoped_org_ids is not None:
            return sorted(set(scoped_org_ids), key=str)
        if job_ids is None:
            rows = (
                await self.session.execute(
                    select(Job.organization_id).where(Job.organization_id.isnot(None))
                )
            ).scalars().all()
        else:
            if not job_ids:
                return []
            rows = (
                await self.session.execute(
                    select(Job.organization_id).where(
                        Job.id.in_(job_ids),
                        Job.organization_id.isnot(None),
                    )
                )
            ).scalars().all()
        return sorted({r for r in rows if r is not None}, key=str)

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------
    async def get_overview(self, actor: User) -> HROverviewResponse:
        """Real, organization-scoped hiring counters.

        Replaces the platform-wide ``/dashboard/hr`` funnel and the hardcoded
        ``/analytics/hr`` distributions with counts over authorized jobs only.
        """
        job_ids, scoped_org_ids = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        job_total = (
            await self.session.execute(
                select(func.count(Job.id)).where(Job.is_archived.is_(False), *scope)
            )
        ).scalar() or 0
        open_positions = (
            await self.session.execute(
                select(func.count(Job.id)).where(
                    Job.is_archived.is_(False),
                    Job.status == JobStatus.PUBLISHED.value,
                    *scope,
                )
            )
        ).scalar() or 0

        status_rows = (
            await self.session.execute(
                select(JobApplication.status, func.count(JobApplication.id))
                .join(Job, Job.id == JobApplication.job_id)
                .where(*scope)
                .group_by(JobApplication.status)
            )
        ).all()
        applications_by_status = {str(row[0]): int(row[1]) for row in status_rows}
        total_applications = sum(applications_by_status.values())

        distinct_candidates = (
            await self.session.execute(
                select(func.count(func.distinct(JobApplication.candidate_id)))
                .join(Job, Job.id == JobApplication.job_id)
                .where(*scope)
            )
        ).scalar() or 0
        distinct_recruiters = (
            await self.session.execute(
                select(func.count(func.distinct(Job.recruiter_id))).where(*scope)
            )
        ).scalar() or 0

        interview_rows = (
            await self.session.execute(
                select(Interview.status, func.count(Interview.id))
                .join(Job, Job.id == Interview.job_id)
                .where(*scope)
                .group_by(Interview.status)
            )
        ).all()
        interviews_by_status = {str(row[0]): int(row[1]) for row in interview_rows}

        assessment_rows = (
            await self.session.execute(
                select(CandidateAssessment.status, func.count(CandidateAssessment.id))
                .join(
                    JobApplication,
                    JobApplication.id == CandidateAssessment.application_id,
                )
                .join(Job, Job.id == JobApplication.job_id)
                .where(*scope)
                .group_by(CandidateAssessment.status)
            )
        ).all()
        assessments_by_status = {str(row[0]): int(row[1]) for row in assessment_rows}

        def _status_count(*values: str) -> int:
            return sum(applications_by_status.get(v, 0) for v in values)

        counts = HROverviewCounts(
            open_positions=int(open_positions),
            total_applications=int(total_applications),
            distinct_candidates=int(distinct_candidates),
            distinct_recruiters=int(distinct_recruiters),
            shortlisted=_status_count(ApplicationStatus.SHORTLISTED.value),
            interview_scheduled=_status_count(
                ApplicationStatus.INTERVIEW_SCHEDULED.value
            ),
            interview_scheduled_total=int(interviews_by_status.get("scheduled", 0)),
            assessments_assigned=int(assessments_by_status.get(AttemptStatus.ASSIGNED.value, 0)),
            assessment_attempts=int(sum(assessments_by_status.values())),
            selected=_status_count(ApplicationStatus.SELECTED.value),
            offered=_status_count(ApplicationStatus.OFFERED.value),
            rejected=_status_count(ApplicationStatus.REJECTED.value),
            hired=_status_count(ApplicationStatus.HIRED.value),
            withdrawn=_status_count(ApplicationStatus.WITHDRAWN.value),
        )

        result = HROverviewResponse(
            organization_ids=await self._organization_ids_for(
                job_ids, scoped_org_ids,
            ),
            is_platform_scope=job_ids is None,
            counts=counts,
            applications_by_status=applications_by_status,
            interviews_by_status=interviews_by_status,
            assessments_by_status=assessments_by_status,
        )
        await self.audit.log(
            event_type=AuditEventType.HR_OVERVIEW_VIEWED,
            action="hr_oversight_overview_viewed",
            user_id=actor.id,
            resource_type="hr_oversight",
            resource_id=None,
            details={
                "is_platform_scope": result.is_platform_scope,
                "total_applications": counts.total_applications,
            },
        )
        return result

    # ------------------------------------------------------------------
    # Jobs + drill-down
    # ------------------------------------------------------------------
    async def list_jobs(self, actor: User) -> HRJobListResponse:
        """Jobs the caller may read, with real per-status application counts.

        One query for the jobs and one grouped count for the funnel, rather than
        a per-job query, so the list does not fan out with the number of jobs.
        """
        job_ids, _ = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        jobs = list(
            (
                await self.session.execute(
                    select(Job)
                    .where(Job.is_archived.is_(False), *scope)
                    .order_by(Job.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        ids = [j.id for j in jobs]
        by_status: dict[uuid.UUID, dict[str, int]] = {}
        if ids:
            rows = (
                await self.session.execute(
                    select(JobApplication.job_id, JobApplication.status,
                           func.count(JobApplication.id))
                    .where(JobApplication.job_id.in_(ids))
                    .group_by(JobApplication.job_id, JobApplication.status)
                )
            ).all()
            for job_id, status, count in rows:
                by_status.setdefault(job_id, {})[str(status)] = int(count)

        recruiter_names = await self._recruiter_names(j.recruiter_id for j in jobs)
        summaries = [
            self._job_summary(
                job,
                by_status.get(job.id, {}),
                recruiter_names.get(job.recruiter_id),
            )
            for job in jobs
        ]
        return HRJobListResponse(
            is_platform_scope=job_ids is None,
            total=len(summaries),
            jobs=summaries,
        )

    async def list_job_applications(
        self, job_id: uuid.UUID, actor: User, status: str | None = None,
    ) -> HRApplicationListResponse:
        """Applications for one job, after a real access check on that job.

        Uses ``authorize_job_access`` rather than trusting the path id, so a
        cross-tenant HR user gets a 403/404 on somebody else's job and cannot
        enumerate applications by guessing ids.

        ``status`` is an optional *exact* funnel-stage filter. It exists so the
        clickable pipeline can drill into the applications behind a single
        stage. An unrecognised status matches nothing rather than silently
        returning the unfiltered list, so a stale link from the UI can never
        show HR a full job pipeline that it labelled as one stage.
        """
        job = await authorize_job_access(self.session, job_id, actor)
        # ``candidate`` is a lazy relationship, and a lazy load during response
        # building raises MissingGreenlet under asyncio. Eager-loading it keeps
        # the projection at one round trip and cannot fail mid-render.
        query = select(JobApplication).options(
            selectinload(JobApplication.candidate)
        ).where(JobApplication.job_id == job.id)
        if status is not None:
            query = query.where(JobApplication.status == status)
        rows = list(
            (
                await self.session.execute(
                    query.order_by(JobApplication.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        interview_ids, assessment_ids = await self._evidence_presence(
            [a.id for a in rows]
        )
        recruiter_names = await self._recruiter_names([job.recruiter_id])
        summaries = [
            await self._application_summary(
                application,
                job,
                recruiter_names.get(job.recruiter_id),
                has_interview=application.id in interview_ids,
                has_assessment=application.id in assessment_ids,
            )
            for application in rows
        ]
        return HRApplicationListResponse(
            job_id=job.id,
            status_filter=status,
            total=len(summaries),
            applications=summaries,
        )

    async def get_application_detail(
        self, application_id: uuid.UUID, actor: User,
    ) -> HRApplicationDetail:
        """The HR drill-down for one application.

        Authorization is delegated to ``ApplicationLifecycleService.authorize_staff_access``
        -- the read-side counterpart of a transition, using the identical rules
        (job owner, or an active org membership in a staff role). It raises
        404 for unknown ids and 403 otherwise, so HR cannot distinguish a
        non-existent application from one in another tenant.

        Each evidence block is then requested from the service that owns it and
        tolerated as absent. If one raises for a legitimate-but-incomplete
        application, that is caught and dropped rather than failing the whole
        drill-down; authorization failures are already handled above and are
        *not* swallowed.
        """
        application, job = await self.lifecycle.authorize_staff_access(
            application_id, actor
        )
        candidate = (
            application.__dict__.get("candidate")
            or await self.session.get(User, application.candidate_id)
        )
        if candidate is None:
            raise NotFoundError("Candidate not found")

        recruiter_name = (await self._recruiter_names([job.recruiter_id])).get(
            job.recruiter_id
        )
        decided_by_name = None
        if application.decided_by:
            decided_by_name = (await self._recruiter_names([application.decided_by])).get(
                application.decided_by
            )

        # Candidate profile, resume & skills projection
        cp_stmt = select(CandidateProfile).where(CandidateProfile.user_id == candidate.id)
        cp_res = await self.session.execute(cp_stmt)
        cp = cp_res.scalar_one_or_none()
        avatar_url = cp.avatar_url if cp else None
        phone = cp.phone if cp else None
        location = cp.location if cp else None
        bio = cp.bio if cp else None
        current_role = cp.current_role if cp else None

        resume_stmt = select(Resume).where(Resume.user_id == candidate.id)
        if application.resume_id:
            resume_stmt = select(Resume).where(Resume.id == application.resume_id)
        resume_res = await self.session.execute(resume_stmt.order_by(Resume.created_at.desc()))
        resume = resume_res.scalars().first()
        resume_filename = resume.original_filename if resume else None
        resume_url = f"/api/v1/hr/applications/{application.id}/resume/download" if resume else None

        skills_set = set()
        experience_years = None
        if resume:
            prd_stmt = select(ParsedResumeData).where(ParsedResumeData.resume_id == resume.id)
            prd_res = await self.session.execute(prd_stmt)
            prd = prd_res.scalars().first()
            if prd:
                if prd.skills:
                    try:
                        import json
                        raw_skills = json.loads(prd.skills) if isinstance(prd.skills, str) else prd.skills
                        if isinstance(raw_skills, list):
                            for s in raw_skills:
                                if isinstance(s, dict):
                                    name = s.get("display_name") or s.get("name")
                                    if name:
                                        skills_set.add(str(name).title())
                                elif isinstance(s, str):
                                    skills_set.add(s.title())
                    except Exception:
                        pass
                if prd.experience:
                    try:
                        import json
                        exp_data = json.loads(prd.experience) if isinstance(prd.experience, str) else prd.experience
                        if isinstance(exp_data, list):
                            experience_years = float(len(exp_data) * 1.5)
                        elif isinstance(exp_data, dict):
                            experience_years = float(exp_data.get("years") or 2.0)
                    except Exception:
                        pass

        if cp:
            cskills_stmt = (
                select(Skill.name)
                .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
                .where(CandidateSkill.profile_id == cp.id)
            )
            cskills_res = await self.session.execute(cskills_stmt)
            for sname in cskills_res.scalars():
                if sname:
                    skills_set.add(str(sname).title())

        skills_list = sorted(list(skills_set)) if skills_set else []

        status_value = str(getattr(application.status, "value", application.status))
        detail = HRApplicationDetail(
            id=application.id,
            status=status_value,
            is_terminal=status_value in {s.value for s in TERMINAL_STATUSES},
            job=self._job_summary(
                job,
                (await self._job_status_counts([job.id])).get(job.id, {}),
                recruiter_name,
            ),
            candidate=HRCandidateView(
                id=candidate.id,
                full_name=candidate.full_name,
                email=candidate.email,
                is_active=candidate.is_active,
                account_status=candidate.account_status,
                has_resume=application.resume_id is not None or resume is not None,
                avatar_url=avatar_url,
                phone=phone,
                location=location,
                resume_url=resume_url,
                resume_filename=resume_filename,
                skills=skills_list,
                experience_years=experience_years,
                bio=bio,
                current_role=current_role,
            ),
            decision=HRDecisionView(
                status=status_value,
                is_terminal=status_value in {s.value for s in TERMINAL_STATUSES},
                decision_reason=application.decision_reason,
                decision_reason_code=application.decision_reason_code,
                decision_comment=application.decision_comment,
                decided_at=application.decided_at,
                decided_by=application.decided_by,
                decided_by_name=decided_by_name,
            ),
            screening=HRScreeningSummary(
                status=application.screening_status,
                attempts=application.screening_attempts or 0,
                started_at=application.screening_started_at,
                completed_at=application.screening_completed_at,
                error=application.screening_error,
            ),
            applied_at=application.created_at,
            cover_letter_available=bool(application.cover_letter),
            explainability=await self._safe(
                self.explanations.get_recruiter_explanation(application.id, actor),
                "explainability",
            ),
            fairness=await self._safe(
                self.fairness.get_application_fairness_context(application.id, actor),
                "fairness",
            ),
            interview=await self._safe(
                self._interview_payload(application.id, actor), "interview",
            ),
            assessment=await self._safe(
                self._assessment_payload(application.id, actor), "assessment",
            ),
            timeline=await self._timeline(application, job, actor),
        )

        await self.audit.log(
            event_type=AuditEventType.HR_APPLICATION_VIEWED,
            action="hr_oversight_application_viewed",
            user_id=actor.id,
            organization_id=job.organization_id,
            resource_type="job_application",
            resource_id=str(application.id),
            details={"job_id": str(job.id), "status": status_value},
        )
        return detail

    # ------------------------------------------------------------------
    # Recruiter (employer) monitoring
    # ------------------------------------------------------------------
    async def list_recruiters(self, actor: User) -> HRRecruiterListResponse:
        """Recruiters the caller may monitor, with their real funnel.

        This is the same authorized job set as ``list_jobs``, rolled up by the
        recruiter who owns each job -- a grouping of rows HR is already allowed
        to read, not a new data source. A recruiter with no readable job in
        scope is simply absent, so the list cannot be used to enumerate the
        platform's users.

        The funnel is computed in two grouped queries (jobs, then applications
        bucketed by recruiter and status) rather than per recruiter, so the
        response cost does not grow with the number of recruiters.
        """
        job_ids, _ = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        jobs = list(
            (
                await self.session.execute(
                    select(Job)
                    .where(Job.is_archived.is_(False), *scope)
                    .order_by(Job.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

        by_recruiter: dict[uuid.UUID, list[Job]] = {}
        for job in jobs:
            by_recruiter.setdefault(job.recruiter_id, []).append(job)

        ids = [j.id for j in jobs]
        funnel: dict[uuid.UUID, dict[str, int]] = {}
        if ids:
            rows = (
                await self.session.execute(
                    select(Job.recruiter_id, JobApplication.status,
                           func.count(JobApplication.id))
                    .join(JobApplication, JobApplication.job_id == Job.id)
                    .where(Job.id.in_(ids))
                    .group_by(Job.recruiter_id, JobApplication.status)
                )
            ).all()
            for recruiter_id, status, count in rows:
                funnel.setdefault(recruiter_id, {})[str(status)] = int(count)

        recruiters = list(
            (
                await self.session.execute(
                    select(User).where(
                        User.id.in_(list(by_recruiter) or [uuid.uuid4()])
                    )
                )
            )
            .scalars()
            .all()
        )
        users = {u.id: u for u in recruiters}

        summaries = []
        for recruiter_id, owned in by_recruiter.items():
            user = users.get(recruiter_id)
            summaries.append(
                self._recruiter_summary(user, recruiter_id, owned, funnel.get(recruiter_id, {}))
            )
        # Deterministic ordering: most applications first, then a stable name
        # tiebreak so two identical requests always return the same order.
        summaries.sort(key=lambda s: (-s.application_count, (s.full_name or "").lower()))

        return HRRecruiterListResponse(
            is_platform_scope=job_ids is None,
            total=len(summaries),
            recruiters=summaries,
        )

    async def get_recruiter_detail(
        self, recruiter_id: uuid.UUID, actor: User,
    ) -> HRRecruiterDetail:
        """One recruiter plus the jobs behind their aggregate.

        Scope is proven the same way as the list: the recruiter is only
        resolvable if they own at least one job inside the caller's authorized
        set. A recruiter outside that set raises, so id enumeration cannot be
        used to confirm that a user id exists elsewhere.
        """
        job_ids, _ = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        owned = list(
            (
                await self.session.execute(
                    select(Job)
                    .where(
                        Job.recruiter_id == recruiter_id,
                        Job.is_archived.is_(False),
                        *scope,
                    )
                    .order_by(Job.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        if not owned:
            # Same 404/403 translation the other HR routes use, so an
            # out-of-scope recruiter is indistinguishable from an unknown one.
            raise NotFoundError("Recruiter not found in your organization scope")

        user = await self.session.get(User, recruiter_id)
        status_counts = await self._job_status_counts([j.id for j in owned])
        funnel: dict[str, int] = {}
        for counts in status_counts.values():
            for status, count in counts.items():
                funnel[status] = funnel.get(status, 0) + count

        return HRRecruiterDetail(
            recruiter=self._recruiter_summary(
                user, recruiter_id, owned, funnel,
            ),
            jobs=[
                self._job_summary(
                    job,
                    status_counts.get(job.id, {}),
                    user.full_name if user else None,
                )
                for job in owned
            ],
        )

    def _recruiter_summary(
        self,
        user: User | None,
        recruiter_id: uuid.UUID,
        owned: list[Job],
        funnel: dict[str, int],
    ) -> HRRecruiterSummary:
        """Fold a recruiter's jobs into one row.

        ``advancement_rate`` is the share of applications the recruiter actually
        acted on -- any status other than the untouched ``applied``/
        ``under_review`` states, excluding ``withdrawn`` (a candidate action,
        not a recruiter outcome). It is ``None`` rather than ``0.0`` when there
        are no applications, so the UI can distinguish "no data" from "no
        progress". A rejected application counts as advanced: the recruiter
        reached a decision, which is what this metric measures.
        """
        total = sum(funnel.values())
        advanced = sum(
            count
            for status, count in funnel.items()
            if status not in _NOT_ADVANCED_STATUSES
        )
        rate = round(advanced / total, 4) if total else None
        return HRRecruiterSummary(
            id=recruiter_id,
            full_name=user.full_name if user else "Unknown recruiter",
            email=user.email if user else None,
            is_active=bool(user.is_active) if user else True,
            total_job_count=len(owned),
            open_job_count=sum(
                1
                for j in owned
                if str(getattr(j.status, "value", j.status)) == JobStatus.PUBLISHED.value
            ),
            application_count=total,
            open_application_count=sum(
                count for status, count in funnel.items() if status in _OPEN_STATUSES
            ),
            applications_by_status=funnel,
            hired_count=funnel.get(ApplicationStatus.HIRED.value, 0),
            advancement_rate=rate,
            job_ids=[j.id for j in owned],
        )

    # ------------------------------------------------------------------
    # Funnel-stage drill-down
    # ------------------------------------------------------------------
    async def get_stage_drilldown(
        self, status: str, actor: User,
    ) -> HRStageDrilldownResponse:
        """Which jobs actually hold the applications in one funnel stage.

        The overview funnel is organization-wide, so clicking one bar cannot
        sensibly list every matching application: a stage like ``applied`` can
        hold thousands of rows spread across jobs. This answers the question
        HR actually has -- "where is this stage?" -- by grouping the stage by
        job in a single aggregate query, and each returned job is a link to the
        stage-filtered application list.

        An unrecognised status returns zero rows rather than every application,
        so a stale or hand-edited link cannot quietly become a full pipeline.
        """
        job_ids, _ = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        rows = (
            await self.session.execute(
                select(
                    Job.id,
                    Job.title,
                    Job.recruiter_id,
                    func.count(JobApplication.id),
                )
                .join(JobApplication, JobApplication.job_id == Job.id)
                .where(JobApplication.status == status, *scope)
                .group_by(Job.id, Job.title, Job.recruiter_id)
                .order_by(func.count(JobApplication.id).desc(), Job.title)
            )
        ).all()

        recruiter_names = await self._recruiter_names(row[2] for row in rows)
        jobs = [
            HRStageJobCount(
                job_id=row[0],
                job_title=row[1],
                recruiter_id=row[2],
                recruiter_name=recruiter_names.get(row[2]),
                count=int(row[3]),
            )
            for row in rows
        ]
        return HRStageDrilldownResponse(
            status=status,
            total=sum(job.count for job in jobs),
            jobs=jobs,
        )

    # ------------------------------------------------------------------
    # Attention center
    # ------------------------------------------------------------------
    async def list_attention(self, actor: User) -> HRAttentionResponse:
        """Deterministic "needs a human look" items, scoped like everything else.

        Every rule here is a *measurement* against a threshold from
        ``Settings`` -- never a recommendation about a candidate and never a
        state change. A flagged row means "a human should look at this"; the
        recruiter-owned write surface remains the only way to act.

        The rules, in the order they are applied:

        1. ``screening_failed`` -- screening recorded a failure for an
           application. This is the one rule that is a data-quality fact rather
           than a pace measurement.
        2. ``stale_application`` -- an application still in a live status whose
           last recorded status change is older than
           ``hr_attention_stale_application_days``. "Last change" is the newest
           ``ApplicationStatusHistory.changed_at``, falling back to the
           application's own ``created_at`` when no history row exists, so an
           application that was never transitioned is still measured from the
           day it arrived.
        3. ``low_advancement`` -- a recruiter with at least
           ``hr_attention_min_pipeline_apps`` applications advancing fewer than
           ``hr_attention_min_advancement_rate`` of them.
        4. ``fairness_gap`` -- the platform fairness engine's org-scoped
           disparate impact ratio below ``hr_attention_fairness_gap``.

        Ordering is total and stable (severity, then rule, then subject id), so
        the same data always yields the same list -- a screen that reshuffles
        itself between refreshes cannot be acted on.
        """
        settings = get_settings()
        job_ids, _ = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        items: list[HRAttentionItem] = []

        # --- application-level rules -------------------------------------
        applications = list(
            (
                await self.session.execute(
                    select(JobApplication, Job)
                    .join(Job, Job.id == JobApplication.job_id)
                    .where(*scope)
                )
            )
            .all()
        )
        recruiter_names = await self._recruiter_names(
            job.recruiter_id for _, job in applications
        )

        last_change: dict[uuid.UUID, datetime] = {}
        if applications:
            history_rows = (
                await self.session.execute(
                    select(
                        ApplicationStatusHistory.application_id,
                        func.max(ApplicationStatusHistory.changed_at),
                    )
                    .where(
                        ApplicationStatusHistory.application_id.in_(
                            [a.id for a, _ in applications]
                        )
                    )
                    .group_by(ApplicationStatusHistory.application_id)
                )
            ).all()
            last_change = {row[0]: row[1] for row in history_rows}

        now = datetime.now(timezone.utc)
        stale_cutoff_days = settings.hr_attention_stale_application_days

        for application, job in applications:
            status_value = str(
                getattr(application.status, "value", application.status)
            )
            if application.screening_status == ScreeningStatus.FAILED.value:
                items.append(
                    HRAttentionItem(
                        rule="screening_failed",
                        severity="critical",
                        reason="Screening failed for this application",
                        subject_type="application",
                        subject_id=application.id,
                        application_id=application.id,
                        job_id=job.id,
                        job_title=job.title,
                        recruiter_id=job.recruiter_id,
                        recruiter_name=recruiter_names.get(job.recruiter_id),
                        status=status_value,
                    )
                )

            # Only live applications can be "stalled" -- a closed one is not
            # waiting on anybody.
            if status_value not in _TERMINAL_STATUS_VALUES:
                seen = last_change.get(application.id) or application.created_at
                idle_days = self._idle_days(seen, now)
                if idle_days is not None and idle_days >= stale_cutoff_days:
                    items.append(
                        HRAttentionItem(
                            rule="stale_application",
                            severity="warning",
                            reason=(
                                f"No status change for {idle_days} days in "
                                f"status {status_value}"
                            ),
                            subject_type="application",
                            subject_id=application.id,
                            application_id=application.id,
                            job_id=job.id,
                            job_title=job.title,
                            recruiter_id=job.recruiter_id,
                            recruiter_name=recruiter_names.get(job.recruiter_id),
                            status=status_value,
                            measured_value=float(idle_days),
                            threshold_value=float(stale_cutoff_days),
                        )
                    )

        # --- recruiter-level rule ----------------------------------------
        for summary in (await self.list_recruiters(actor)).recruiters:
            if summary.advancement_rate is None:
                continue
            if (
                summary.application_count < settings.hr_attention_min_pipeline_apps
                or summary.advancement_rate >= settings.hr_attention_min_advancement_rate
            ):
                continue
            items.append(
                HRAttentionItem(
                    rule="low_advancement",
                    severity="warning",
                    reason=(
                        f"{summary.application_count} applications, "
                        f"{int(summary.advancement_rate * 100)}% advanced"
                    ),
                    subject_type="recruiter",
                    subject_id=summary.id,
                    recruiter_id=summary.id,
                    recruiter_name=summary.full_name,
                    measured_value=float(summary.advancement_rate),
                    threshold_value=float(settings.hr_attention_min_advancement_rate),
                )
            )

        # --- organization-level fairness rule ----------------------------
        items.extend(
            await self._fairness_attention_items(
                job_ids, settings.hr_attention_fairness_gap
            )
        )

        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        items.sort(
            key=lambda i: (
                severity_rank.get(i.severity, 99),
                i.rule,
                str(i.subject_id or ""),
            )
        )

        total_flagged = len(items)
        capped = items[: settings.hr_attention_max_items]
        return HRAttentionResponse(
            is_platform_scope=job_ids is None,
            thresholds={
                "stale_application_days": float(stale_cutoff_days),
                "min_advancement_rate": float(
                    settings.hr_attention_min_advancement_rate
                ),
                "min_pipeline_applications": float(
                    settings.hr_attention_min_pipeline_apps
                ),
                "fairness_gap": float(settings.hr_attention_fairness_gap),
            },
            total_flagged=total_flagged,
            items=capped,
            truncated=total_flagged > len(capped),
        )

    async def _fairness_attention_items(
        self,
        job_ids: list[uuid.UUID] | None,
        threshold: float,
    ) -> list[HRAttentionItem]:
        """Turn the platform fairness engine's org metric into an attention item.

        Delegates the arithmetic to ``FairnessEngine`` rather than recomputing a
        parity statistic here, so HR sees exactly the number the fairness
        screens already show. A platform with no screening results has no ratio
        to report, and that is surfaced as "no data" rather than as a 0.0 that
        would look like total bias.
        """
        try:
            metrics = await FairnessEngine(self.session).get_fairness_metrics(job_ids)
        except Exception:  # pragma: no cover - engine is best-effort context
            logger.warning("fairness metrics unavailable for HR attention", exc_info=True)
            return []

        ratio = (metrics.get("disparate_impact_ratio") or {}).get("value")
        # data_points == 0 means nothing was screened, so the ratio is not a
        # measurement at all.
        if ratio is None or not metrics.get("data_points"):
            return []
        if ratio >= threshold:
            return []
        return [
            HRAttentionItem(
                rule="fairness_gap",
                severity="critical",
                reason=(
                    f"Disparate impact ratio {ratio} is below the "
                    f"{threshold} review threshold"
                ),
                subject_type="organization",
                subject_id=None,
                measured_value=float(ratio),
                threshold_value=float(threshold),
            )
        ]

    @staticmethod
    def _idle_days(seen: datetime | None, now: datetime) -> int | None:
        """Whole days between ``seen`` and ``now``, or None if unknowable.

        The platform stores timestamps both timezone-aware and naive depending
        on the column, so both sides are normalized to naive UTC before the
        subtraction rather than letting a mismatch raise mid-request.
        """
        if seen is None:
            return None
        if seen.tzinfo is not None:
            seen = seen.astimezone(timezone.utc).replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        delta = now - seen
        if delta.total_seconds() < 0:
            # A timestamp in the future (clock skew, or a row written by a
            # process with a different clock) is not stale; report nothing
            # rather than a negative age.
            return None
        return delta.days

    # ------------------------------------------------------------------
    # Hiring quality
    # ------------------------------------------------------------------
    async def get_hiring_quality(self, actor: User) -> HRHiringQualityResponse:
        """How much real quality evidence the organization actually has.

        This reports *coverage* of the existing screening / interview /
        decision / hire signals, plus the fairness alerts the platform engine
        already produces. It deliberately does not invent a composite "hiring
        quality score": screening fairness and explainability own those
        judgments, and a number assembled here would imply an authority this
        service does not have.
        """
        settings = get_settings()
        job_ids, scoped_org_ids = await self._scope(actor)
        scope = self._scope_filter(job_ids)

        screening_by_status: dict[str, int] = {}
        if job_ids != []:
            rows = (
                await self.session.execute(
                    select(JobApplication.screening_status,
                           func.count(JobApplication.id))
                    .join(Job, Job.id == JobApplication.job_id)
                    .where(*scope)
                    .group_by(JobApplication.screening_status)
                )
            ).all()
            screening_by_status = {str(r[0]): int(r[1]) for r in rows}

        status_rows = (
            await self.session.execute(
                select(JobApplication.status, func.count(JobApplication.id))
                .join(Job, Job.id == JobApplication.job_id)
                .where(*scope)
                .group_by(JobApplication.status)
            )
        ).all()
        by_status = {str(r[0]): int(r[1]) for r in status_rows}
        total = sum(by_status.values())

        def _share(*statuses: str) -> float | None:
            hit = sum(by_status.get(s, 0) for s in statuses)
            return round(hit / total, 4) if total else None

        screened = screening_by_status.get(ScreeningStatus.COMPLETED.value, 0)
        alerts: list[HRFairnessAlert] = []

        try:
            metrics = await FairnessEngine(self.session).get_fairness_metrics(job_ids)
            ratio = (metrics.get("disparate_impact_ratio") or {}).get("value")
            if ratio is not None and metrics.get("data_points"):
                if ratio < settings.hr_attention_fairness_gap:
                    alerts.append(
                        HRFairnessAlert(
                            metric="disparate_impact_ratio",
                            observed_value=float(ratio),
                            threshold_value=float(settings.hr_attention_fairness_gap),
                            detail=(
                                "Organization-wide selection parity ratio is below "
                                "the configured review threshold."
                            ),
                        )
                    )
        except Exception:  # pragma: no cover - engine is best-effort context
            logger.warning("fairness metrics unavailable for HR quality", exc_info=True)

        return HRHiringQualityResponse(
            is_platform_scope=job_ids is None,
            organization_ids=await self._organization_ids_for(
                job_ids, scoped_org_ids,
            ),
            coverage=HRQualityCoverage(
                total_applications=total,
                screening_by_status=screening_by_status,
                screening_rate=round(screened / total, 4) if total else None,
                interview_rate=_share(
                    ApplicationStatus.INTERVIEW_SCHEDULED.value,
                    ApplicationStatus.INTERVIEWED.value,
                    ApplicationStatus.SELECTED.value,
                    ApplicationStatus.OFFERED.value,
                    ApplicationStatus.HIRED.value,
                ),
                decision_rate=_share(
                    ApplicationStatus.REJECTED.value,
                    ApplicationStatus.SELECTED.value,
                    ApplicationStatus.OFFERED.value,
                    ApplicationStatus.HIRED.value,
                ),
                hire_rate=_share(ApplicationStatus.HIRED.value),
            ),
            fairness_alerts=alerts,
            fairness_gap_threshold=float(settings.hr_attention_fairness_gap),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _safe(self, awaitable, label: str) -> Any:
        """Await an optional evidence source, tolerating a legitimate failure.

        Only non-authorization problems are absorbed: an application with no
        screening run, no interview, or a fairness cohort too small to report
        must still render its HR drill-down. Authorization has already been
        proven by ``authorize_staff_access`` above, so anything that still
        raises here is missing/partial data for an application the caller is
        already entitled to see, and the honest result is "this section is not
        available" -- not a 500 for the whole page.
        """
        try:
            return await awaitable
        except (NotFoundError, ForbiddenError):
            # Should be unreachable post-authorization; surface it rather than
            # silently degrading a read the caller was entitled to.
            raise
        except Exception as exc:  # noqa: BLE001 - deliberately broad
            logger.info(
                "HR oversight: %s unavailable for application %s: %s",
                label, getattr(awaitable, "__class__", type(awaitable)), exc,
            )
            return None

    async def _recruiter_names(
        self, user_ids,
    ) -> dict[uuid.UUID, str]:
        ids = {u for u in user_ids if u}
        if not ids:
            return {}
        rows = (
            await self.session.execute(
                select(User.id, User.full_name).where(User.id.in_(ids))
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _job_status_counts(
        self, job_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, int]]:
        if not job_ids:
            return {}
        rows = (
            await self.session.execute(
                select(JobApplication.job_id, JobApplication.status,
                       func.count(JobApplication.id))
                .where(JobApplication.job_id.in_(job_ids))
                .group_by(JobApplication.job_id, JobApplication.status)
            )
        ).all()
        out: dict[uuid.UUID, dict[str, int]] = {}
        for job_id, status, count in rows:
            out.setdefault(job_id, {})[str(status)] = int(count)
        return out

    async def _evidence_presence(
        self, application_ids: list[uuid.UUID],
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        if not application_ids:
            return set(), set()
        interview_ids = set(
            (
                await self.session.execute(
                    select(Interview.application_id).where(
                        Interview.application_id.in_(application_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        assessment_ids = set(
            (
                await self.session.execute(
                    select(CandidateAssessment.application_id).where(
                        CandidateAssessment.application_id.in_(application_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        return interview_ids, assessment_ids

    def _job_summary(
        self, job: Job, status_counts: dict[str, int], recruiter_name: str | None,
    ) -> HRJobSummary:
        status_value = str(getattr(job.status, "value", job.status))
        return HRJobSummary(
            id=job.id,
            title=job.title,
            company=job.company,
            description=job.description,
            department=job.department,
            location=job.location,
            status=status_value,
            organization_id=job.organization_id,
            recruiter_id=job.recruiter_id,
            recruiter_name=recruiter_name,
            created_at=job.created_at,
            application_count=sum(status_counts.values()),
            applications_by_status=status_counts,
            hired_count=status_counts.get(ApplicationStatus.HIRED.value, 0),
            open_application_count=sum(
                count
                for status, count in status_counts.items()
                if status in _OPEN_STATUSES
            ),
        )

    async def _application_summary(
        self, application: JobApplication, job: Job, recruiter_name: str | None,
        *, has_interview: bool, has_assessment: bool,
    ) -> HRApplicationSummary:
        candidate = (
            application.__dict__.get("candidate")
            or await self.session.get(User, application.candidate_id)
        )
        status_value = str(getattr(application.status, "value", application.status))
        return HRApplicationSummary(
            id=application.id,
            job_id=job.id,
            job_title=job.title,
            candidate_id=application.candidate_id,
            candidate_name=candidate.full_name if candidate else "Unknown",
            status=status_value,
            is_terminal=status_value in {s.value for s in TERMINAL_STATUSES},
            screening_status=application.screening_status,
            applied_at=application.created_at,
            decided_at=application.decided_at,
            decided_by=application.decided_by,
            recruiter_id=job.recruiter_id,
            recruiter_name=recruiter_name,
            has_interview=has_interview,
            has_assessment=has_assessment,
        )

    async def _interview_payload(
        self, application_id: uuid.UUID, actor: User,
    ) -> dict | None:
        """Reuse the interview service's own staff projection.

        ``get_evidence`` performs its own staff authorization against the same
        rules, so the payload HR renders is byte-for-byte the payload a
        recruiter for the same job would see -- including the candidate-safe
        redaction that service already applies.
        """
        evidence = await self.interviews.get_evidence(application_id, actor)
        return evidence.model_dump(mode="json") if evidence else None

    async def _assessment_payload(
        self, application_id: uuid.UUID, actor: User,
    ) -> dict | None:
        """Reuse the assessment service's own staff projection."""
        evidence = await self.assessments.get_evidence(application_id, actor)
        return evidence.model_dump(mode="json") if evidence else None

    async def _timeline(
        self, application: JobApplication, job: Job, actor: User,
    ) -> list[HRTimelineEvent]:
        """Compose the timeline from rows that already exist.

        Sources, in chronological merge order:
        - ``application_status_history`` (every lifecycle transition, from the
          application creation record onward);
        - the application-linked interview record;
        - the application-linked assessment attempt records.

        Nothing is synthesized. If a source has no rows, it contributes no
        events rather than a placeholder.
        """
        events: list[HRTimelineEvent] = []

        history = await self.history_repo.list_by_application(application.id)
        actor_ids = [h.changed_by for h in history if h.changed_by]
        names = await self._recruiter_names(actor_ids)
        for record in history:
            events.append(
                HRTimelineEvent(
                    id=record.id,
                    source="status_history",
                    event="status_changed",
                    at=record.changed_at,
                    from_status=record.from_status,
                    to_status=record.to_status,
                    actor_id=record.changed_by,
                    actor_name=names.get(record.changed_by) if record.changed_by else None,
                    detail=record.reason or record.comment,
                )
            )

        interviews = list(
            (
                await self.session.execute(
                    select(Interview)
                    .where(Interview.application_id == application.id)
                    .order_by(Interview.scheduled_at.asc())
                )
            )
            .scalars()
            .all()
        )
        interview_actor_ids = [i.recruiter_id for i in interviews if i.recruiter_id]
        interview_names = await self._recruiter_names(interview_actor_ids)
        for interview in interviews:
            status = str(getattr(interview.status, "value", interview.status))
            events.append(
                HRTimelineEvent(
                    id=interview.id,
                    source="interview",
                    event=f"interview_{status}",
                    at=interview.scheduled_at or interview.created_at,
                    to_status=status,
                    actor_id=interview.recruiter_id,
                    actor_name=(
                        interview_names.get(interview.recruiter_id)
                        if interview.recruiter_id
                        else None
                    ),
                    detail=str(
                        getattr(interview.interview_type, "value", interview.interview_type)
                    ),
                )
            )

        attempts = list(
            (
                await self.session.execute(
                    select(CandidateAssessment)
                    .where(CandidateAssessment.application_id == application.id)
                    .order_by(CandidateAssessment.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for attempt in attempts:
            status = str(getattr(attempt.status, "value", attempt.status))
            events.append(
                HRTimelineEvent(
                    id=attempt.id,
                    source="assessment",
                    event=f"assessment_{status}",
                    at=attempt.created_at,
                    to_status=status,
                    detail=(
                        f"Attempt {attempt.attempt_number}"
                        if attempt.attempt_number
                        else None
                    ),
                )
            )

        events.sort(key=lambda e: (e.at is None, e.at or datetime.min, str(e.id)))
        return events

    async def list_hr_interviews(
        self, actor: User,
    ) -> HRInterviewListResponse:
        """List candidates who are in the HR interview pipeline or have HR interviews."""
        job_ids, org_ids = await self._scope(actor)
        if job_ids is not None and not job_ids:
            return HRInterviewListResponse(items=[], total=0)

        app_query = (
            select(JobApplication, Job, User)
            .join(Job, JobApplication.job_id == Job.id)
            .join(User, JobApplication.candidate_id == User.id)
        )
        if job_ids is not None:
            app_query = app_query.where(Job.id.in_(job_ids))

        app_rows = (await self.session.execute(app_query)).all()

        items: list[HRInterviewItem] = []
        for app, job, candidate in app_rows:
            iv_res = await self.session.execute(
                select(Interview)
                .where(Interview.application_id == app.id)
                .order_by(Interview.created_at.asc())
            )
            interviews = iv_res.scalars().all()

            # Only candidates advanced to HR stage by recruiters reach the HR page
            if app.advanced_to_hr_at is None:
                continue

            recruiter_iv = next((iv for iv in reversed(interviews) if iv.stage == "recruiter"), None)
            recruiter_sc = None
            if recruiter_iv:
                sc_res = await self.session.execute(
                    select(InterviewScorecard).where(InterviewScorecard.interview_id == recruiter_iv.id)
                )
                recruiter_sc = sc_res.scalar_one_or_none()

            hr_iv = next((iv for iv in reversed(interviews) if iv.stage == "hr"), None)
            hr_sc = None
            interviewer_name = None
            if hr_iv:
                sc_res = await self.session.execute(
                    select(InterviewScorecard).where(InterviewScorecard.interview_id == hr_iv.id)
                )
                hr_sc = sc_res.scalar_one_or_none()
                if hr_iv.recruiter_id:
                    int_user = await self.session.get(User, hr_iv.recruiter_id)
                    interviewer_name = int_user.full_name if int_user else None

            rec_user_name = None
            if job.recruiter_id:
                rec_user = await self.session.get(User, job.recruiter_id)
                rec_user_name = rec_user.full_name if rec_user else None
            elif recruiter_iv and recruiter_iv.recruiter_id:
                rec_user = await self.session.get(User, recruiter_iv.recruiter_id)
                rec_user_name = rec_user.full_name if rec_user else None

            org_name = None
            if job.organization_id:
                from app.domain.models import Organization
                org = await self.session.get(Organization, job.organization_id)
                org_name = org.name if org else None

            status_str = hr_iv.status if hr_iv else "pending_schedule"
            app_status = str(getattr(app.status, "value", app.status))
            is_terminal = app_status in {s.value for s in TERMINAL_STATUSES}

            cand_cp_res = await self.session.execute(
                select(CandidateProfile.avatar_url).where(CandidateProfile.user_id == candidate.id)
            )
            candidate_avatar_url = cand_cp_res.scalar_one_or_none()

            items.append(
                HRInterviewItem(
                    id=hr_iv.id if hr_iv else None,
                    application_id=app.id,
                    candidate_id=candidate.id,
                    candidate_name=candidate.full_name,
                    candidate_email=candidate.email,
                    job_id=job.id,
                    job_title=job.title,
                    organization_id=job.organization_id,
                    organization_name=org_name or job.company,
                    stage="hr",
                    status=status_str,
                    scheduled_at=hr_iv.scheduled_at if hr_iv else None,
                    duration_minutes=hr_iv.duration_minutes if hr_iv else None,
                    room_id=hr_iv.room_id if hr_iv else None,
                    interviewer_id=hr_iv.recruiter_id if hr_iv else None,
                    interviewer_name=interviewer_name,
                    recruiter_name=rec_user_name,
                    recruiter_score=recruiter_sc.overall_score if recruiter_sc else None,
                    recruiter_recommendation=recruiter_sc.recommendation if recruiter_sc else None,
                    recruiter_notes=recruiter_sc.recruiter_notes if recruiter_sc else None,
                    hr_score=hr_sc.overall_score if hr_sc else None,
                    hr_recommendation=hr_sc.recommendation if hr_sc else None,
                    hr_notes=hr_sc.recruiter_notes if hr_sc else None,
                    application_status=app_status,
                    advanced_to_hr_at=app.advanced_to_hr_at,
                    candidate_avatar_url=candidate_avatar_url,
                    is_terminal=is_terminal,
                )
            )

        items.sort(
            key=lambda x: (
                0 if x.status in ("in_progress", "scheduled") else 1,
                x.scheduled_at or datetime.max.replace(tzinfo=timezone.utc),
            )
        )
        return HRInterviewListResponse(items=items, total=len(items))

    async def request_additional_interview(
        self, application_id: uuid.UUID, body: dict, actor: User
    ) -> dict:
        """Schedule or request an additional HR interview evaluation round."""
        from app.core.exceptions import ConflictError
        application, job = await self.lifecycle.authorize_staff_access(
            application_id, actor
        )
        active = await self.interviews.interview_repo.get_active_by_application(application_id)
        if active is not None:
            raise ConflictError(
                "This application already has an interview that is scheduled or in progress",
                extra={"application_id": str(application_id), "interview_id": str(active.id)},
            )

        scheduled_at = None
        if body.get("scheduled_at"):
            try:
                from datetime import datetime
                scheduled_at = datetime.fromisoformat(str(body["scheduled_at"]).replace("Z", "+00:00"))
            except Exception:
                scheduled_at = datetime.now(timezone.utc)
        else:
            scheduled_at = datetime.now(timezone.utc)

        iv_id = uuid.uuid4()
        new_interview = Interview(
            id=iv_id,
            application_id=application_id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            recruiter_id=actor.id,
            stage="hr",
            status="scheduled",
            scheduled_at=scheduled_at,
            duration_minutes=int(body.get("duration_minutes") or 45),
            room_id=f"room_{iv_id.hex[:12]}",
            notes=str(body.get("notes") or "Additional HR interview evaluation round requested."),
        )
        self.session.add(new_interview)
        await self.session.commit()

        return {
            "success": True,
            "interview_id": str(new_interview.id),
            "status": "scheduled",
            "room_id": new_interview.room_id,
            "scheduled_at": new_interview.scheduled_at.isoformat() if new_interview.scheduled_at else None,
            "message": "Additional HR interview scheduled successfully.",
        }
