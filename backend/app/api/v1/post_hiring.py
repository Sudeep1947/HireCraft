"""Post-Hiring, Offer Management, Document Verification and Employee Onboarding API routes."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.db.session import get_db
from app.domain.models import User
from app.domain.post_hiring_schemas import (
    JoiningConfirmRequest,
    CandidateTaskSubmitRequest,
    TaskReviewRequest,
    RecruiterPostHiringCandidateItem,
    PostHiringTimelineEvent,
    ApprovedCandidateSummary,
    CandidateDocumentResponse,
    DocumentVerifyRequest,
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
    JobOfferCandidateResponseRequest,
    JobOfferClarifyRequest,
    JobOfferCreateRequest,
    JobOfferResponse,
    JobOfferUpdateRequest,
    OnboardingTaskCreateRequest,
    OnboardingTaskResponse,
    OnboardingTaskUpdateRequest,
    PostHiringStatsResponse,
)
from app.services.post_hiring.post_hiring_service import DOCUMENTS_UPLOAD_DIR, PostHiringService

router = APIRouter(prefix="/post-hiring", tags=["post-hiring"])

HR_STAFF_ROLES = ["hr", "hr_manager", "organization_admin", "admin"]
ALL_STAFF_ROLES = ["hr", "hr_manager", "recruiter", "organization_admin", "admin"]


def get_service(db: AsyncSession = Depends(get_db)) -> PostHiringService:
    return PostHiringService(db)


# ─────────────────────────────────────────────────────────────────────────────
# HR / Recruiter / Admin: Statistics & Overview
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=PostHiringStatsResponse)
async def get_hr_post_hiring_stats(
    current_user: User = Depends(require_role(*ALL_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Retrieve post-hiring statistics and upcoming joinings for HR and staff."""
    return await service.get_hr_stats(current_user)


