import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.enums import ApplicationStatus, EmploymentType, JobStatus
from app.domain.screening_schemas import ScreeningResultResponse


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    department: str | None = Field(None, max_length=255)
    employment_type: EmploymentType
    experience_required: str | None = Field(None, max_length=255)
    education_required: str | None = Field(None, max_length=255)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    location: str = Field(..., min_length=1, max_length=255)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str = "USD"
    description: str = Field(..., min_length=1)
    benefits: str | None = None
    application_deadline: date | None = None
    status: JobStatus = JobStatus.DRAFT


class JobUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    company: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = Field(None, max_length=255)
    employment_type: EmploymentType | None = None
    experience_required: str | None = Field(None, max_length=255)
    education_required: str | None = Field(None, max_length=255)
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    location: str | None = Field(None, min_length=1, max_length=255)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = Field(None, min_length=1)
    benefits: str | None = None
    application_deadline: date | None = None
    status: JobStatus | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    company: str
    department: str | None
    employment_type: str
    experience_required: str | None
    education_required: str | None
    required_skills: list
    preferred_skills: list | None
    location: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    description: str
    benefits: str | None
    application_deadline: date | None
    status: str
    is_archived: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    company: str
    department: str | None
    employment_type: str
    location: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    status: str
    application_deadline: date | None
    created_at: datetime
    updated_at: datetime
    application_count: int = 0

    model_config = {"from_attributes": True}


class JobApplicationCreate(BaseModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    cover_letter: str | None = None


class JobApplicationUpdate(BaseModel):
    status: ApplicationStatus
    reason: str | None = Field(default=None, max_length=255)
    comment: str | None = None


class JobApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID | None
    cover_letter: str | None
    status: str
    screening_status: str = "not_started"
    effective_screening_status: str = "not_started"
    screening_task_id: str | None = None
    screening_error: str | None = None
    screening_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobApplicationDetailResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID | None
    cover_letter: str | None
    status: str
    screening_status: str = "not_started"
    effective_screening_status: str = "not_started"
    screening_task_id: str | None = None
    screening_error: str | None = None
    screening_started_at: datetime | None = None
    screening_completed_at: datetime | None = None
    screening_attempt_count: int = 0
    screening_attempts: int = 0
    screening_result: ScreeningResultResponse | None = None
    overall_match_score: int | None = None
    score: int | None = None
    recommendation: str | None = None
    strength_level: str | None = None
    strength: str | None = None
    decision_reason: str | None = None
    decision_comment: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    candidate_name: str = ""
    candidate_email: str = ""
    job_title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    recruiter_notes: list["RecruiterNoteResponse"] = []

    model_config = {"from_attributes": True}


class ApplicantSummaryResponse(BaseModel):
    job_id: uuid.UUID
    total_applicants: int
    total_screened: int
    not_screened: int
    queued: int
    running: int
    failed: int
    skipped: int
    average_score: float | None = None
    high_match_count: int
    status_breakdown: dict[str, int]
    application_status_breakdown: dict[str, int] = Field(default_factory=dict)
    screening_status_breakdown: dict[str, int]
    recommendation_breakdown: dict[str, int]
    strength_level_breakdown: dict[str, int] = Field(default_factory=dict)


class JobApplicantsResponse(BaseModel):
    job: JobResponse
    items: list[JobApplicationDetailResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    summary: ApplicantSummaryResponse


class SavedJobResponse(BaseModel):
    job_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class JobApplicationListItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID | None
    cover_letter: str | None
    status: str
    screening_status: str = "not_started"
    screening_error: str | None = None
    screening_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    job_title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""


class RecruiterNoteCreate(BaseModel):
    note: str = Field(..., min_length=1)


class RecruiterNoteResponse(BaseModel):
    id: uuid.UUID
    job_application_id: uuid.UUID
    recruiter_id: uuid.UUID
    note: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchParams(BaseModel):
    q: str | None = None
    employment_type: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    skills: list[str] | None = None
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class JobSearchResponse(BaseModel):
    items: list[JobListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


JobApplicationDetailResponse.model_rebuild()
