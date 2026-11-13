"""Integration & unit tests for Post-Hiring, Offer Management, Document Verification and Onboarding."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    ApplicationStatus,
    DocumentType,
    DocumentVerificationStatus,
    EmploymentStatus,
    MembershipStatus,
    OfferStatus,
    OnboardingStatus,
    RoleName,
)
from app.domain.models import (
    CandidateDocument,
    Employee,
    Job,
    JobApplication,
    JobOffer,
    OnboardingTask,
    Organization,
    OrganizationMembership,
    Role,
    User,
    UserRole,
)
from app.domain.post_hiring_schemas import (
    JoiningConfirmRequest,
    CandidateTaskSubmitRequest,
    TaskReviewRequest,
    DocumentVerifyRequest,
    EmployeeCreateRequest,
    JobOfferCandidateResponseRequest,
    JobOfferCreateRequest,
    JobOfferUpdateRequest,
)
from app.services.post_hiring.post_hiring_service import PostHiringService


@pytest.mark.asyncio
async def test_post_hiring_end_to_end_workflow(session: AsyncSession):
    service = PostHiringService(session)

    # 1. Setup Organization, HR User, and Candidate User
    org = Organization(name="HireCraft Test Org", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    session.add(org)
    await session.flush()

    hr_user = User(
        email=f"hr_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="Harish HR",
        is_active=True,
    )
    cand_user = User(
        email=f"cand_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="Gagan B",
        is_active=True,
    )
    session.add_all([hr_user, cand_user])
    await session.flush()

    # Roles & Org Memberships
    hr_role = (await session.execute(select(Role).where(Role.name == "hr_manager"))).scalar_one_or_none()
    if not hr_role:
        hr_role = Role(name="hr_manager", description="HR Manager")
        session.add(hr_role)
        await session.flush()

    cand_role = (await session.execute(select(Role).where(Role.name == "candidate"))).scalar_one_or_none()
    if not cand_role:
        cand_role = Role(name="candidate", description="Candidate")
        session.add(cand_role)
        await session.flush()

    session.add(UserRole(user_id=hr_user.id, role_id=hr_role.id))
    session.add(UserRole(user_id=cand_user.id, role_id=cand_role.id))
    session.add(
        OrganizationMembership(
            organization_id=org.id,
            user_id=hr_user.id,
            role="hr_manager",
            status=MembershipStatus.ACTIVE.value,
        )
    )
    await session.flush()

    # 2. Setup Job and Selected Application
    job = Job(
        organization_id=org.id,
        recruiter_id=hr_user.id,
        title="Senior Cloud Engineer",
        company="HireCraft Technologies",
        employment_type="full_time",
        department="Engineering",
        description="Test role",
        location="Remote",
    )
    session.add(job)
    await session.flush()

    app = JobApplication(
        job_id=job.id,
        candidate_id=cand_user.id,
        status=ApplicationStatus.SELECTED.value,
    )
    session.add(app)
    await session.commit()

    # 3. Test Approved Candidates Listing
    approved = await service.get_approved_candidates(hr_user)
    assert any(a.candidate_id == cand_user.id for a in approved)

    # 4. Test Create Draft Offer
    now = datetime.now(timezone.utc)
    create_req = JobOfferCreateRequest(
        application_id=app.id,
        designation="Senior Cloud Engineer",
        department="Engineering",
        employment_type="full_time",
        offered_salary=120000.0,
        currency="USD",
        work_location="Remote",
        reporting_manager="VP Engineering",
        joining_date=now + timedelta(days=14),
        probation_period_months=3,
        benefits_summary="Health + 401(k)",
        additional_terms="Subject to background check",
        offer_expiry_date=now + timedelta(days=7),
        hr_remarks="Recommended by HR panel",
        send_immediately=False,
    )
    offer_res = await service.create_offer(hr_user, create_req)
    assert offer_res.status == OfferStatus.DRAFT.value
    assert offer_res.offered_salary == 120000.0

    # 5. Test Send Offer
    sent_res = await service.send_offer(hr_user, offer_res.id)
    assert sent_res.status == OfferStatus.SENT.value
    assert sent_res.sent_at is not None

    # 6. Test PDF Generation
    pdf_bytes = await service.generate_offer_pdf(offer_res.id)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500

    # 7. Test Candidate View & Accept Offer
    cand_offers = await service.candidate_get_offers(cand_user)
    assert len(cand_offers) >= 1

    accept_res = await service.candidate_respond_offer(
        cand_user,
        offer_res.id,
        JobOfferCandidateResponseRequest(action="accept", candidate_notes="Delighted to accept!"),
    )
    assert accept_res.status == OfferStatus.ACCEPTED.value

    # 8. Verify Standard Document Requirement Slots Seeded
    cand_docs = await service.get_candidate_documents(cand_user)
    assert len(cand_docs) == 4
    gov_id_doc = next(d for d in cand_docs if d.document_type == DocumentType.GOV_ID.value)
    assert gov_id_doc.status == DocumentVerificationStatus.NOT_SUBMITTED.value

    # 9. Test Candidate Upload Document
    upload_res = await service.candidate_upload_document(
        candidate_user=cand_user,
        application_id=app.id,
        document_type=DocumentType.GOV_ID.value,
        document_title="Passport Photo ID",
        file_bytes=b"%PDF-1.4 test document content",
        file_name="passport_scan.pdf",
        mime_type="application/pdf",
    )
    assert upload_res.status == DocumentVerificationStatus.SUBMITTED.value

    # 10. Test HR Verify Document
    verify_res = await service.verify_document(
        hr_user,
        gov_id_doc.id,
        DocumentVerifyRequest(status="verified", hr_remarks="Passport photo and DOB verified."),
    )
    assert verify_res.status == "verified"
    assert verify_res.verified_by_id == hr_user.id

    # 11. Test Employee Profile Creation (Rule: EMP-XXXX format & Onboarding Status)
    emp_req = EmployeeCreateRequest(
        candidate_id=cand_user.id,
        application_id=app.id,
        designation="Senior Cloud Engineer",
        department="Engineering",
        employment_type="full_time",
        work_location="Remote",
        reporting_manager="VP Engineering",
        joining_date=now + timedelta(days=14),
    )
    emp_res = await service.create_employee(hr_user, emp_req)
    assert emp_res.employee_id.startswith("EMP-")
    assert emp_res.employment_status == EmploymentStatus.ONBOARDING.value
    assert emp_res.onboarding_status == OnboardingStatus.IN_PROGRESS.value
    assert len(emp_res.tasks) >= 5  # Checklist tasks seeded

    # 12. Test Candidate Task Toggle
    first_task = emp_res.tasks[0]
    toggled = await service.candidate_toggle_task(cand_user, first_task.id)
    assert toggled.is_completed is True

    # 13. Test HR Complete Onboarding -> Transition to ACTIVE
    activated_emp = await service.complete_onboarding(hr_user, emp_res.id)
    assert activated_emp.employment_status == EmploymentStatus.ACTIVE.value
    assert activated_emp.onboarding_status == OnboardingStatus.COMPLETED.value
    assert activated_emp.onboarding_completed_at is not None

    # 14. Test HR Post-Hiring Statistics Aggregate
    stats = await service.get_hr_stats(hr_user)
    assert stats.offers_created >= 1
    assert stats.offers_accepted >= 1
    assert stats.active_employees >= 1


@pytest.mark.asyncio
async def test_onboarding_joining_and_activation_workflow(session: AsyncSession):
    service = PostHiringService(session)

    # Setup
    org = Organization(name="Acme Corp", slug=f"acme-{uuid.uuid4().hex[:6]}")
    session.add(org)
    await session.flush()

    hr = User(email=f"hr_{uuid.uuid4().hex[:6]}@acme.com", password_hash="h", full_name="Harish HR", is_active=True)
    cand = User(email=f"cand_{uuid.uuid4().hex[:6]}@acme.com", password_hash="h", full_name="Santhosh", is_active=True)
    session.add_all([hr, cand])
    await session.flush()

    hr_role = (await session.execute(select(Role).where(Role.name == "hr_manager"))).scalar_one_or_none()
    if not hr_role:
        hr_role = Role(name="hr_manager", description="HR Manager")
        session.add(hr_role)
        await session.flush()

    session.add(UserRole(user_id=hr.id, role_id=hr_role.id))
    session.add(OrganizationMembership(organization_id=org.id, user_id=hr.id, role="hr_manager", status="active"))
    await session.flush()

    job = Job(organization_id=org.id, recruiter_id=hr.id, title="Frontend Lead", company="Acme", employment_type="full_time", department="Engineering", description="Role", location="Hybrid")
    session.add(job)
    await session.flush()

    app = JobApplication(job_id=job.id, candidate_id=cand.id, status=ApplicationStatus.SELECTED.value)
    session.add(app)
    await session.commit()

    # 1. Start Onboarding (with Engineering checklist template)
    now = datetime.now(timezone.utc)
    emp_req = EmployeeCreateRequest(
        candidate_id=cand.id,
        application_id=app.id,
        designation="Frontend Lead",
        department="Engineering",
        employment_type="full_time",
        work_location="Hybrid",
        reporting_manager="Director of Tech",
        joining_date=now + timedelta(days=10),
        checklist_template="engineering",
    )
    emp_res = await service.create_employee(hr, emp_req)
    assert emp_res.employment_status == EmploymentStatus.ONBOARDING.value
    assert emp_res.joining_status == "pending"
    assert len(emp_res.tasks) == 9  # 7 base + 2 engineering tasks

    # 2. Candidate submits a task
    cand_task = emp_res.tasks[0]
    sub_res = await service.candidate_submit_task(
        cand, cand_task.id, CandidateTaskSubmitRequest(submission_notes="Acknowledged and signed electronically.")
    )
    assert sub_res.status == "pending_approval"
    assert sub_res.submission_notes == "Acknowledged and signed electronically."

    # 3. HR Reviews and approves the task
    rev_res = await service.review_task(hr, cand_task.id, TaskReviewRequest(status="completed", hr_remarks="Verified digital signature."))
    assert rev_res.status == "completed"
    assert rev_res.is_completed is True
    assert rev_res.hr_remarks == "Verified digital signature."

    # 4. HR Confirms Joining
    confirm_res = await service.confirm_joining(
        hr, emp_res.id, JoiningConfirmRequest(joining_status="confirmed", remarks="All pre-joining background checks clear.")
    )
    assert confirm_res.joining_status == "confirmed"
    assert confirm_res.joining_confirmed_at is not None

    # 5. HR Activates Employee
    activated = await service.activate_employee(hr, emp_res.id)
    assert activated.employment_status == EmploymentStatus.ACTIVE.value
    assert activated.onboarding_status == OnboardingStatus.COMPLETED.value
    assert activated.activated_at is not None
    assert activated.total_tasks == 9