@router.get("/approved-candidates", response_model=list[ApprovedCandidateSummary])
async def get_approved_candidates(
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """List candidates who are selected or recommended and eligible for an offer."""
    return await service.get_approved_candidates(current_user)


# ─────────────────────────────────────────────────────────────────────────────
# Offers Management (HR & Staff)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/offers", response_model=list[JobOfferResponse])
async def list_offers(
    status: str | None = Query(None),
    current_user: User = Depends(require_role(*ALL_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """List job offers scoped to caller's organization."""
    return await service.get_offers(current_user, status=status)


@router.post("/offers", response_model=JobOfferResponse)
async def create_job_offer(
    payload: JobOfferCreateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Create a new job offer (as draft or sent immediately)."""
    return await service.create_offer(current_user, payload)


@router.get("/offers/{offer_id}", response_model=JobOfferResponse)
async def get_job_offer(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PostHiringService = Depends(get_service),
):
    """Get details of a specific job offer."""
    return await service.get_offer_by_id(current_user, offer_id)


@router.put("/offers/{offer_id}", response_model=JobOfferResponse)
async def update_job_offer(
    offer_id: uuid.UUID,
    payload: JobOfferUpdateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Update details of a draft job offer."""
    return await service.update_offer(current_user, offer_id, payload)


@router.post("/offers/{offer_id}/send", response_model=JobOfferResponse)
async def send_job_offer(
    offer_id: uuid.UUID,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Send a draft job offer to the candidate."""
    return await service.send_offer(current_user, offer_id)


@router.post("/offers/{offer_id}/withdraw", response_model=JobOfferResponse)
async def withdraw_job_offer(
    offer_id: uuid.UUID,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Withdraw an issued job offer."""
    return await service.withdraw_offer(current_user, offer_id)


@router.get("/offers/{offer_id}/pdf")
async def download_offer_pdf(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PostHiringService = Depends(get_service),
):
    """Download official PDF offer letter."""
    # Check access first
    await service.get_offer_by_id(current_user, offer_id)
    pdf_bytes = await service.generate_offer_pdf(offer_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Job_Offer_{offer_id}.pdf"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Candidate Post-Hiring Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/candidate/offers", response_model=list[JobOfferResponse])
async def candidate_get_my_offers(
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Retrieve all active offers addressed to the logged-in candidate."""
    return await service.candidate_get_offers(current_user)


@router.post("/candidate/offers/{offer_id}/respond", response_model=JobOfferResponse)
async def candidate_respond_to_offer(
    offer_id: uuid.UUID,
    payload: JobOfferCandidateResponseRequest,
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Accept or decline an offer."""
    return await service.candidate_respond_offer(current_user, offer_id, payload)


@router.post("/candidate/offers/{offer_id}/clarify")
async def candidate_clarify_offer(
    offer_id: uuid.UUID,
    payload: JobOfferClarifyRequest,
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Submit a question or clarification request about an offer."""
    return await service.candidate_clarify_offer(current_user, offer_id, payload.question)


@router.get("/candidate/documents", response_model=list[CandidateDocumentResponse])
async def candidate_get_my_documents(
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Retrieve required document checklist and submission statuses."""
    return await service.get_candidate_documents(current_user)


@router.post("/candidate/documents/upload", response_model=CandidateDocumentResponse)
async def candidate_upload_document(
    application_id: uuid.UUID = Form(...),
    document_type: str = Form(...),
    document_title: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Upload a verification document file."""
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise ValidationError("File size exceeds 10MB limit.")

    return await service.candidate_upload_document(
        candidate_user=current_user,
        application_id=application_id,
        document_type=document_type,
        document_title=document_title or document_type.replace("_", " ").title(),
        file_bytes=contents,
        file_name=file.filename or "document.pdf",
        mime_type=file.content_type or "application/octet-stream",
    )


@router.get("/candidate/onboarding", response_model=EmployeeResponse | None)
async def candidate_get_onboarding_status(
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Retrieve onboarding status and task checklist for candidate."""
    return await service.candidate_get_onboarding(current_user)


@router.post("/candidate/tasks/{task_id}/toggle", response_model=OnboardingTaskResponse)
async def candidate_toggle_task_completion(
    task_id: uuid.UUID,
    current_user: User = Depends(require_role("candidate")),
    service: PostHiringService = Depends(get_service),
):
    """Toggle completion of an assigned onboarding task."""
    return await service.candidate_toggle_task(current_user, task_id)


# ─────────────────────────────────────────────────────────────────────────────
# Document Verification (HR & Staff)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/documents", response_model=list[CandidateDocumentResponse])
async def list_candidate_documents(
    application_id: uuid.UUID | None = Query(None),
    candidate_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(require_role(*ALL_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """List candidate documents pending or completed for organization."""
    return await service.get_candidate_documents(
        current_user, application_id=application_id, candidate_id=candidate_id,
    )


@router.post("/documents/{document_id}/verify", response_model=CandidateDocumentResponse)
async def verify_candidate_document(
    document_id: uuid.UUID,
    payload: DocumentVerifyRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Verify, reject, or request resubmission for a submitted document."""
    return await service.verify_document(current_user, document_id, payload)


@router.get("/documents/file/{filename}")
async def serve_document_file(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """Serve uploaded document file."""
    # Prevent directory traversal
    safe_name = Path(filename).name
    file_path = DOCUMENTS_UPLOAD_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path))


# ─────────────────────────────────────────────────────────────────────────────
# Employee Profile & Onboarding Management (HR & Staff)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/employees", response_model=list[EmployeeResponse])
async def list_employees(
    department: str | None = Query(None),
    employment_status: str | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(require_role(*ALL_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """List employees with task progress and directory filters."""
    return await service.get_employees(
        current_user, department=department, employment_status=employment_status, search=search,
    )


@router.post("/employees", response_model=EmployeeResponse)
async def create_employee_profile(
    payload: EmployeeCreateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Create a new employee profile and initiate onboarding."""
    return await service.create_employee(current_user, payload)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee_details(
    employee_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PostHiringService = Depends(get_service),
):
    """Get full employee details including onboarding tasks."""
    return await service.get_employee_by_id(current_user, employee_id)


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee_profile(
    employee_id: uuid.UUID,
    payload: EmployeeUpdateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Update employee details."""
    return await service.update_employee(current_user, employee_id, payload)


@router.post("/employees/{employee_id}/tasks", response_model=OnboardingTaskResponse)
async def add_onboarding_task(
    employee_id: uuid.UUID,
    payload: OnboardingTaskCreateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Add a new task to an employee's onboarding checklist."""
    return await service.add_onboarding_task(current_user, employee_id, payload)


@router.put("/tasks/{task_id}", response_model=OnboardingTaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: OnboardingTaskUpdateRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Update or mark an onboarding task as complete."""
    return await service.update_onboarding_task(current_user, task_id, payload)


@router.post("/employees/{employee_id}/complete-onboarding", response_model=EmployeeResponse)
async def complete_employee_onboarding(
    employee_id: uuid.UUID,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Complete employee onboarding and transition to Active status."""
    return await service.complete_onboarding(current_user, employee_id)


# ─────────────────────────────────────────────────────────────────────────────
# Admin Statistics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/stats")
async def get_admin_post_hiring_stats(
    current_user: User = Depends(require_role("admin", "organization_admin")),
    service: PostHiringService = Depends(get_service),
):
    """Retrieve organization or platform-wide employee and onboarding stats."""
    return await service.get_admin_stats(current_user)


@router.get("/recruiter/tracker", response_model=list[RecruiterPostHiringCandidateItem])
async def get_recruiter_post_hiring_tracker(
    service: PostHiringService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    """Candidate post-hiring tracking for recruiters and authorized users."""
    return await service.get_recruiter_post_hiring_tracker(current_user)


@router.get("/timeline/{application_id}", response_model=list[PostHiringTimelineEvent])
async def get_post_hiring_timeline(
    application_id: uuid.UUID,
    service: PostHiringService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    """Centralized post-hiring activity timeline for a candidate application."""
    return await service.get_post_hiring_timeline(application_id, current_user)


@router.post("/employees/{employee_id}/confirm-joining", response_model=EmployeeResponse)
async def confirm_employee_joining(
    employee_id: uuid.UUID,
    payload: JoiningConfirmRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Confirm or update candidate joining status before final employee activation."""
    return await service.confirm_joining(current_user, employee_id, payload)


@router.post("/employees/{employee_id}/activate", response_model=EmployeeResponse)
async def activate_employee_profile(
    employee_id: uuid.UUID,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """Officially transition onboarded candidate to Active Employee status."""
    return await service.activate_employee(current_user, employee_id)


@router.post("/candidate/tasks/{task_id}/submit", response_model=OnboardingTaskResponse)
async def candidate_submit_onboarding_task(
    task_id: uuid.UUID,
    payload: CandidateTaskSubmitRequest,
    current_user: User = Depends(get_current_user),
    service: PostHiringService = Depends(get_service),
):
    """Candidate submits onboarding checklist task for HR verification."""
    return await service.candidate_submit_task(current_user, task_id, payload)


@router.post("/tasks/{task_id}/review", response_model=OnboardingTaskResponse)
async def hr_review_onboarding_task(
    task_id: uuid.UUID,
    payload: TaskReviewRequest,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """HR reviews and approves or rejects candidate onboarding task submission."""
    return await service.review_task(current_user, task_id, payload)


@router.post("/tasks/{task_id}/reminder")
async def send_onboarding_task_reminder(
    task_id: uuid.UUID,
    current_user: User = Depends(require_role(*HR_STAFF_ROLES)),
    service: PostHiringService = Depends(get_service),
):
    """HR dispatches reminder notification for an onboarding task."""
    return await service.send_task_reminder(current_user, task_id)
