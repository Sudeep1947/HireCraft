"""HR organization-level oversight endpoints (Revised Phase 14).

This is the read-only HR surface: an overview, a job list, the applications
behind each job, and a single application drill-down. It is deliberately
*advisory*. There is no transition, decision, interview or assessment write
endpoint here, so HR oversight cannot become a second, less-guarded way to
change hiring state.

Authorization notes:
- Every route is gated by ``require_role`` with the HR role set. The *object*
  check then happens inside ``HROversightService``, which derives the tenant
  from the caller's memberships and reuses the platform's existing
  ``authorized_job_ids`` / ``authorize_job_access`` /
  ``authorize_staff_access`` helpers. Client-supplied organization ids are
  never accepted, so one tenant cannot request another's data.
- Unknown ids return 404 and out-of-scope ids return 403, via the shared
  ``NotFoundError`` / ``ForbiddenError`` handlers, so HR cannot probe another
  organization's application space by id enumeration.
- ``hr_manager`` and ``organization_admin`` are accepted alongside ``hr`` and
  ``recruiter`` because the frontend already groups those under the HR role
  set; the scope check in the service is what actually decides the data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.domain.application_decision_schemas import (
    ApplicationDecisionCreate,
    ApplicationDecisionResult,
)
from app.services.applications.application_decision_service import ApplicationDecisionService
from app.services.applications.application_decision_notification import queue_decision_notification
from app.services.interview.application_interview_notification import queue_staff_application_notification
from app.domain.hr_oversight_schemas import (
    HRInterviewListResponse,
    HRApplicationDetail,
    HRApplicationListResponse,
    HRAttentionResponse,
    HRHiringQualityResponse,
    HRJobListResponse,
    HRRecruiterDetail,
    HRRecruiterListResponse,
    HROverviewResponse,
    HRStageDrilldownResponse,
)
from app.domain.models import User
from app.services.hr.hr_oversight_service import HROversightService
from app.services.screening.access import (
    JobAccessDeniedError,
    JobNotFoundError,
)

router = APIRouter(prefix="/hr", tags=["hr-oversight"])

# The role set the HR nav already assumes. Object-level tenant scoping is
# enforced by the service; this is only the coarse gate.
HR_OVERSIGHT_ROLES = ("hr", "hr_manager", "organization_admin", "admin")


def _get_service(
    db: AsyncSession = Depends(get_db),
) -> HROversightService:
    return HROversightService(db)


@router.get("/overview", response_model=HROverviewResponse)
async def get_hr_overview(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Real, organization-scoped hiring counters for the HR overview.

    Replaces the platform-wide ``/dashboard/hr`` funnel as the source of truth
    for HR numbers: every counter is a live aggregate over the jobs the caller
    is entitled to read, and ``is_platform_scope`` states plainly whether the
    numbers are org-scoped or cross-tenant (platform admin only).
    """
    return await service.get_overview(current_user)


