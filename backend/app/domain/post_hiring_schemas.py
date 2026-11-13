"""Pydantic schemas for Post-Hiring, Offer Management, Document Verification and Onboarding."""

from __future__ import annotations



import uuid

from datetime import datetime

from typing import Any



from pydantic import BaseModel, Field





# ─────────────────────────────────────────────────────────────────────────────

# Offer Management Schemas

# ─────────────────────────────────────────────────────────────────────────────



class JobOfferCreateRequest(BaseModel):

    application_id: uuid.UUID

    designation: str = Field(..., min_length=2, max_length=255)

    department: str = Field(..., min_length=2, max_length=255)

    employment_type: str = Field("full_time", max_length=50)

    offered_salary: float = Field(..., gt=0)

    currency: str = Field("USD", max_length=10)

    work_location: str = Field(..., min_length=2, max_length=255)

    reporting_manager: str | None = Field(None, max_length=255)

    joining_date: datetime

    probation_period_months: int = Field(3, ge=0, le=24)

    benefits_summary: str | None = None

    additional_terms: str | None = None

    offer_expiry_date: datetime

    hr_remarks: str | None = None

    offer_reference_no: str | None = None

    work_arrangement: str | None = "Hybrid"

    base_salary: float | None = None

    variable_compensation: float | None = None

    allowances: float | None = None

    send_immediately: bool = False





class JobOfferUpdateRequest(BaseModel):

    designation: str | None = Field(None, min_length=2, max_length=255)

    department: str | None = Field(None, min_length=2, max_length=255)

    employment_type: str | None = Field(None, max_length=50)

    offered_salary: float | None = Field(None, gt=0)

    currency: str | None = Field(None, max_length=10)

    work_location: str | None = Field(None, min_length=2, max_length=255)

    reporting_manager: str | None = Field(None, max_length=255)

    joining_date: datetime | None = None

    probation_period_months: int | None = Field(None, ge=0, le=24)

    benefits_summary: str | None = None

    additional_terms: str | None = None

    offer_expiry_date: datetime | None = None

    hr_remarks: str | None = None

    offer_reference_no: str | None = None

    work_arrangement: str | None = None

    base_salary: float | None = None

    variable_compensation: float | None = None

    allowances: float | None = None





class JobOfferResponse(BaseModel):

    id: uuid.UUID

    application_id: uuid.UUID

    candidate_id: uuid.UUID

    candidate_name: str | None = None

    candidate_email: str | None = None

    job_id: uuid.UUID

    job_title: str | None = None

    organization_id: uuid.UUID

    organization_name: str | None = None

    created_by_id: uuid.UUID | None = None

    created_by_name: str | None = None



    designation: str

    department: str

    employment_type: str

    offered_salary: float

    currency: str

    work_location: str

    reporting_manager: str | None = None

    joining_date: datetime

    probation_period_months: int

    benefits_summary: str | None = None

    additional_terms: str | None = None

    offer_expiry_date: datetime

    hr_remarks: str | None = None

    offer_reference_no: str | None = None

    application_reference: str | None = None

    work_arrangement: str | None = "Hybrid"

    base_salary: float | None = None

    variable_compensation: float | None = None

    allowances: float | None = None

    variable_percentage: int | None = None

    candidate_phone: str | None = None

    candidate_avatar_url: str | None = None

    candidate_location: str | None = None



    status: str

    sent_at: datetime | None = None

    viewed_at: datetime | None = None

    responded_at: datetime | None = None

    decline_reason: str | None = None

    candidate_notes: str | None = None

    created_at: datetime

    updated_at: datetime



    model_config = {"from_attributes": True}





class JobOfferCandidateResponseRequest(BaseModel):

    action: str = Field(..., pattern="^(accept|decline)$")

    decline_reason: str | None = None

    candidate_notes: str | None = None





class JobOfferClarifyRequest(BaseModel):

    question: str = Field(..., min_length=5, max_length=2000)





# ─────────────────────────────────────────────────────────────────────────────

# Document Verification Schemas

# ─────────────────────────────────────────────────────────────────────────────



class CandidateDocumentResponse(BaseModel):

    id: uuid.UUID

    application_id: uuid.UUID

    candidate_id: uuid.UUID

    candidate_name: str | None = None

    candidate_email: str | None = None

    organization_id: uuid.UUID

    document_type: str

    document_title: str

    file_url: str | None = None

    file_name: str | None = None

    file_size: int | None = None

    mime_type: str | None = None



    status: str

    submitted_at: datetime | None = None

    verified_at: datetime | None = None

    verified_by_id: uuid.UUID | None = None

    verified_by_name: str | None = None

    hr_remarks: str | None = None

    created_at: datetime

    updated_at: datetime



    model_config = {"from_attributes": True}





class DocumentVerifyRequest(BaseModel):

    status: str = Field(..., pattern="^(verified|rejected|resubmission_required)$")

    hr_remarks: str | None = Field(None, max_length=1000)





# ─────────────────────────────────────────────────────────────────────────────

# Employee & Onboarding Schemas

# ─────────────────────────────────────────────────────────────────────────────



class EmployeeCreateRequest(BaseModel):

    candidate_id: uuid.UUID

    application_id: uuid.UUID | None = None

    designation: str = Field(..., min_length=2, max_length=255)

    department: str = Field(..., min_length=2, max_length=255)

    employment_type: str = Field("full_time", max_length=50)

    work_location: str = Field(..., min_length=2, max_length=255)

    reporting_manager: str | None = Field(None, max_length=255)

    joining_date: datetime

    profile_picture_url: str | None = None
    joining_status: str = "pending"
    joining_confirmed_at: datetime | None = None
    joining_remarks: str | None = None
    checklist_template: str | None = "standard"
    onboarding_deadline: datetime | None = None
    activated_at: datetime | None = None





