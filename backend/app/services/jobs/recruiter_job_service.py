import logging
import uuid

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.domain.enums import (
    ApplicationStatus,
    HiringRecommendation,
    MembershipStatus,
    NotificationType,
    ScreeningStatus,
)
from app.domain.job_schemas import JobCreate, JobResponse, JobUpdate, RecruiterNoteCreate
from app.domain.models import Job, JobApplication, Notification, OrganizationMembership, RecruiterNote, User
from app.domain.screening_schemas import ScreeningResultResponse
from app.repositories.jobs.job import (
    APPLICANT_SORT_ALIASES,
    JobApplicationRepository,
    JobRepository,
)
from app.repositories.user import UserRepository
from app.services.applications.application_lifecycle_service import ApplicationLifecycleService
from app.services.screening.access import (
    JobAccessDeniedError,
    JobNotFoundError,
    authorize_job_access,
)

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")


class RecruiterJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = JobRepository(session)
        self.application_repo = JobApplicationRepository(session)
        self.user_repo = UserRepository(session)
        self.lifecycle_service = ApplicationLifecycleService(session)

    async def create_job(
        self,
        recruiter_id: uuid.UUID,
        data: JobCreate,
        organization_id: uuid.UUID | None = None,
    ) -> Job:
        org_id = organization_id
        if not org_id:
            mem_stmt = (
                select(OrganizationMembership.organization_id)
                .where(
                    OrganizationMembership.user_id == recruiter_id,
                    OrganizationMembership.status == MembershipStatus.ACTIVE.value,
                )
                .limit(1)
            )
            mem_res = await self.session.execute(mem_stmt)
            org_id = mem_res.scalar_one_or_none()

        employment_type = (
            data.employment_type.value
            if hasattr(data.employment_type, "value")
            else data.employment_type
        )
        status_val = (
            data.status.value
            if hasattr(data.status, "value")
            else data.status
        )

        job = await self.job_repo.create(
            recruiter_id=recruiter_id,
            organization_id=org_id,
            title=data.title,
            company=data.company,
            department=data.department,
            employment_type=employment_type,
            experience_required=data.experience_required,
            education_required=data.education_required,
            required_skills=data.required_skills,
            preferred_skills=data.preferred_skills,
            location=data.location,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            salary_currency=data.salary_currency,
            description=data.description,
            benefits=data.benefits,
            application_deadline=data.application_deadline,
            status=status_val,
        )
        AUDIT_LOGGER.info(
            "JOB_CREATE | recruiter=%s job=%s title=%s",
            recruiter_id, job.id, job.title,
        )
        return job

    async def update_job(self, job_id: uuid.UUID, recruiter_id: uuid.UUID, data: JobUpdate) -> Job | None:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            return None
        update_kwargs = data.model_dump(exclude_unset=True)
        if update_kwargs.get("employment_type"):
            update_kwargs["employment_type"] = update_kwargs["employment_type"].value
        if update_kwargs.get("status"):
            update_kwargs["status"] = update_kwargs["status"].value
        if update_kwargs:
            update_kwargs["version"] = job.version + 1
        updated = await self.job_repo.update(job_id, **update_kwargs)
        AUDIT_LOGGER.info(
            "JOB_UPDATE | recruiter=%s job=%s fields=%s",
            recruiter_id, job_id, list(update_kwargs.keys()),
        )
        return updated

    async def get_job(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> Job | None:
        return await self.job_repo.get_by_recruiter(job_id, recruiter_id)

    async def list_jobs(self, recruiter_id: uuid.UUID) -> list[dict]:
        jobs = await self.job_repo.list_by_recruiter(recruiter_id)
        result = []
        for job in jobs:
            count = await self.application_repo.count_by_job(job.id)
            result.append({
                "id": job.id,
                "recruiter_id": job.recruiter_id,
                "title": job.title,
                "company": job.company,
                "department": job.department,
                "employment_type": job.employment_type,
                "location": job.location,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "status": job.status,
                "application_deadline": job.application_deadline,
                "application_count": count,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            })
        return result

    async def delete_job(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> bool:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            return False
        await self.session.delete(job)
        await self.session.flush()
        AUDIT_LOGGER.info("JOB_DELETE | recruiter=%s job=%s", recruiter_id, job_id)
        return True

    async def change_job_status(self, job_id: uuid.UUID, recruiter_id: uuid.UUID, status: str) -> Job | None:
        job = await self.job_repo.get_by_recruiter(job_id, recruiter_id)
        if not job:
            return None
        updated = await self.job_repo.update(job_id, status=status, version=job.version + 1)
        AUDIT_LOGGER.info(
            "JOB_STATUS_CHANGE | recruiter=%s job=%s status=%s",
            recruiter_id, job_id, status,
        )
        return updated

    @staticmethod
    def _value(value) -> str | None:
        if value is None:
            return None
        return getattr(value, "value", value)

    async def _actor(self, actor: User | uuid.UUID) -> User:
        if isinstance(actor, User):
            return actor
        user = await self.user_repo.get(actor)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def _authorize_recruiter_job(
        self, job_id: uuid.UUID, actor: User | uuid.UUID,
    ) -> Job:
        user = await self._actor(actor)
        try:
            return await authorize_job_access(self.session, job_id, user)
        except JobNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        except JobAccessDeniedError as exc:
            raise ForbiddenError(str(exc)) from exc

    @staticmethod
    def _screening_result(application: JobApplication):
        screening = application.screening_result
        if isinstance(screening, (list, tuple, set)):
            return next(iter(screening), None)
        return screening

    @classmethod
    def effective_screening_status(cls, application: JobApplication) -> str:
        """A stored screening result always means effective ``completed``.

        Manual screening can leave ``JobApplication.screening_status`` stale, so
        the presence of a result is the authority. Shared with the Phase 5
        screening detail so both surfaces agree.
        """
        if cls._screening_result(application) is not None:
            return ScreeningStatus.COMPLETED.value
        return cls._value(application.screening_status) or ScreeningStatus.NOT_STARTED.value

    @classmethod
    def _application_to_dict(cls, application: JobApplication, job: Job) -> dict:
        candidate = application.candidate
        screening = cls._screening_result(application)
        screening_dict = None
        if screening is not None:
            screening_dict = ScreeningResultResponse.model_validate(screening).model_dump()

        notes = [
            {
                "id": note.id,
                "job_application_id": note.job_application_id,
                "recruiter_id": note.recruiter_id,
                "note": note.note,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
            }
            for note in application.recruiter_notes
        ]
        score = screening.overall_match_score if screening else None
        recommendation = cls._value(screening.recommendation) if screening else None
        strength = cls._value(screening.strength_level) if screening else None
        effective_status = cls.effective_screening_status(application)
        attempts = application.screening_attempts or 0
        return {
            "id": application.id,
            "job_id": application.job_id,
            "candidate_id": application.candidate_id,
            "resume_id": application.resume_id,
            "cover_letter": application.cover_letter,
            "status": cls._value(application.status),
            "screening_status": effective_status,
            "effective_screening_status": effective_status,
            "screening_task_id": application.screening_task_id,
            "screening_error": application.screening_error,
            "screening_started_at": application.screening_started_at,
            "screening_completed_at": application.screening_completed_at,
            "screening_attempt_count": attempts,
            "screening_attempts": attempts,
            "screening_result": screening_dict,
            "overall_match_score": score,
            "score": score,
            "recommendation": recommendation,
            "strength_level": strength,
            "strength": strength,
            "decision_reason": application.decision_reason,
            "decision_comment": application.decision_comment,
            "decided_at": application.decided_at,
            "created_at": application.created_at,
            "updated_at": application.updated_at,
            "candidate_name": candidate.full_name if candidate else "",
            "candidate_email": candidate.email if candidate else "",
            "job_title": job.title,
            "company": job.company,
            "location": job.location,
            "employment_type": cls._value(job.employment_type),
            "recruiter_notes": notes,
        }

    async def get_applications_for_job(
        self,
        job_id: uuid.UUID,
        recruiter_id: User | uuid.UUID,
    ) -> list[dict]:
        job = await self._authorize_recruiter_job(job_id, recruiter_id)
        applications = await self.application_repo.list_all_with_screening_by_job(job_id)
        return [self._application_to_dict(application, job) for application in applications]

    async def get_job_applicants(
        self,
        job_id: uuid.UUID,
        actor: User | uuid.UUID,
        *,
        q: str | None = None,
        application_status: ApplicationStatus | str | None = None,
        screening_status: ScreeningStatus | str | None = None,
        recommendation: HiringRecommendation | str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        sort_by: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        job = await self._authorize_recruiter_job(job_id, actor)

        if page < 1:
            raise ValidationError("page must be at least 1")
        if page_size < 1 or page_size > 100:
            raise ValidationError("page_size must be between 1 and 100")
        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValidationError("min_score cannot be greater than max_score")

        allowed_application_statuses = {item.value for item in ApplicationStatus}
        allowed_screening_statuses = {item.value for item in ScreeningStatus}
        allowed_recommendations = {item.value for item in HiringRecommendation}
        application_status_value = self._value(application_status)
        screening_status_value = self._value(screening_status)
        recommendation_value = self._value(recommendation)
        if application_status_value and application_status_value not in allowed_application_statuses:
            raise ValidationError("Invalid application_status")
        if screening_status_value and screening_status_value not in allowed_screening_statuses:
            raise ValidationError("Invalid screening_status")
        if recommendation_value and recommendation_value not in allowed_recommendations:
            raise ValidationError("Invalid recommendation")
        normalized_sort_by = APPLICANT_SORT_ALIASES.get(sort_by)
        if normalized_sort_by is None:
            raise ValidationError("Invalid sort_by")

        applications, total = await self.application_repo.list_filtered_by_job(
            job_id,
            q=q.strip() if q and q.strip() else None,
            application_status=application_status_value,
            screening_status=screening_status_value,
            recommendation=recommendation_value,
            min_score=min_score,
            max_score=max_score,
            sort_by=normalized_sort_by,
            page=page,
            page_size=page_size,
        )
        summary = await self.application_repo.get_dashboard_summary(job_id)
        return {
            "job": JobResponse.model_validate(job).model_dump(),
            "items": [self._application_to_dict(application, job) for application in applications],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "summary": summary,
        }

    async def get_job_applicant_summary(
        self, job_id: uuid.UUID, actor: User | uuid.UUID,
    ) -> dict:
        await self._authorize_recruiter_job(job_id, actor)
        return await self.application_repo.get_dashboard_summary(job_id)

    async def update_application_status(
        self,
        application_id: uuid.UUID,
        actor: User,
        status: str,
        reason: str | None = None,
        comment: str | None = None,
    ) -> JobApplication:
        """Transition an application through the lifecycle service and notify
        the candidate when the status actually changed."""
        app = await self.application_repo.get(application_id)
        if not app:
            raise NotFoundError("Application not found")
        job = await self.job_repo.get(app.job_id)
        if not job:
            raise NotFoundError("Job not found")
        previous_status = app.status

        updated = await self.lifecycle_service.transition_application(
            application_id, status, actor, reason=reason, comment=comment,
        )

        if previous_status != updated.status:
            notification = Notification(
                user_id=app.candidate_id,
                title="Application Status Updated",
                message=f"Your application for '{job.title}' has been updated to {updated.status.replace('_', ' ').title()}",
                notification_type=NotificationType.APPLICATION_STATUS,
            )
            self.session.add(notification)
            await self.session.flush()
        return updated

    async def add_recruiter_note(
        self,
        application_id: uuid.UUID,
        actor: User | uuid.UUID,
        data: RecruiterNoteCreate,
    ) -> RecruiterNote | None:
        app = await self.application_repo.get(application_id)
        if not app:
            return None
        await self._authorize_recruiter_job(app.job_id, actor)
        user = await self._actor(actor)
        note = RecruiterNote(
            job_application_id=application_id,
            recruiter_id=user.id,
            note=data.note,
        )
        self.session.add(note)
        await self.session.flush()
        return note

    async def update_recruiter_note(
        self,
        note_id: uuid.UUID,
        application_id: uuid.UUID,
        actor: User | uuid.UUID,
        note_text: str,
    ) -> RecruiterNote | None:
        app = await self.application_repo.get(application_id)
        if not app:
            return None
        await self._authorize_recruiter_job(app.job_id, actor)
        user = await self._actor(actor)
        stmt = (
            sa_update(RecruiterNote)
            .where(
                RecruiterNote.id == note_id,
                RecruiterNote.job_application_id == application_id,
                RecruiterNote.recruiter_id == user.id,
            )
            .values(note=note_text)
            .returning(RecruiterNote)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete_recruiter_note(
        self,
        note_id: uuid.UUID,
        application_id: uuid.UUID,
        actor: User | uuid.UUID,
    ) -> bool:
        app = await self.application_repo.get(application_id)
        if not app:
            return False
        await self._authorize_recruiter_job(app.job_id, actor)
        user = await self._actor(actor)
        note = await self.session.get(RecruiterNote, note_id)
        if not note or note.recruiter_id != user.id or note.job_application_id != application_id:
            return False
        await self.session.delete(note)
        await self.session.flush()
        return True

    async def get_recruiter_dashboard(self, recruiter_id: uuid.UUID) -> dict:
        jobs = await self.job_repo.list_by_recruiter(recruiter_id)
        total_jobs = len(jobs)
        published = sum(1 for j in jobs if j.status == "published")
        draft = sum(1 for j in jobs if j.status == "draft")
        closed = sum(1 for j in jobs if j.status == "closed")
        total_applications = 0
        recent_applications = []
        for job in jobs:
            apps = await self.application_repo.list_by_job(job.id)
            total_applications += len(apps)
            for app in apps[:5]:
                candidate = await self.user_repo.get(app.candidate_id)
                recent_applications.append({
                    "id": app.id,
                    "job_title": job.title,
                    "candidate_name": candidate.full_name if candidate else "",
                    "status": app.status,
                    "created_at": app.created_at,
                })
        recent_applications.sort(key=lambda x: x["created_at"], reverse=True)
        recent_applications = recent_applications[:10]
        return {
            "total_jobs": total_jobs,
            "published_jobs": published,
            "draft_jobs": draft,
            "closed_jobs": closed,
            "total_applications": total_applications,
            "recent_applications": recent_applications,
        }