@router.get("/jobs", response_model=HRJobListResponse)
async def list_hr_jobs(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Jobs the caller may read, with their real application funnel.

    This is the HR drill-down entry point: each summary carries its recruiter
    and per-status application counts, so the UI can move from overview to a
    specific job's pipeline without a second round of per-row requests.
    """
    return await service.list_jobs(current_user)


@router.get("/jobs/{job_id}/applications", response_model=HRApplicationListResponse)
async def list_hr_job_applications(
    job_id: uuid.UUID,
    status: str | None = None,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Applications for one job, after an access check on that job.

    Access is checked against the job in the path (not trusted from the
    request), so a cross-tenant HR user is refused rather than shown an empty
    list, and cannot enumerate applications by guessing ids.

    ``status`` narrows to a single funnel stage so the clickable pipeline can
    drill into the rows behind one bar. It is passed straight to the service,
    which matches it exactly: an unknown stage yields zero rows instead of
    quietly widening back to the whole job.
    """
    try:
        return await service.list_job_applications(job_id, current_user, status)
    except JobNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except JobAccessDeniedError as exc:
        # Same translation the screening/recruiter/fairness routers use, so
        # the shared handler answers 404 for unknown and 403 for out-of-scope.
        raise ForbiddenError(str(exc)) from exc


@router.get("/applications/{application_id}", response_model=HRApplicationDetail)
async def get_hr_application_detail(
    application_id: uuid.UUID,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """The HR drill-down for one application.

    One request returns the full oversight view -- job, privacy-limited
    candidate, screening summary, recruiter explainability, fairness context,
    interview and assessment evidence, and a composed timeline -- because a
    read screen must not fan out into a waterfall of per-section calls. Every
    sub-payload is the existing service's own projection, so HR sees exactly
    what an entitled recruiter sees and nothing more; sections that have no
    underlying record (no interview yet, screening not run) come back absent
    rather than fabricated.
    """
    return await service.get_application_detail(application_id, current_user)


@router.get("/pipeline/{status}", response_model=HRStageDrilldownResponse)
async def get_hr_stage_drilldown(
    status: str,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """The jobs behind one funnel stage, grouped so the overview bar is clickable.

    The overview funnel is organization-wide, so one bar can stand for thousands
    of applications spread across jobs. This returns the per-job breakdown of a
    single stage -- one aggregate query, scoped exactly like every other route --
    and each job row is a link to that job's stage-filtered applications.

    An unrecognised stage yields zero rows instead of falling back to the whole
    pipeline, so a stale link can never present an unfiltered list as if it were
    one stage.
    """
    return await service.get_stage_drilldown(status, current_user)


@router.get("/recruiters", response_model=HRRecruiterListResponse)
async def list_hr_recruiters(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Employers (recruiters) in scope, with their real hiring funnel.

    The counterpart to ``/hr/jobs``: the same authorized job set rolled up by
    who owns it, so a recruiter's numbers always equal the sum of the jobs on
    their row. A recruiter with no job in scope is absent rather than shown
    with zeroes, so the list cannot be used to enumerate users.

    Read-only, like every route here -- there is no way to change a recruiter,
    their jobs, or any application from this surface.
    """
    return await service.list_recruiters(current_user)


@router.get("/recruiters/{recruiter_id}", response_model=HRRecruiterDetail)
async def get_hr_recruiter_detail(
    recruiter_id: uuid.UUID,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """One recruiter plus the jobs behind their aggregate.

    Returns 404 for a recruiter outside the caller's organizations, which is
    deliberately the same answer as an unknown id so this route cannot be used
    to confirm that a user id exists in another tenant.
    """
    return await service.get_recruiter_detail(recruiter_id, current_user)


@router.get("/attention", response_model=HRAttentionResponse)
async def list_hr_attention(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Deterministic items that deserve a human look, newest signals first.

    Every item names the rule that produced it and the measured value against
    the threshold, and the thresholds in force are echoed in the payload, so
    the screen can explain itself instead of showing unattributed numbers.

    This is advisory only: nothing here approves, rejects, scores, or changes
    an application. It is a *review trigger*, and the recruiter-owned write
    surface remains the only way to act on any row it points at.
    """
    return await service.list_attention(current_user)


@router.get("/quality", response_model=HRHiringQualityResponse)
async def get_hr_hiring_quality(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Organization-scoped coverage of the existing hiring-quality signals.

    Reports how many applications actually reached screening, interview,
    decision and hire, alongside the fairness alerts the platform's own engine
    produced. Ratios are ``null`` rather than ``0.0`` when the denominator is
    zero, so "no applications" is never displayed as "0% success".

    There is deliberately no composite quality *score* here: screening
    fairness and explainability own those judgments, and a new number would
    imply an authority this read surface does not have.
    """
    return await service.get_hiring_quality(current_user)


def _get_decision_service(
    db: AsyncSession = Depends(get_db),
) -> ApplicationDecisionService:
    return ApplicationDecisionService(db)


@router.get("/interviews", response_model=HRInterviewListResponse)
async def list_hr_interviews(
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """List candidates who are in the HR interview pipeline or have HR interviews."""
    return await service.list_hr_interviews(current_user)


@router.post(
    "/applications/{application_id}/decision",
    response_model=ApplicationDecisionResult,
)
async def record_hr_application_decision(
    application_id: uuid.UUID,
    body: ApplicationDecisionCreate,
    background_tasks: BackgroundTasks,
    service: ApplicationDecisionService = Depends(_get_decision_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Record an explicit HR manager decision: Hire / Select, Reject, or Keep Under Review."""
    result = await service.record_decision(application_id, body, current_user)
    app = await service.lifecycle.application_repo.get(application_id)
    if result.changed_status and app is not None:
        queue_decision_notification(
            background_tasks,
            application_id=application_id,
            candidate_id=app.candidate_id,
            status=result.status,
            candidate_message=result.candidate_message,
        )
        try:
            job = await service.lifecycle.job_repo.get(app.job_id) if hasattr(service.lifecycle, 'job_repo') else None
            if job and job.recruiter_id:
                candidate_user = await service.lifecycle.user_repo.get(app.candidate_id) if hasattr(service.lifecycle, 'user_repo') else None
                candidate_name = candidate_user.full_name if candidate_user else "The candidate"
                decision_label = result.status.value.replace("_", " ").capitalize()
                queue_staff_application_notification(
                    background_tasks,
                    user_id=job.recruiter_id,
                    application_id=application_id,
                    event=f"hr_decision_{result.status.value}",
                    title=f"HR Decision: {candidate_name} ({decision_label})",
                    message=f"HR has finalized the decision for {candidate_name} on {job.title}: {decision_label}.",
                    action_link=f"/recruiter/jobs/{job.id}/applicants",
                )
                if result.status.value == "hired" and job.organization_id:
                    from app.domain.models import OrganizationMembership
                    org_admins_res = await service.session.execute(
                        select(OrganizationMembership.user_id).where(
                            OrganizationMembership.organization_id == job.organization_id,
                            OrganizationMembership.role.in_(["organization_admin", "admin"]),
                            OrganizationMembership.is_active == True,
                        )
                    )
                    for admin_id in org_admins_res.scalars().all():
                        if admin_id != job.recruiter_id:
                            queue_staff_application_notification(
                                background_tasks,
                                user_id=admin_id,
                                application_id=application_id,
                                event="candidate_hired",
                                title=f"Candidate Hired: {candidate_name}",
                                message=f"{candidate_name} has been officially HIRED for {job.title}.",
                                action_link=f"/hr/applications/{application_id}",
                            )
        except Exception:
            pass
    return result


@router.get("/applications/{application_id}/resume/download")
async def download_candidate_resume(
    application_id: uuid.UUID,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Download or view the candidate's resume for an application in scope."""
    application, job = await service.lifecycle.authorize_staff_access(
        application_id, current_user
    )
    from app.domain.models import Resume
    resume_query = select(Resume).where(Resume.user_id == application.candidate_id)
    if application.resume_id:
        resume_query = select(Resume).where(Resume.id == application.resume_id)
    res = await service.session.execute(resume_query.order_by(Resume.created_at.desc()))
    resume = res.scalars().first()
    if not resume:
        raise NotFoundError("Resume not found for this candidate")

    import os
    path = Path(resume.storage_path)
    if not path.exists():
        filename = path.name
        search_dirs = [
            Path(os.getenv("RESUME_UPLOAD_DIR", "uploads/resumes")),
            Path("uploads/resumes"),
            Path("backend/uploads/resumes"),
            Path(r"C:\Users\Tejas P\OneDrive\Desktop\19-09\pro29-9\sudeep\27-9proj\hackyyyy\hackyyy\Hackyton\Hack\hire (2)\hire\backend\uploads\resumes"),
            Path(r"C:\Users\Tejas P\OneDrive\Desktop\pro29-9\sudeep\27-9proj\hackyyyy\hackyyy\Hackyton\Hack\hire (2)\hire\backend\uploads\resumes"),
        ]
        for sdir in search_dirs:
            if (sdir / filename).exists():
                path = sdir / filename
                break
        else:
            raise NotFoundError("Resume file is missing from storage")

    return FileResponse(
        path=str(path),
        filename=resume.original_filename or "resume.pdf",
        media_type=resume.mime_type or "application/pdf",
    )


@router.post(
    "/applications/{application_id}/additional-interview",
    response_model=dict,
)
async def request_additional_hr_interview(
    application_id: uuid.UUID,
    body: dict,
    service: HROversightService = Depends(_get_service),
    current_user: User = Depends(require_role(*HR_OVERSIGHT_ROLES)),
):
    """Schedule or request an additional HR interview evaluation round."""
    return await service.request_additional_interview(application_id, body, current_user)