class EmployeeUpdateRequest(BaseModel):

    designation: str | None = None

    department: str | None = None

    employment_type: str | None = None

    work_location: str | None = None

    reporting_manager: str | None = None

    joining_date: datetime | None = None

    employment_status: str | None = None

    profile_picture_url: str | None = None





class OnboardingTaskResponse(BaseModel):

    id: uuid.UUID

    employee_id: uuid.UUID

    organization_id: uuid.UUID

    title: str

    description: str | None = None

    category: str

    assigned_to_role: str

    deadline: datetime | None = None

    is_completed: bool

    completed_at: datetime | None = None

    completed_by_id: uuid.UUID | None = None

    hr_remarks: str | None = None

    status: str = "not_started"

    instructions: str | None = None

    submission_notes: str | None = None

    attachment_url: str | None = None

    created_at: datetime

    updated_at: datetime



    model_config = {"from_attributes": True}





class OnboardingTaskCreateRequest(BaseModel):

    title: str = Field(..., min_length=2, max_length=255)

    description: str | None = None

    category: str = Field("documentation", max_length=50)

    assigned_to_role: str = Field("employee", max_length=50)

    deadline: datetime | None = None

    hr_remarks: str | None = None





class OnboardingTaskUpdateRequest(BaseModel):

    is_completed: bool | None = None

    hr_remarks: str | None = None

    deadline: datetime | None = None





class EmployeeResponse(BaseModel):

    id: uuid.UUID

    employee_id: str

    user_id: uuid.UUID

    user_name: str | None = None

    user_email: str | None = None

    application_id: uuid.UUID | None = None

    organization_id: uuid.UUID

    organization_name: str | None = None

    designation: str

    department: str

    employment_type: str

    work_location: str

    reporting_manager: str | None = None

    joining_date: datetime

    employment_status: str

    onboarding_status: str

    onboarding_completed_at: datetime | None = None

    profile_picture_url: str | None = None

    joining_status: str = "pending"

    joining_confirmed_at: datetime | None = None

    joining_remarks: str | None = None

    checklist_template: str | None = "standard"

    onboarding_deadline: datetime | None = None

    activated_at: datetime | None = None

    created_at: datetime

    updated_at: datetime



    total_tasks: int = 0

    completed_tasks: int = 0

    onboarding_progress_percent: int = 0

    tasks: list[OnboardingTaskResponse] = []



    model_config = {"from_attributes": True}





# ─────────────────────────────────────────────────────────────────────────────

# Dashboard & Aggregate Schemas

# ─────────────────────────────────────────────────────────────────────────────



class UpcomingJoining(BaseModel):

    employee_id: str | None = None

    candidate_name: str

    candidate_email: str

    designation: str

    department: str

    joining_date: datetime

    status: str

    avatar_url: str | None = None





class RecentHiringActivity(BaseModel):

    id: str

    title: str

    description: str

    activity_type: str

    timestamp: datetime

    badge_variant: str = "default"





class PostHiringStatsResponse(BaseModel):
    total_selected_candidates: int = 0
    offers_created: int = 0
    offers_sent: int = 0
    offers_viewed: int = 0
    offers_pending: int = 0
    offers_accepted: int = 0
    offers_declined: int = 0
    documents_submitted: int = 0
    documents_pending_verification: int = 0
    documents_verified: int = 0
    documents_requiring_resubmission: int = 0
    employees_onboarding: int = 0
    onboarding_tasks_pending: int = 0
    onboarding_completion_rate: int = 0
    active_employees: int = 0
    upcoming_joinings: list[UpcomingJoining] = []
    recent_activities: list[RecentHiringActivity] = []


class RecruiterPostHiringCandidateItem(BaseModel):
    application_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    job_id: uuid.UUID
    job_title: str
    department: str
    hr_hiring_decision: str = "HIRED"
    offer_id: uuid.UUID | None = None
    offer_status: str | None = None
    offer_sent_at: datetime | None = None
    offer_accepted_at: datetime | None = None
    joining_date: datetime | None = None
    document_submission_status: str = "Pending"
    documents_submitted: int = 0
    documents_verified: int = 0
    documents_total: int = 4
    onboarding_status: str = "Not Started"
    onboarding_progress_percent: int = 0
    employee_status: str = "None"
    employee_id_code: str | None = None
    updated_at: datetime | None = None


class PostHiringTimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    title: str
    description: str
    actor_name: str
    actor_role: str
    status: str = "completed"
    action_link: str | None = None





class ApprovedCandidateSummary(BaseModel):

    application_id: uuid.UUID

    candidate_id: uuid.UUID

    candidate_name: str

    candidate_email: str

    job_id: uuid.UUID

    job_title: str

    department: str

    application_status: str

    has_offer: bool

    offer_id: uuid.UUID | None = None

    offer_status: str | None = None

    recruiter_score: int | None = None

    hr_score: int | None = None

    decision: str | None = None



class JoiningConfirmRequest(BaseModel):
    joining_status: str = Field("confirmed", pattern="^(confirmed|no_show|cancelled)$")
    joining_date: datetime | None = None
    remarks: str | None = None


class CandidateTaskSubmitRequest(BaseModel):
    submission_notes: str | None = None
    attachment_url: str | None = None


class TaskReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(completed|rejected)$")
    hr_remarks: str | None = None
