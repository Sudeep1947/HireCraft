import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.enums import ApplicationStatus, NotificationType
from app.domain.job_schemas import JobApplicationCreate, JobSearchParams
from app.domain.models import Job, JobApplication, Notification, SavedJob, User
from app.repositories.candidate.resume import ResumeRepository
from app.repositories.jobs.job import JobApplicationRepository, JobRepository, SavedJobRepository
from app.repositories.user import UserRepository
from app.services.applications.application_lifecycle_service import ApplicationLifecycleService
from app.services.applications.screening_scheduler import dispatch_automatic_screening

logger = logging.getLogger(__name__)


class CandidateJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = JobRepository(session)
        self.application_repo = JobApplicationRepository(session)
        self.saved_job_repo = SavedJobRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.user_repo = UserRepository(session)
        self.lifecycle_service = ApplicationLifecycleService(session)

    async def search_jobs(self, params: JobSearchParams) -> dict:
        items, total = await self.job_repo.search(
            q=params.q,
            employment_type=params.employment_type,
            location=params.location,
            salary_min=params.salary_min,
            salary_max=params.salary_max,
            skills=params.skills,
            status=params.status,
            page=params.page,
            page_size=params.page_size,
        )
        total_pages = max(1, (total + params.page_size - 1) // params.page_size)
        job_list = []
        for job in items:
            count = await self.application_repo.count_by_job(job.id)
            job_list.append({
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
        return {
            "items": job_list,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": total_pages,
        }

    async def get_job_detail(self, job_id: uuid.UUID) -> Job | None:
        job = await self.job_repo.get(job_id)
        if not job or job.status != "published" or job.is_archived:
            return None
        return job

    async def apply(self, candidate_id: uuid.UUID, data: JobApplicationCreate) -> JobApplication:
        existing = await self.application_repo.get_by_job_and_candidate(data.job_id, candidate_id)
        if existing:
            raise ValueError("You have already applied for this job")
        job = await self.job_repo.get(data.job_id)
        if not job or job.status != "published":
            raise ValueError("Job is not available for applications")
        app = JobApplication(
            job_id=data.job_id,
            candidate_id=candidate_id,
            resume_id=data.resume_id,
            cover_letter=data.cover_letter,
            status=ApplicationStatus.APPLIED.value,
        )
        self.session.add(app)
        await self.session.flush()

        candidate = await self.user_repo.get(candidate_id)
        await self.lifecycle_service.record_creation(app, actor=candidate)

        candidate_name = candidate.full_name if candidate else "A candidate"
        notification = Notification(
            user_id=job.recruiter_id,
            title="New Application Received",
            message=f"{candidate_name} applied for '{job.title}'",
            notification_type=NotificationType.APPLICATION_STATUS,
        )
        self.session.add(notification)
        await self.session.flush()

        await dispatch_automatic_screening(self.session, app.id)

        return app

    async def get_my_applications(self, candidate_id: uuid.UUID) -> list[dict]:
        """List the caller's own applications, each with its job summary.

        Jobs are fetched in a single query rather than one per application, so a
        candidate with many applications does not trigger a query per row. A job
        that is no longer present still yields a row with empty job fields
        instead of dropping the application from the candidate's list.
        """
        apps = await self.application_repo.list_by_candidate(candidate_id)
        if not apps:
            return []
        job_ids = {app.job_id for app in apps}
        jobs = {
            job.id: job
            for job in (
                await self.session.execute(select(Job).where(Job.id.in_(job_ids)))
            ).scalars().all()
        }
        result = []
        for app in apps:
            job = jobs.get(app.job_id)
            result.append({
                "id": app.id,
                "job_id": app.job_id,
                "candidate_id": app.candidate_id,
                "resume_id": app.resume_id,
                "cover_letter": app.cover_letter,
                "status": app.status,
                "screening_status": app.screening_status,
                "screening_error": app.screening_error,
                "screening_completed_at": app.screening_completed_at,
                "created_at": app.created_at,
                "updated_at": app.updated_at,
                "job_title": job.title if job else "",
                "company": job.company if job else "",
                "location": job.location if job else "",
                "employment_type": job.employment_type if job else "",
            })
        return result

    async def withdraw_application(self, application_id: uuid.UUID, candidate: User) -> JobApplication:
        app = await self.application_repo.get(application_id)
        if not app or app.candidate_id != candidate.id:
            raise NotFoundError("Application not found")
        return await self.lifecycle_service.transition_application(
            application_id, ApplicationStatus.WITHDRAWN.value, candidate,
        )

    async def save_job(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> SavedJob:
        existing = await self.saved_job_repo.is_saved(candidate_id, job_id)
        if existing:
            raise ValueError("Job already saved")
        saved = SavedJob(candidate_id=candidate_id, job_id=job_id)
        self.session.add(saved)
        await self.session.flush()
        return saved

    async def unsave_job(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        return await self.saved_job_repo.remove(candidate_id, job_id)

    async def get_saved_jobs(self, candidate_id: uuid.UUID) -> list[dict]:
        saved = await self.saved_job_repo.list_by_candidate(candidate_id)
        result = []
        for s in saved:
            job = await self.job_repo.get(s.job_id)
            if job:
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
                    "saved_at": s.created_at,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                })
        return result

    async def get_candidate_dashboard(self, candidate_id: uuid.UUID) -> dict:
        apps = await self.application_repo.list_by_candidate(candidate_id)
        saved = await self.saved_job_repo.list_by_candidate(candidate_id)
        status_counts = {}
        for app in apps:
            status_counts[app.status] = status_counts.get(app.status, 0) + 1
        return {
            "total_applications": len(apps),
            "saved_jobs": len(saved),
            "status_breakdown": status_counts,
            "recent_applications": [
                {
                    "id": app.id,
                    "job_id": app.job_id,
                    "status": app.status,
                    "created_at": app.created_at,
                }
                for app in sorted(apps, key=lambda x: x.created_at, reverse=True)[:5]
            ],
        }
