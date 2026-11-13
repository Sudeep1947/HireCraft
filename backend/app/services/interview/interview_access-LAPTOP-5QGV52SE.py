"""Server-side access control for Interview Intelligence reads and writes.

Phase 11 makes the interview system part of the application-centric hiring
workflow, which turns its authorization from a cosmetic concern into a tenant
boundary: interview evidence contains scorecards, per-answer evaluations and
recruiter notes for a specific candidate at a specific employer. This module
centralizes who may read or change what, so the rule exists once.

Two audiences, two rules:

- **Staff** may reach an interview through the job it belongs to, using the same
  job-owner-or-active-organization-staff check the screening and application
  layers already use. A recruiter who is not the job owner but is an active
  member of the job's organization with a read role is allowed; a recruiter from
  a different organization is not.
- **The candidate** may reach only interviews where they are the candidate. They
  are not a member of the hiring organization, so no organization check applies
  and the interview row is the only link between the two.

Every function here takes the interview id as untrusted input and authorizes
against the loaded row. A caller that passes somebody else's interview id gets
the same error whether or not that interview exists, so ids cannot be probed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.domain.models import Interview, Job, User
from app.repositories.interview.interview import InterviewRepository
from app.services.screening.access import JobAccessDeniedError, authorize_job_access

# Roles that may read interview intelligence inside their organization. Kept
# aligned with the screening read roles so a recruiter does not gain interview
# access to a job their screening access already denies.
_INTERVIEW_STAFF_ROLES = {"recruiter", "hr", "hr_manager", "organization_admin", "admin"}


async def load_interview_for_read(
    session: AsyncSession,
    interview_id: uuid.UUID,
    user: User,
) -> Interview:
    """Load an interview ``user`` is allowed to read.

    Raises ``NotFoundError`` when the interview does not exist or the caller may
    not see it, so an unauthorized probe is indistinguishable from a missing id.
    """
    repo = InterviewRepository(session)
    interview = await repo.get(interview_id)
    if interview is None:
        raise NotFoundError("Interview not found")

    if interview.candidate_id == user.id:
        return interview

    try:
        await authorize_job_access(session, interview.job_id, user)
    except JobAccessDeniedError as exc:
        raise NotFoundError("Interview not found") from exc
    return interview


async def load_interview_for_staff_write(
    session: AsyncSession,
    interview_id: uuid.UUID,
    user: User,
) -> Interview:
    """Load an interview ``user`` is allowed to change as staff.

    Same job-scoped rule as the read path, but a candidate who happens to be the
    interview's subject is refused outright: completing or scoring an interview
    is a staff action, and the candidate self-service path goes through the mock
    interview flow instead.
    """
    repo = InterviewRepository(session)
    interview = await repo.get(interview_id)
    if interview is None:
        raise NotFoundError("Interview not found")

    if interview.candidate_id == user.id:
        raise ForbiddenError("You do not have permission to modify this interview")

    try:
        await authorize_job_access(session, interview.job_id, user)
    except JobAccessDeniedError as exc:
        raise NotFoundError("Interview not found") from exc
    return interview


async def load_interview_for_staff_read(
    session: AsyncSession,
    interview_id: uuid.UUID,
    user: User,
) -> Interview:
    """Load an interview only staff may read, refusing the subject candidate.

    Distinct from :func:`load_interview_for_read`, which returns the interview
    when the caller *is* the candidate. Being the subject of an interview is not
    permission to read the hiring material attached to it: a scorecard holds the
    recommendation, the hiring confidence and the recruiter's private notes, and
    those must not be readable by the person being judged. Staff reach for
    :func:`load_interview_for_read`; this is for the endpoints that are staff
    material end to end.
    """
    repo = InterviewRepository(session)
    interview = await repo.get(interview_id)
    if interview is None:
        raise NotFoundError("Interview not found")

    if interview.candidate_id == user.id:
        raise ForbiddenError("You do not have permission to view this interview")

    try:
        await authorize_job_access(session, interview.job_id, user)
    except JobAccessDeniedError as exc:
        raise NotFoundError("Interview not found") from exc
    return interview


async def require_job_staff_access(
    session: AsyncSession, job_id: uuid.UUID, user: User,
) -> Job:
    """Resolve a job the caller may act on as staff.

    Wraps the screening access check so interview routes surface a 403 instead of
    leaking a 404, and so a candidate cannot reach a staff scheduling path by
    passing their own id around.
    """
    try:
        return await authorize_job_access(session, job_id, user)
    except JobAccessDeniedError as exc:
        raise ForbiddenError("You do not have access to this job") from exc


def is_staff_role(user: User) -> bool:
    """True when the user holds a role that may read interview evidence."""
    return bool(_INTERVIEW_STAFF_ROLES & {ur.role.name for ur in user.roles})


async def require_own_interview(
    session: AsyncSession, interview_id: uuid.UUID, user: User,
) -> Interview:
    """Load an interview the caller must *be the candidate* of.

    The candidate self-service paths (answering a question, finishing a mock
    session, submitting a coding solution) are not job-scoped: a candidate is not
    a member of the hiring organization, so the only thing tying them to an
    interview is the ``candidate_id`` column. Staff reading their own interviews
    is a different question, answered by
    :func:`load_interview_for_read`.

    A 404 is raised rather than a 403 so a candidate cannot use these endpoints to
    discover which interview ids exist.
    """
    repo = InterviewRepository(session)
    interview = await repo.get(interview_id)
    if interview is None or interview.candidate_id != user.id:
        raise NotFoundError("Interview not found")
    return interview


async def require_own_question(
    session: AsyncSession, question_id: uuid.UUID, user: User,
) -> Interview:
    """Resolve a question id to the interview the caller is the candidate of.

    Answers are submitted by question id, which is untrusted input. Resolving it
    to its interview first is what stops a candidate from answering -- and
    therefore reading the AI evaluation of -- somebody else's interview.
    """
    from app.domain.models import InterviewQuestion

    question = await session.get(InterviewQuestion, question_id)
    if question is None:
        raise NotFoundError("Question not found")
    return await require_own_interview(session, question.interview_id, user)


async def require_own_coding_assessment(
    session: AsyncSession, assessment_id: uuid.UUID, user: User,
):
    """Resolve a coding assessment id to the caller's own interview."""
    from app.domain.models import CodingAssessment

    assessment = await session.get(CodingAssessment, assessment_id)
    if assessment is None:
        raise NotFoundError("Assessment not found")
    await require_own_interview(session, assessment.interview_id, user)
    return assessment
