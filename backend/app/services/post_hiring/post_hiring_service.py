"""Post-Hiring, Offer Management, Document Verification and Employee Onboarding service.







Provides complete business logic, authorization scoping, PDF generation,



and notification dispatching for post-hiring workflows.



"""



from __future__ import annotations







import io



import os



import uuid



from datetime import datetime, timezone



from pathlib import Path



from typing import Any







from reportlab.lib import colors



from reportlab.lib.pagesizes import letter



from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet



from reportlab.pdfgen import canvas

from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle



from sqlalchemy import desc, func, or_, select



from sqlalchemy.ext.asyncio import AsyncSession



from sqlalchemy.orm import selectinload







from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError



from app.core.logging import get_logger



from app.domain.enums import (



    ApplicationStatus,



    DocumentType,



    DocumentVerificationStatus,



    EmploymentStatus,



    MembershipStatus,



    NotificationType,



    OfferStatus,



    OnboardingStatus,



    OnboardingTaskCategory,



)



from app.domain.models import (
    AuditLog,



        CandidateDocument,

    CandidateProfile,



    Employee,



    Interview,



    InterviewScorecard,



    Job,



    JobApplication,



    JobOffer,



    Notification,



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
    RecruiterPostHiringCandidateItem,
    PostHiringTimelineEvent,




    ApprovedCandidateSummary,



    CandidateDocumentResponse,



    DocumentVerifyRequest,



    EmployeeCreateRequest,



    EmployeeResponse,



    EmployeeUpdateRequest,



    JobOfferCandidateResponseRequest,



    JobOfferCreateRequest,



    JobOfferResponse,



    JobOfferUpdateRequest,



    OnboardingTaskCreateRequest,



    OnboardingTaskResponse,



    OnboardingTaskUpdateRequest,



    PostHiringStatsResponse,



    RecentHiringActivity,



    UpcomingJoining,



)



from app.services.email_service import EmailService







logger = get_logger(__name__)







DOCUMENTS_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "documents"











def _normalize_dt(dt: datetime | None) -> datetime:



    if not dt:



        return datetime.min.replace(tzinfo=timezone.utc)



    if dt.tzinfo is None:



        return dt.replace(tzinfo=timezone.utc)



    return dt.astimezone(timezone.utc)











def number_to_words(n: float | int) -> str:

    n = int(round(n))

    if n == 0:

        return "Zero Only"

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",

            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",

            "Seventeen", "Eighteen", "Nineteen"]

    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    

    def helper(num: int) -> str:

        if num == 0:

            return ""

        elif num < 20:

            return ones[num] + " "

        elif num < 100:

            return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "") + " "

        elif num < 1000:

            return ones[num // 100] + " Hundred " + helper(num % 100)

        elif num < 1000000:

            return helper(num // 1000) + "Thousand " + helper(num % 1000)

        else:

            return helper(num // 1000000) + "Million " + helper(num % 1000000)

    

    words = helper(n).strip()

    return f"{words} Only"





class OfferNumberedCanvas(canvas.Canvas):

    offer_ref_str: str = "HC-2025-0012"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._saved_page_states = []



    def showPage(self):

        self._saved_page_states.append(dict(self.__dict__))

        self._startPage()



    def save(self):

        num_pages = len(self._saved_page_states)

        for state in self._saved_page_states:

            self.__dict__.update(state)

            self.draw_page_decorations(num_pages)

            super().showPage()

        super().save()



    def draw_page_decorations(self, page_count):

        self.saveState()

        self.setFillColor(colors.HexColor("#0B2545"))

        self.rect(36, 18, 540, 18, fill=True, stroke=False)

        self.setFillColor(colors.white)

        self.setFont("Helvetica-Bold", 7.5)

        self.drawString(44, 23, f"HireCraft AI | Offer Reference No: {getattr(self, 'offer_ref_str', 'HC-2025-0012')}")

        self.drawRightString(568, 23, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()





class PostHiringService:



    def __init__(self, session: AsyncSession) -> None:



        self.session = session



        self.email_service = EmailService()



        DOCUMENTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)







    # ─────────────────────────────────────────────────────────────────────────



    # Tenant Scope & Authorization Helpers



    # ─────────────────────────────────────────────────────────────────────────







    async def get_user_roles(self, user: User) -> set[str]:



        roles: set[str] = set()



        if "roles" in user.__dict__:



            for ur in user.__dict__["roles"] or []:



                if hasattr(ur, "role") and ur.role is not None:



                    roles.add(ur.role.name)



        if not roles:



            stmt = (



                select(Role.name)



                .join(UserRole, UserRole.role_id == Role.id)



                .where(UserRole.user_id == user.id)



            )



            roles = set((await self.session.execute(stmt)).scalars().all())



        return roles







    async def get_user_org_ids(self, user: User) -> list[uuid.UUID] | None:



        """Returns list of authorized organization IDs, or None if global admin."""



        roles = await self.get_user_roles(user)



        if "admin" in roles:



            return None







        stmt = select(OrganizationMembership.organization_id).where(



            OrganizationMembership.user_id == user.id,



            OrganizationMembership.status == MembershipStatus.ACTIVE.value,



        )



        return list((await self.session.execute(stmt)).scalars().all())







    async def get_primary_org_id(self, user: User) -> uuid.UUID:



        """Returns caller's primary organization ID."""



        org_ids = await self.get_user_org_ids(user)



        if org_ids:



            return org_ids[0]







        # Fallback to any organization or default



        stmt = select(Organization.id).limit(1)



        fallback = (await self.session.execute(stmt)).scalar_one_or_none()



        if not fallback:



            raise ValidationError("No active organization found for user.")



        return fallback







    # ─────────────────────────────────────────────────────────────────────────



    # Notification & Audit Dispatcher



    # ─────────────────────────────────────────────────────────────────────────







    async def dispatch_notification(



        self,



        user_id: uuid.UUID,



        title: str,



        message: str,



        notification_type: str,



        action_link: str | None = None,



    ) -> Notification:



        notif = Notification(



            user_id=user_id,



            title=title,



            message=message,



            notification_type=notification_type,



            action_link=action_link,



            is_read=False,



        )



        self.session.add(notif)



        return notif







    # ─────────────────────────────────────────────────────────────────────────



    # HR & Admin Statistics



    # ─────────────────────────────────────────────────────────────────────────







    async def get_hr_stats(self, user: User) -> PostHiringStatsResponse:



        org_ids = await self.get_user_org_ids(user)







        # Selected candidates query



        app_q = select(func.count(JobApplication.id)).join(Job, JobApplication.job_id == Job.id)



        if org_ids is not None:



            app_q = app_q.where(Job.organization_id.in_(org_ids))



        app_q = app_q.where(



            JobApplication.status.in_([



                ApplicationStatus.SELECTED.value,



                ApplicationStatus.OFFERED.value,



                ApplicationStatus.HIRED.value,



            ])



        )



        total_selected = (await self.session.execute(app_q)).scalar_one() or 0







        # Offers queries



        offers_base = select(JobOffer)



        if org_ids is not None:



            offers_base = offers_base.where(JobOffer.organization_id.in_(org_ids))



        all_offers = (await self.session.execute(offers_base)).scalars().all()







        offers_created = len(all_offers)



        offers_pending = sum(1 for o in all_offers if o.status in [OfferStatus.SENT.value, OfferStatus.VIEWED.value, "pending"])



        offers_accepted = sum(1 for o in all_offers if o.status == OfferStatus.ACCEPTED.value)



        offers_declined = sum(1 for o in all_offers if o.status == OfferStatus.DECLINED.value)







        # Pending documents



        docs_q = select(func.count(CandidateDocument.id))



        if org_ids is not None:



            docs_q = docs_q.where(CandidateDocument.organization_id.in_(org_ids))



        docs_q = docs_q.where(CandidateDocument.status.in_([



            DocumentVerificationStatus.SUBMITTED.value,



            DocumentVerificationStatus.UNDER_REVIEW.value,



            "resubmission_required",



        ]))



        docs_pending = (await self.session.execute(docs_q)).scalar_one() or 0







        # Employees



        emp_q = select(Employee)



        if org_ids is not None:



            emp_q = emp_q.where(Employee.organization_id.in_(org_ids))



        employees = (await self.session.execute(emp_q)).scalars().all()







        employees_onboarding = sum(1 for e in employees if e.employment_status == EmploymentStatus.ONBOARDING.value)



        active_employees = sum(1 for e in employees if e.employment_status == EmploymentStatus.ACTIVE.value)







        # Upcoming joinings



        now = datetime.now(timezone.utc)



        upcoming_joinings: list[UpcomingJoining] = []



        for emp in employees:



            if emp.joining_date:



                # Load candidate user details



                cand = await self.session.get(User, emp.user_id)



                upcoming_joinings.append(



                    UpcomingJoining(



                        employee_id=emp.employee_id,



                        candidate_name=cand.full_name if cand else "Candidate",



                        candidate_email=cand.email if cand else "",



                        designation=emp.designation,



                        department=emp.department,



                        joining_date=emp.joining_date,



                        status=emp.employment_status,



                    )



                )



        # Also include accepted offers that don't have employee records yet



        for off in all_offers:



            if off.status == OfferStatus.ACCEPTED.value:



                # check if employee already exists for this application



                exists = any(e.application_id == off.application_id for e in employees)



                if not exists and off.joining_date:



                    cand = await self.session.get(User, off.candidate_id)



                    upcoming_joinings.append(



                        UpcomingJoining(



                            employee_id=None,



                            candidate_name=cand.full_name if cand else "Candidate",



                            candidate_email=cand.email if cand else "",



                            designation=off.designation,



                            department=off.department,



                            joining_date=off.joining_date,



                            status="offer_accepted",



                        )



                    )



        upcoming_joinings.sort(key=lambda x: _normalize_dt(x.joining_date))







        # Recent activities



        recent_activities: list[RecentHiringActivity] = []



        for off in sorted(all_offers, key=lambda x: _normalize_dt(x.updated_at), reverse=True)[:5]:



            cand = await self.session.get(User, off.candidate_id)



            cname = cand.full_name if cand else "Candidate"



            if off.status == OfferStatus.ACCEPTED.value:



                recent_activities.append(



                    RecentHiringActivity(



                        id=f"offer-acc-{off.id}",



                        title="Offer Accepted",



                        description=f"{cname} accepted offer for {off.designation}",



                        activity_type="offer_accepted",



                        timestamp=off.responded_at or off.updated_at,



                        badge_variant="success",



                    )



                )



            elif off.status == OfferStatus.SENT.value:



                recent_activities.append(



                    RecentHiringActivity(



                        id=f"offer-sent-{off.id}",



                        title="Offer Sent",



                        description=f"Official offer sent to {cname} ({off.designation})",



                        activity_type="offer_sent",



                        timestamp=off.sent_at or off.created_at,



                        badge_variant="primary",



                    )



                )



            elif off.status == OfferStatus.DECLINED.value:



                recent_activities.append(



                    RecentHiringActivity(



                        id=f"offer-dec-{off.id}",



                        title="Offer Declined",



                        description=f"{cname} declined offer for {off.designation}",



                        activity_type="offer_declined",



                        timestamp=off.responded_at or off.updated_at,



                        badge_variant="destructive",



                    )



                )







        return PostHiringStatsResponse(



            total_selected_candidates=total_selected,



            offers_created=offers_created,



            offers_pending=offers_pending,



            offers_accepted=offers_accepted,



            offers_declined=offers_declined,



            documents_pending_verification=docs_pending,



            employees_onboarding=employees_onboarding,



            active_employees=active_employees,



            upcoming_joinings=upcoming_joinings[:8],



            recent_activities=recent_activities,



        )







    # ─────────────────────────────────────────────────────────────────────────



    # Approved Candidates (Eligible for Offer Creation)



    # ─────────────────────────────────────────────────────────────────────────







    async def get_approved_candidates(self, user: User) -> list[ApprovedCandidateSummary]:



        org_ids = await self.get_user_org_ids(user)







        stmt = (



            select(JobApplication, Job, User)



            .join(Job, JobApplication.job_id == Job.id)



            .join(User, JobApplication.candidate_id == User.id)



        )



        if org_ids is not None:



            stmt = stmt.where(Job.organization_id.in_(org_ids))







        # Include applications that are selected, offered, or hired



        stmt = stmt.where(



            JobApplication.status.in_([



                ApplicationStatus.SELECTED.value,



                ApplicationStatus.OFFERED.value,



                ApplicationStatus.HIRED.value,



            ])



        ).order_by(desc(JobApplication.updated_at))







        results = (await self.session.execute(stmt)).all()







        output: list[ApprovedCandidateSummary] = []



        for app, job, cand in results:



            # Check existing offer



            off_stmt = select(JobOffer).where(JobOffer.application_id == app.id).order_by(desc(JobOffer.created_at)).limit(1)



            offer = (await self.session.execute(off_stmt)).scalar_one_or_none()







            # Check interview scores



            sc_stmt = (



                select(InterviewScorecard, Interview)



                .join(Interview, InterviewScorecard.interview_id == Interview.id)



                .where(Interview.application_id == app.id)



            )



            sc_results = (await self.session.execute(sc_stmt)).all()



            rec_score = next((sc.overall_score for sc, iv in sc_results if getattr(iv, "interview_stage", "") == "recruiter"), None)



            hr_score = next((sc.overall_score for sc, iv in sc_results if getattr(iv, "interview_stage", "") == "hr"), None)







            # Check decision from application columns



            decision_text = app.decision_reason or app.decision_comment or app.status







            output.append(



                ApprovedCandidateSummary(



                    application_id=app.id,



                    candidate_id=cand.id,



                    candidate_name=cand.full_name,



                    candidate_email=cand.email,



                    job_id=job.id,



                    job_title=job.title,



                    department=job.department or "Engineering",



                    application_status=app.status,



                    has_offer=offer is not None,



                    offer_id=offer.id if offer else None,



                    offer_status=offer.status if offer else None,



                    recruiter_score=rec_score,



                    hr_score=hr_score,



                    decision=decision_text,



                )



            )







        return output







    # ─────────────────────────────────────────────────────────────────────────



    # Offer Management Operations



    # ─────────────────────────────────────────────────────────────────────────







    async def create_offer(self, user: User, data: JobOfferCreateRequest) -> JobOfferResponse:



        app = await self.session.get(JobApplication, data.application_id)



        if not app:



            raise NotFoundError("Job application not found")







        job = await self.session.get(Job, app.job_id)



        if not job:



            raise NotFoundError("Associated job not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and job.organization_id not in org_ids:



            raise ForbiddenError("You do not have access to manage offers for this job.")







        status = OfferStatus.SENT.value if data.send_immediately else OfferStatus.DRAFT.value



        sent_at = datetime.now(timezone.utc) if data.send_immediately else None







        offer = JobOffer(



            application_id=app.id,



            candidate_id=app.candidate_id,



            job_id=job.id,



            organization_id=job.organization_id,



            created_by_id=user.id,



            designation=data.designation,



            department=data.department,



            employment_type=data.employment_type,



            offered_salary=data.offered_salary,



            currency=data.currency,



            work_location=data.work_location,



            reporting_manager=data.reporting_manager,



            joining_date=data.joining_date,



            probation_period_months=data.probation_period_months,



            benefits_summary=data.benefits_summary,



            additional_terms=data.additional_terms,



            offer_expiry_date=data.offer_expiry_date,



            hr_remarks=data.hr_remarks,



            status=status,



            sent_at=sent_at,



        )



        self.session.add(offer)







        if data.send_immediately:



            app.status = ApplicationStatus.OFFERED.value



            await self._on_offer_sent(offer, job, app)







        await self.session.commit()



        await self.session.refresh(offer)



        return await self._to_offer_response(offer)







    async def get_offers(



        self, user: User, status: str | None = None,



    ) -> list[JobOfferResponse]:



        org_ids = await self.get_user_org_ids(user)







        stmt = select(JobOffer).order_by(desc(JobOffer.created_at))



        if org_ids is not None:



            stmt = stmt.where(JobOffer.organization_id.in_(org_ids))



        if status:



            stmt = stmt.where(JobOffer.status == status)







        offers = (await self.session.execute(stmt)).scalars().all()



        return [await self._to_offer_response(o) for o in offers]







    async def get_offer_by_id(self, user: User, offer_id: uuid.UUID) -> JobOfferResponse:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer:



            raise NotFoundError("Offer not found")







        org_ids = await self.get_user_org_ids(user)



        roles = await self.get_user_roles(user)



        if "candidate" in roles and offer.candidate_id != user.id:



            raise ForbiddenError("Access denied to this offer.")



        if "candidate" not in roles and org_ids is not None and offer.organization_id not in org_ids:



            raise ForbiddenError("Access denied to this offer.")







        return await self._to_offer_response(offer)







    async def update_offer(



        self, user: User, offer_id: uuid.UUID, data: JobOfferUpdateRequest,



    ) -> JobOfferResponse:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer:



            raise NotFoundError("Offer not found")







        if offer.status in [OfferStatus.ACCEPTED.value, OfferStatus.DECLINED.value]:



            raise ValidationError("Cannot edit an offer that has already been responded to.")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and offer.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        for key, value in data.model_dump(exclude_unset=True).items():



            if value is not None:



                setattr(offer, key, value)







        await self.session.commit()



        await self.session.refresh(offer)



        return await self._to_offer_response(offer)







    async def send_offer(self, user: User, offer_id: uuid.UUID) -> JobOfferResponse:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer:



            raise NotFoundError("Offer not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and offer.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        offer.status = OfferStatus.SENT.value



        offer.sent_at = datetime.now(timezone.utc)







        app = await self.session.get(JobApplication, offer.application_id)



        if app:



            app.status = ApplicationStatus.OFFERED.value







        job = await self.session.get(Job, offer.job_id)



        if job and app:



            await self._on_offer_sent(offer, job, app)







        await self.session.commit()



        await self.session.refresh(offer)



        return await self._to_offer_response(offer)







    async def withdraw_offer(self, user: User, offer_id: uuid.UUID) -> JobOfferResponse:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer:



            raise NotFoundError("Offer not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and offer.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        offer.status = OfferStatus.WITHDRAWN.value



        await self.dispatch_notification(



            user_id=offer.candidate_id,



            title="Offer Withdrawn",



            message=f"The job offer for {offer.designation} has been withdrawn by HR.",



            notification_type=NotificationType.OFFER_DECLINED.value,



            action_link="/candidate/offers-onboarding",



        )







        await self.session.commit()



        await self.session.refresh(offer)



        return await self._to_offer_response(offer)







    async def _on_offer_sent(self, offer: JobOffer, job: Job, app: JobApplication) -> None:



        cand = await self.session.get(User, offer.candidate_id)



        org = await self.session.get(Organization, offer.organization_id)



        org_name = org.name if org else "HireCraft AI Partner"







        await self.dispatch_notification(



            user_id=offer.candidate_id,



            title=f"Official Job Offer: {offer.designation}",



            message=f"Congratulations! You have received an official job offer for {offer.designation} at {org_name}. Please review and respond.",



            notification_type=NotificationType.OFFER_SENT.value,



            action_link="/candidate/offers-onboarding",



        )







        if cand and cand.email:



            try:



                self.email_service.send_html(



                    to_email=cand.email,



                    subject=f"Job Offer: {offer.designation} at {org_name}",



                    html_body=(



                        f"<h2>Congratulations {cand.full_name}!</h2>"



                        f"<p>We are delighted to extend you an offer for the position of <strong>{offer.designation}</strong> at <strong>{org_name}</strong>.</p>"



                        f"<p><strong>Salary:</strong> {offer.currency} {offer.offered_salary:,.2f}<br/>"



                        f"<strong>Joining Date:</strong> {offer.joining_date.strftime('%B %d, %Y')}<br/>"



                        f"<strong>Location:</strong> {offer.work_location}</p>"



                        f"<p>Please log in to your HireCraft portal to review the full offer letter and confirm your acceptance.</p>"



                    ),



                )



            except Exception as e:



                logger.warning("Failed to send offer email: %s", e)







    # ─────────────────────────────────────────────────────────────────────────



    # Candidate Offer Interactions



    # ─────────────────────────────────────────────────────────────────────────







    async def candidate_get_offers(self, candidate_user: User) -> list[JobOfferResponse]:



        stmt = select(JobOffer).where(



            JobOffer.candidate_id == candidate_user.id,



            JobOffer.status != OfferStatus.DRAFT.value,



        ).order_by(desc(JobOffer.created_at))







        offers = (await self.session.execute(stmt)).scalars().all()







        # Mark any newly viewed offer



        changed = False



        for o in offers:



            if o.status == OfferStatus.SENT.value and not o.viewed_at:



                o.status = OfferStatus.VIEWED.value



                o.viewed_at = datetime.now(timezone.utc)



                changed = True



        if changed:



            await self.session.flush()



            for o in offers:



                await self.session.refresh(o)







        return [await self._to_offer_response(o) for o in offers]







    async def candidate_respond_offer(



        self,



        candidate_user: User,



        offer_id: uuid.UUID,



        req: JobOfferCandidateResponseRequest,



    ) -> JobOfferResponse:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer or offer.candidate_id != candidate_user.id:



            raise NotFoundError("Offer not found")







        if offer.status in [OfferStatus.ACCEPTED.value, OfferStatus.DECLINED.value]:



            raise ValidationError(f"This offer has already been {offer.status}.")







        now = datetime.now(timezone.utc)



        if offer.offer_expiry_date:



            expiry = _normalize_dt(offer.offer_expiry_date)



            if expiry < now:



                offer.status = OfferStatus.EXPIRED.value



                await self.session.commit()



                raise ValidationError("This offer has expired. Please contact HR.")







        offer.responded_at = now



        offer.candidate_notes = req.candidate_notes







        app = await self.session.get(JobApplication, offer.application_id)



        cand_name = candidate_user.full_name







        if req.action == "accept":



            offer.status = OfferStatus.ACCEPTED.value



            if app:



                app.status = ApplicationStatus.SELECTED.value







            # Notify HR creator



            if offer.created_by_id:



                await self.dispatch_notification(



                    user_id=offer.created_by_id,



                    title="Offer Accepted!",



                    message=f"{cand_name} has accepted the offer for {offer.designation}.",



                    notification_type=NotificationType.OFFER_ACCEPTED.value,



                    action_link=f"/hr/offers?id={offer.id}",



                )







            # Auto-seed standard document requirement slots for this candidate



            await self._seed_standard_documents_for_candidate(offer)







            # Notify candidate on next steps (document submission)



            await self.dispatch_notification(



                user_id=candidate_user.id,



                title="Offer Accepted - Document Submission Required",



                message="Congratulations on accepting the offer! Please upload your identity and verification documents to proceed with onboarding.",



                notification_type=NotificationType.OFFER_ACCEPTED.value,



                action_link="/candidate/offers-onboarding",



            )



        else:



            offer.status = OfferStatus.DECLINED.value



            offer.decline_reason = req.decline_reason



            if offer.created_by_id:



                await self.dispatch_notification(



                    user_id=offer.created_by_id,



                    title="Offer Declined",



                    message=f"{cand_name} declined the offer for {offer.designation}. Reason: {req.decline_reason or 'No reason provided'}",



                    notification_type=NotificationType.OFFER_DECLINED.value,



                    action_link=f"/hr/offers?id={offer.id}",



                )







        await self.session.commit()



        await self.session.refresh(offer)



        return await self._to_offer_response(offer)







    async def candidate_clarify_offer(



        self, candidate_user: User, offer_id: uuid.UUID, question: str,



    ) -> dict[str, str]:



        offer = await self.session.get(JobOffer, offer_id)



        if not offer or offer.candidate_id != candidate_user.id:



            raise NotFoundError("Offer not found")







        cand_name = candidate_user.full_name



        if offer.created_by_id:



            await self.dispatch_notification(



                user_id=offer.created_by_id,



                title=f"Offer Query: {cand_name}",



                message=f"{cand_name} requested clarification on the offer for {offer.designation}: \"{question}\"",



                notification_type=NotificationType.GENERAL.value,



                action_link=f"/hr/offers?id={offer.id}",



            )



            await self.session.commit()







        return {"status": "clarification_sent", "message": "Your question has been sent to the HR team."}







    async def _seed_standard_documents_for_candidate(self, offer: JobOffer) -> None:



        required_types = [



            (DocumentType.GOV_ID.value, "Government Photo ID (Passport / Driving License / National ID)"),



            (DocumentType.ADDRESS_PROOF.value, "Proof of Address (Utility Bill / Bank Statement)"),



            (DocumentType.EDUCATION.value, "Educational Degree Certificate & Transcripts"),



            (DocumentType.PREVIOUS_EMPLOYMENT.value, "Previous Relieving Letter & Experience Certificates"),



        ]



        for dtype, dtitle in required_types:



            stmt = select(CandidateDocument).where(



                CandidateDocument.application_id == offer.application_id,



                CandidateDocument.document_type == dtype,



            )



            existing = (await self.session.execute(stmt)).scalar_one_or_none()



            if not existing:



                doc = CandidateDocument(



                    application_id=offer.application_id,



                    candidate_id=offer.candidate_id,



                    organization_id=offer.organization_id,



                    document_type=dtype,



                    document_title=dtitle,



                    status=DocumentVerificationStatus.NOT_SUBMITTED.value,



                )



                self.session.add(doc)







    # ─────────────────────────────────────────────────────────────────────────



    # Official Offer Letter PDF Generation (ReportLab)



    # ─────────────────────────────────────────────────────────────────────────







    async def generate_offer_pdf(self, offer_id: uuid.UUID) -> bytes:

        offer = await self.session.get(JobOffer, offer_id)

        if not offer:

            raise NotFoundError("Offer not found")



        cand = await self.session.get(User, offer.candidate_id)

        org = await self.session.get(Organization, offer.organization_id)

        job = await self.session.get(Job, offer.job_id)



        cand_prof_stmt = select(CandidateProfile).where(CandidateProfile.user_id == offer.candidate_id)

        cand_prof = (await self.session.execute(cand_prof_stmt)).scalar_one_or_none()



        org_name = (
            (org.name if org and org.name else None)
            or (job.company if job and getattr(job, "company", None) else None)
            or (offer.department if offer.department else None)
            or "Company Name"
        )
        company_initial = org_name[0].upper() if org_name else "C"
        company_domain = "".join(c for c in org_name.lower() if c.isalnum()) + ".com"

        cand_name = cand.full_name if cand else "Candidate"

        cand_first_name = cand.full_name.split()[0] if cand and cand.full_name else "Candidate"

        cand_email = cand.email if cand else ""

        cand_location = (cand_prof.location if cand_prof and cand_prof.location else None) or offer.work_location



        offered = float(offer.offered_salary) if offer.offered_salary else 0.0

        base_sal = getattr(offer, "base_salary", None)

        if base_sal is None:

            base_sal = round(offered * 0.8235, 2)

        var_comp = getattr(offer, "variable_compensation", None)

        if var_comp is None:

            var_comp = round(offered * 0.0588, 2)

        allow = getattr(offer, "allowances", None)

        if allow is None:

            allow = round(offered - (base_sal + var_comp), 2)

        var_pct = int(round((var_comp / offered) * 100)) if offered > 0 else 0

        ref_no = getattr(offer, "offer_reference_no", None) or f"HC-{offer.created_at.year if offer.created_at else 2026}-{str(offer.id)[-4:].upper()}"

        issue_date = (offer.sent_at or offer.created_at or datetime.now()).strftime("%b %d, %Y")

        work_arr = getattr(offer, "work_arrangement", None) or "Hybrid"

        salary_words = number_to_words(offered)



        buf = io.BytesIO()

        doc = SimpleDocTemplate(

            buf,

            pagesize=letter,

            leftMargin=36,

            rightMargin=36,

            topMargin=32,

            bottomMargin=44,

        )



        styles = getSampleStyleSheet()

        story = []



        # 1. Header (Company branding + Address)
        logo_cell = Table(
            [[Paragraph(f'<font size="18" color="white"><b>{company_initial}</b></font>', styles['Normal'])]],
            colWidths=[36],
            rowHeights=[36]
        )
        logo_cell.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#2563EB')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        header_data = [
            [
                logo_cell,
                Paragraph(f'<font size="18" color="#0B2545"><b>{org_name}</b></font><br/><font size="8.5" color="#2563EB"><b>{offer.department or "Official Employment Offer"}</b></font>', styles['Normal']),
                Paragraph(f'<para align="right"><font size="8" color="#334155">123 Tech Park, Whitefield<br/>Bengaluru, Karnataka - 560066, India<br/>www.{company_domain} | hr@{company_domain}</font></para>', styles['Normal'])
            ]
        ]

        ht = Table(header_data, colWidths=[44, 226, 270])

        ht.setStyle(TableStyle([

            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

            ('BOTTOMPADDING', (0,0), (-1,-1), 0),

            ('TOPPADDING', (0,0), (-1,-1), 0),

            ('LEFTPADDING', (0,0), (-1,-1), 0),

            ('RIGHTPADDING', (0,0), (-1,-1), 0),

        ]))

        story.append(ht)

        story.append(Spacer(1, 8))



        # 2. Main Title Banner (Full-width dark navy #0B2545)

        b_data = [[Paragraph('<para align="center"><font size="13" color="white"><b>OFFER OF EMPLOYMENT</b></font></para>', styles['Normal'])]]

        bt = Table(b_data, colWidths=[540])

        bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 5),

            ('LEFTPADDING', (0,0), (-1,-1), 0),

            ('RIGHTPADDING', (0,0), (-1,-1), 0),

        ]))

        story.append(bt)

        story.append(Spacer(1, 7))



        # 3. Meta: Reference No & Date

        meta_data = [

            [

                Paragraph(f'<font size="8.5" color="#0F172A"><b>Offer Reference No: {ref_no}</b><br/><b>PRIVATE & CONFIDENTIAL</b></font>', styles['Normal']),

                Paragraph(f'<para align="right"><font size="8.5" color="#0F172A"><b>Date of Issue: {issue_date}</b></font></para>', styles['Normal']),

            ]

        ]

        mt = Table(meta_data, colWidths=[320, 220])

        mt.setStyle(TableStyle([

            ('VALIGN', (0,0), (-1,-1), 'TOP'),

            ('LEFTPADDING', (0,0), (-1,-1), 0),

            ('RIGHTPADDING', (0,0), (-1,-1), 0),

            ('TOPPADDING', (0,0), (-1,-1), 0),

            ('BOTTOMPADDING', (0,0), (-1,-1), 0),

        ]))

        story.append(mt)

        story.append(Spacer(1, 7))



        # 4. To, Addressee

        to_p = Paragraph(f'<font size="8.5" color="#0F172A"><b>To,</b><br/><b>{cand_name}</b><br/>{cand_email}<br/>{cand_location}</font>', styles['Normal'])

        story.append(to_p)

        story.append(Spacer(1, 7))



        # 5. Salutation & Opening Paragraph

        dear_p = Paragraph(f'<font size="8.5" color="#1E293B"><b>Dear {cand_first_name},</b><br/><br/>We are pleased to offer you the position of <b>{offer.designation}</b> at <b>{org_name}</b>, in the <b>{offer.department}</b> department. We look forward to welcoming you to our organization and being a part of our growing team.</font>', styles['Normal'])

        story.append(dear_p)

        story.append(Spacer(1, 9))



        # 6. Section 1 Banner: 1. Employment Details

        s1_b = [[Paragraph('<font size="9" color="white"><b>1. Employment Details</b></font>', styles['Normal'])]]

        s1_bt = Table(s1_b, colWidths=[540])

        s1_bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(s1_bt)



        rep_mgr = offer.reporting_manager or "Anita Verma (Engineering Manager)"

        emp_data = [

            [Paragraph('<b>Designation</b>', styles['Normal']), Paragraph(offer.designation, styles['Normal'])],

            [Paragraph('<b>Department</b>', styles['Normal']), Paragraph(offer.department, styles['Normal'])],

            [Paragraph('<b>Employment Type</b>', styles['Normal']), Paragraph(offer.employment_type.replace('_', ' ').title(), styles['Normal'])],

            [Paragraph('<b>Work Location</b>', styles['Normal']), Paragraph(offer.work_location, styles['Normal'])],

            [Paragraph('<b>Work Arrangement</b>', styles['Normal']), Paragraph(work_arr, styles['Normal'])],

            [Paragraph('<b>Reporting Manager</b>', styles['Normal']), Paragraph(rep_mgr, styles['Normal'])],

            [Paragraph('<b>Joining Date</b>', styles['Normal']), Paragraph(offer.joining_date.strftime('%b %d, %Y'), styles['Normal'])],

            [Paragraph('<b>Probation Period</b>', styles['Normal']), Paragraph(f'{offer.probation_period_months} months', styles['Normal'])],

        ]

        et = Table(emp_data, colWidths=[200, 340])

        et.setStyle(TableStyle([

            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),

            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),

            ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#FFFFFF')),

            ('TOPPADDING', (0,0), (-1,-1), 3),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

            ('RIGHTPADDING', (0,0), (-1,-1), 8),

            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        ]))

        story.append(et)

        story.append(Spacer(1, 9))



        # 7. Section 2 Banner: 2. Compensation Details

        s2_b = [[Paragraph('<font size="9" color="white"><b>2. Compensation Details</b></font>', styles['Normal'])]]

        s2_bt = Table(s2_b, colWidths=[540])

        s2_bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(s2_bt)



        comp_data = [

            [

                Paragraph(f'<font size="8" color="#475569">Total Annual Compensation</font><br/><br/><font size="16" color="#0B2545"><b>{offer.currency} {offered:,.0f}</b></font><br/><br/><font size="7.5" color="#64748B"><i>({salary_words})</i></font>', styles['Normal']),

                Paragraph(f'<font size="8.5" color="#0F172A"><b>Base Salary</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: {offer.currency} {base_sal:,.0f}<br/><br/><b>Variable Compensation</b>&nbsp;: {offer.currency} {var_comp:,.0f} ({var_pct}%)<br/><br/><b>Allowances</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: {offer.currency} {allow:,.0f}<br/><br/><b>Currency</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: {offer.currency}</font>', styles['Normal']),

            ]

        ]

        ct = Table(comp_data, colWidths=[240, 300])

        ct.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EBF3FC')),

            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#BFDBFE')),

            ('LINEBEFORE', (1,0), (1,-1), 0.5, colors.HexColor('#BFDBFE')),

            ('TOPPADDING', (0,0), (-1,-1), 8),

            ('BOTTOMPADDING', (0,0), (-1,-1), 8),

            ('LEFTPADDING', (0,0), (-1,-1), 12),

            ('RIGHTPADDING', (0,0), (-1,-1), 12),

            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        ]))

        story.append(ct)



        # 8. Page 2 (Benefits, Terms, and Signatures)

        story.append(PageBreak())



        # Page 2 Mini Header

        p2_h = [

            [

                Paragraph(f'<font size="11" color="#0B2545"><b>{org_name}</b> &bull; Offer Letter</font>', styles['Normal']),

                Paragraph(f'<para align="right"><font size="8.5" color="#475569">Offer Reference No: {ref_no}</font></para>', styles['Normal'])

            ]

        ]

        p2_ht = Table(p2_h, colWidths=[270, 270])

        p2_ht.setStyle(TableStyle([

            ('LEFTPADDING', (0,0), (-1,-1), 0),

            ('RIGHTPADDING', (0,0), (-1,-1), 0),

            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),

            ('BOTTOMPADDING', (0,0), (-1,-1), 5),

        ]))

        story.append(p2_ht)

        story.append(Spacer(1, 10))



        # Section 3: Benefits & Perks

        s3_b = [[Paragraph('<font size="9" color="white"><b>3. Benefits & Perks</b></font>', styles['Normal'])]]

        s3_bt = Table(s3_b, colWidths=[540])

        s3_bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(s3_bt)



        other_ben = offer.benefits_summary or "Performance bonuses, home workspace setup stipend, and wellness allowance."

        ben_data = [

            [Paragraph('<b>Health Insurance</b>', styles['Normal']), Paragraph('Comprehensive medical, dental, and vision insurance for employee and immediate family members.', styles['Normal'])],

            [Paragraph('<b>Paid Leave</b>', styles['Normal']), Paragraph('24 days of paid annual vacation plus company holidays and sick leave privileges.', styles['Normal'])],

            [Paragraph('<b>Learning Support</b>', styles['Normal']), Paragraph('Annual educational stipend and certification reimbursement program.', styles['Normal'])],

            [Paragraph('<b>Retirement Benefits</b>', styles['Normal']), Paragraph('Company matched 401(k) / Provident Fund retirement savings program.', styles['Normal'])],

            [Paragraph('<b>Other Benefits</b>', styles['Normal']), Paragraph(other_ben, styles['Normal'])],

        ]

        btab = Table(ben_data, colWidths=[160, 380])

        btab.setStyle(TableStyle([

            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),

            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),

            ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#FFFFFF')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

            ('RIGHTPADDING', (0,0), (-1,-1), 8),

            ('VALIGN', (0,0), (-1,-1), 'TOP'),

        ]))

        story.append(btab)

        story.append(Spacer(1, 12))



        # Section 4: Terms & Conditions

        s4_b = [[Paragraph('<font size="9" color="white"><b>4. Terms & Conditions</b></font>', styles['Normal'])]]

        s4_bt = Table(s4_b, colWidths=[540])

        s4_bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(s4_bt)



        terms_data = [

            [Paragraph('<b>Verification Contingency:</b> This offer is contingent upon successful verification of credentials, background checks, and identity documents.', styles['Normal'])],

            [Paragraph('<b>Confidentiality:</b> You agree to execute and abide by the company Non-Disclosure and Intellectual Property Assignment Agreement.', styles['Normal'])],

            [Paragraph('<b>Notice Period:</b> A standard 60-day notice period applies to either party following confirmation of permanent employment.', styles['Normal'])],

            [Paragraph('<b>Code of Conduct:</b> Adherence to all organizational compliance, security, and workplace ethics policies is mandatory.', styles['Normal'])],

        ]

        if offer.additional_terms:

            terms_data.append([Paragraph(f'<b>Additional Terms:</b> {offer.additional_terms}', styles['Normal'])])



        ttab = Table(terms_data, colWidths=[540])

        ttab.setStyle(TableStyle([

            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),

            ('TOPPADDING', (0,0), (-1,-1), 4),

            ('BOTTOMPADDING', (0,0), (-1,-1), 4),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

            ('RIGHTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(ttab)

        story.append(Spacer(1, 14))



        # Section 5: Acceptance & Signatures

        s5_b = [[Paragraph('<font size="9" color="white"><b>5. Acceptance of Offer</b></font>', styles['Normal'])]]

        s5_bt = Table(s5_b, colWidths=[540])

        s5_bt.setStyle(TableStyle([

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0B2545')),

            ('TOPPADDING', (0,0), (-1,-1), 3.5),

            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),

            ('LEFTPADDING', (0,0), (-1,-1), 8),

        ]))

        story.append(s5_bt)



        sig_data = [

            [

                Paragraph(f'<b>For {org_name}</b><br/><br/><i>[Digitally Approved & Authorized]</i><br/><br/><br/><b>Authorized Signatory:</b> Human Resources<br/><b>Date:</b> {issue_date}', styles['Normal']),

                Paragraph(f'<b>Candidate Acceptance</b><br/><br/><i>I have read, understood and accept the terms of this offer.</i><br/><br/><b>Signature:</b> ___________________________<br/><b>Name:</b> {cand_name}<br/><b>Date:</b> ___________________________', styles['Normal']),

            ]

        ]

        sigt = Table(sig_data, colWidths=[270, 270])

        sigt.setStyle(TableStyle([

            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),

            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFFFF')),

            ('TOPPADDING', (0,0), (-1,-1), 8),

            ('BOTTOMPADDING', (0,0), (-1,-1), 8),

            ('LEFTPADDING', (0,0), (-1,-1), 10),

            ('RIGHTPADDING', (0,0), (-1,-1), 10),

            ('VALIGN', (0,0), (-1,-1), 'TOP'),

        ]))

        story.append(sigt)



        # Custom canvas with offer reference number

        class ContextOfferCanvas(OfferNumberedCanvas):

            offer_ref_str = ref_no
            company_name_str = org_name

            def draw_page_decorations(self, page_count):

                self.saveState()

                self.setFillColor(colors.HexColor("#0B2545"))

                self.rect(36, 18, 540, 18, fill=True, stroke=False)

                self.setFillColor(colors.white)

                self.setFont("Helvetica-Bold", 7.5)

                self.drawString(44, 23, f"{getattr(self, 'company_name_str', 'Company')} | Offer Reference No: {self.offer_ref_str}")

                self.drawRightString(568, 23, f"Page {self._pageNumber} of {page_count}")

                self.restoreState()



        doc.build(story, canvasmaker=ContextOfferCanvas)

        return buf.getvalue()



    # Candidate Document Verification Operations



    # ─────────────────────────────────────────────────────────────────────────







    async def get_candidate_documents(



        self, user: User, application_id: uuid.UUID | None = None, candidate_id: uuid.UUID | None = None,



    ) -> list[CandidateDocumentResponse]:



        roles = await self.get_user_roles(user)



        stmt = select(CandidateDocument).order_by(desc(CandidateDocument.updated_at))







        if "candidate" in roles:



            stmt = stmt.where(CandidateDocument.candidate_id == user.id)



        else:



            org_ids = await self.get_user_org_ids(user)



            if org_ids is not None:



                stmt = stmt.where(CandidateDocument.organization_id.in_(org_ids))



            if application_id:



                stmt = stmt.where(CandidateDocument.application_id == application_id)



            if candidate_id:



                stmt = stmt.where(CandidateDocument.candidate_id == candidate_id)







        docs = (await self.session.execute(stmt)).scalars().all()

        if "candidate" in roles and len(docs) == 0:
            offer_stmt = (
                select(JobOffer)
                .where(
                    JobOffer.candidate_id == user.id,
                    JobOffer.status == OfferStatus.ACCEPTED.value,
                )
                .order_by(desc(JobOffer.updated_at))
                .limit(1)
            )
            accepted_offer = (await self.session.execute(offer_stmt)).scalar_one_or_none()
            if accepted_offer:
                await self._seed_standard_documents_for_candidate(accepted_offer)
                await self.session.commit()
                docs = (await self.session.execute(stmt)).scalars().all()



        return [await self._to_document_response(d) for d in docs]







    async def candidate_upload_document(



        self,



        candidate_user: User,



        application_id: uuid.UUID,



        document_type: str,



        document_title: str,



        file_bytes: bytes,



        file_name: str,



        mime_type: str,



    ) -> CandidateDocumentResponse:



        # Check application belongs to candidate



        app = await self.session.get(JobApplication, application_id)



        if not app or app.candidate_id != candidate_user.id:



            raise NotFoundError("Application not found")







        job = await self.session.get(Job, app.job_id)



        org_id = job.organization_id if job else await self.get_primary_org_id(candidate_user)







        # Save file to disk safely



        safe_name = f"{candidate_user.id}_{uuid.uuid4().hex[:8]}_{Path(file_name).name}"



        save_path = DOCUMENTS_UPLOAD_DIR / safe_name



        with open(save_path, "wb") as f:



            f.write(file_bytes)







        file_url = f"/api/v1/post-hiring/documents/file/{safe_name}"







        # Find existing document row or create new



        stmt = select(CandidateDocument).where(



            CandidateDocument.application_id == application_id,



            CandidateDocument.document_type == document_type,



        )



        doc = (await self.session.execute(stmt)).scalar_one_or_none()







        if not doc:



            doc = CandidateDocument(



                application_id=application_id,



                candidate_id=candidate_user.id,



                organization_id=org_id,



                document_type=document_type,



                document_title=document_title or document_type.replace("_", " ").title(),



            )



            self.session.add(doc)







        doc.file_url = file_url



        doc.file_name = file_name



        doc.file_size = len(file_bytes)



        doc.mime_type = mime_type



        doc.status = DocumentVerificationStatus.SUBMITTED.value



        doc.submitted_at = datetime.now(timezone.utc)



        doc.hr_remarks = None







        # Notify HR



        cand_name = candidate_user.full_name



        # Find who created the offer or HR manager in org



        off_stmt = select(JobOffer).where(JobOffer.application_id == application_id).order_by(desc(JobOffer.created_at)).limit(1)



        offer = (await self.session.execute(off_stmt)).scalar_one_or_none()



        if offer and offer.created_by_id:



            await self.dispatch_notification(



                user_id=offer.created_by_id,



                title="Document Submitted for Verification",



                message=f"{cand_name} submitted document: {doc.document_title}",



                notification_type=NotificationType.DOCUMENT_SUBMITTED.value,



                action_link=f"/hr/documents?app_id={application_id}",



            )







        await self.session.commit()



        await self.session.refresh(doc)



        return await self._to_document_response(doc)







    async def verify_document(



        self, hr_user: User, document_id: uuid.UUID, req: DocumentVerifyRequest,



    ) -> CandidateDocumentResponse:



        doc = await self.session.get(CandidateDocument, document_id)



        if not doc:



            raise NotFoundError("Document not found")







        org_ids = await self.get_user_org_ids(hr_user)



        if org_ids is not None and doc.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        doc.status = req.status



        doc.hr_remarks = req.hr_remarks



        doc.verified_at = datetime.now(timezone.utc)



        doc.verified_by_id = hr_user.id







        # Notify candidate



        if req.status == DocumentVerificationStatus.VERIFIED.value:



            await self.dispatch_notification(



                user_id=doc.candidate_id,



                title="Document Verified",



                message=f"Your document '{doc.document_title}' has been verified successfully.",



                notification_type=NotificationType.DOCUMENT_VERIFIED.value,



                action_link="/candidate/offers-onboarding",



            )



        elif req.status == DocumentVerificationStatus.RESUBMISSION_REQUIRED.value:



            await self.dispatch_notification(



                user_id=doc.candidate_id,



                title="Document Resubmission Required",



                message=f"Please resubmit '{doc.document_title}'. HR Remark: {req.hr_remarks or 'Document is unclear or incomplete'}",



                notification_type=NotificationType.DOCUMENT_RESUBMIT.value,



                action_link="/candidate/offers-onboarding",



            )



        elif req.status == DocumentVerificationStatus.REJECTED.value:



            await self.dispatch_notification(



                user_id=doc.candidate_id,



                title="Document Rejected",



                message=f"Document '{doc.document_title}' was rejected. Reason: {req.hr_remarks or 'Invalid document'}",



                notification_type=NotificationType.DOCUMENT_REJECTED.value,



                action_link="/candidate/offers-onboarding",



            )







        await self.session.commit()



        await self.session.refresh(doc)



        return await self._to_document_response(doc)







    # ─────────────────────────────────────────────────────────────────────────



    # Employee Creation & Onboarding Lifecycle



    # ─────────────────────────────────────────────────────────────────────────







    async def create_employee(self, hr_user: User, req: EmployeeCreateRequest) -> EmployeeResponse:
        cand = await self.session.get(User, req.candidate_id)
        if not cand:
            raise NotFoundError("Candidate user not found")

        org_ids = await self.get_user_org_ids(hr_user)
        org_id = org_ids[0] if org_ids else await self.get_primary_org_id(hr_user)

        # Prevent duplicate employee profile
        stmt = select(Employee).where(
            Employee.user_id == req.candidate_id,
            Employee.organization_id == org_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationError(f"Employee profile already exists with ID {existing.employee_id}.")

        # Generate next Employee ID: EMP-XXXX
        count_stmt = select(func.count(Employee.id)).where(Employee.organization_id == org_id)
        current_count = (await self.session.execute(count_stmt)).scalar_one() or 0
        emp_code = f"EMP-{current_count + 1:04d}"

        tmpl = getattr(req, "checklist_template", "standard") or "standard"
        employee = Employee(
            employee_id=emp_code,
            user_id=req.candidate_id,
            application_id=req.application_id,
            organization_id=org_id,
            designation=req.designation,
            department=req.department,
            employment_type=req.employment_type,
            work_location=req.work_location,
            reporting_manager=req.reporting_manager,
            joining_date=req.joining_date,
            employment_status=EmploymentStatus.ONBOARDING.value,
            onboarding_status=OnboardingStatus.IN_PROGRESS.value,
            profile_picture_url=req.profile_picture_url,
            joining_status="pending",
            checklist_template=tmpl,
            onboarding_deadline=getattr(req, "onboarding_deadline", None),
        )
        self.session.add(employee)
        await self.session.flush()

        # Update application status to HIRED
        if req.application_id:
            app = await self.session.get(JobApplication, req.application_id)
            if app:
                app.status = ApplicationStatus.HIRED.value

        # Seed onboarding checklist based on selected template
        base_tasks = [
            ("Documentation: Submit Signed Code of Conduct & NDA", "Sign and acknowledge corporate intellectual property agreement and policies.", OnboardingTaskCategory.DOCUMENTATION.value, "employee", "Review employee handbook and electronically sign the NDA document."),
            ("Personal Info: Complete Emergency Contact & Address Details", "Verify home address, emergency contacts, and phone details.", OnboardingTaskCategory.HR_ADMIN.value, "employee", "Fill in complete address and emergency contact phone numbers."),
            ("HR Administration: Complete Payroll & Bank Direct Deposit", "Submit direct deposit routing numbers and tax withholding preferences.", OnboardingTaskCategory.HR_ADMIN.value, "employee", "Upload voided check or official direct deposit authorization."),
            ("IT Setup: Workstation Provisioning & Email Access", "Provision corporate workstation, email account, SSO and VPN access.", OnboardingTaskCategory.IT_SETUP.value, "hr_admin", "IT administrators will issue corporate credentials and setup devices."),
            ("Orientation: Complete Welcome Orientation & Team Alignment", "Attend welcome orientation session with team members and HR.", OnboardingTaskCategory.ORIENTATION.value, "employee", "Join the company overview orientation call with HR and leadership."),
            ("Reporting Manager: Initial 1-on-1 Goal Setting", "Connect with reporting manager to establish 30-60-90 day milestones.", OnboardingTaskCategory.ORIENTATION.value, "employee", "Schedule initial 45-minute alignment session with your manager."),
            ("Compliance Training: Cybersecurity & Ethics Modules", "Complete mandatory data privacy, security and harassment prevention training.", OnboardingTaskCategory.TRAINING.value, "employee", "Complete required online LMS security and compliance modules."),
        ]

        if tmpl == "engineering":
            base_tasks.append(("Engineering: Dev Environment & GitHub Repository Setup", "Clone repositories, configure Docker/Dev containers and local development keys.", OnboardingTaskCategory.IT_SETUP.value, "employee", "Follow team setup guide in repository wiki and request repo write access."))
            base_tasks.append(("Engineering: Architecture & CI/CD Pipeline Walkthrough", "Review system architecture diagrams, Kubernetes clusters, and deployment pipelines.", OnboardingTaskCategory.TRAINING.value, "employee", "Pair with team tech lead to review deployment procedures."))
        elif tmpl in ["sales_operations", "sales"]:
            base_tasks.append(("Sales & Ops: CRM & Tooling Setup (Salesforce/HubSpot)", "Configure CRM account, sales cadences, and pipeline dashboards.", OnboardingTaskCategory.IT_SETUP.value, "employee", "Complete CRM sandbox onboarding module."))
            base_tasks.append(("Sales: Client Communication & Pitch Deck Guidelines", "Review corporate brand guidelines, email templates, and standard product demo deck.", OnboardingTaskCategory.POLICY.value, "employee", "Review customer pitch recordings and deck collateral."))
        elif tmpl == "executive":
            base_tasks.append(("Executive: Board & Stakeholder Introduction Meetings", "Conduct 1-on-1 strategy sessions with department heads and executive peers.", OnboardingTaskCategory.ORIENTATION.value, "employee", "Meet with functional leaders across Engineering, Product, and Sales."))
            base_tasks.append(("Governance: Review Signing Authority & Delegation Matrix", "Review corporate governance policies, budget authorizations, and approval thresholds.", OnboardingTaskCategory.POLICY.value, "employee", "Sign official delegation of authority authorization."))

        for title, descr, cat, role, instr in base_tasks:
            task = OnboardingTask(
                employee_id=employee.id,
                organization_id=org_id,
                title=title,
                description=descr,
                category=cat,
                assigned_to_role=role,
                instructions=instr,
                status="not_started",
                is_completed=False,
            )
            self.session.add(task)

        # Record timeline event
        await self._record_timeline_event(
            application_id=req.application_id,
            event_type="ONBOARDING_STARTED",
            title=f"Onboarding Started ({tmpl.capitalize()} Template)",
            description=f"HR ({hr_user.full_name}) initialized onboarding with {len(base_tasks)} checklist tasks for {req.designation}.",
            actor_name=hr_user.full_name,
            actor_role="HR Manager",
            status="in_progress",
        )

        # Notify new employee
        await self.dispatch_notification(
            user_id=cand.id,
            title="Welcome to the Team! Onboarding Started",
            message=f"Your employee profile has been created ({emp_code}). Please review your onboarding tasks and instructions.",
            notification_type=NotificationType.ONBOARDING_STARTED.value,
            action_link="/candidate/offers-onboarding",
        )

        await self.session.commit()
        await self.session.refresh(employee)
        return await self._to_employee_response(employee)

    async def get_employees(



        self,



        user: User,



        department: str | None = None,



        employment_status: str | None = None,



        search: str | None = None,



    ) -> list[EmployeeResponse]:



        org_ids = await self.get_user_org_ids(user)







        stmt = select(Employee).options(selectinload(Employee.tasks)).order_by(desc(Employee.created_at))



        if org_ids is not None:



            stmt = stmt.where(Employee.organization_id.in_(org_ids))



        if department:



            stmt = stmt.where(Employee.department == department)



        if employment_status:



            stmt = stmt.where(Employee.employment_status == employment_status)







        employees = (await self.session.execute(stmt)).scalars().all()



        responses = [await self._to_employee_response(e) for e in employees]







        if search:



            s = search.lower()



            responses = [



                r for r in responses



                if s in (r.employee_id.lower())



                or s in (r.user_name or "").lower()



                or s in (r.user_email or "").lower()



                or s in r.designation.lower()



                or s in r.department.lower()



            ]







        return responses







    async def get_employee_by_id(self, user: User, employee_id: uuid.UUID) -> EmployeeResponse:



        stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.id == employee_id)



        employee = (await self.session.execute(stmt)).scalar_one_or_none()



        if not employee:



            raise NotFoundError("Employee not found")







        roles = await self.get_user_roles(user)



        if "candidate" in roles and employee.user_id != user.id:



            raise ForbiddenError("Access denied.")







        org_ids = await self.get_user_org_ids(user)



        if "candidate" not in roles and org_ids is not None and employee.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        return await self._to_employee_response(employee)







    async def update_employee(



        self, user: User, employee_id: uuid.UUID, req: EmployeeUpdateRequest,



    ) -> EmployeeResponse:



        employee = await self.session.get(Employee, employee_id)



        if not employee:



            raise NotFoundError("Employee not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and employee.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        for key, value in req.model_dump(exclude_unset=True).items():



            if value is not None:



                setattr(employee, key, value)







        await self.session.commit()



        await self.session.refresh(employee)



        return await self._to_employee_response(employee)







    async def add_onboarding_task(



        self, user: User, employee_id: uuid.UUID, req: OnboardingTaskCreateRequest,



    ) -> OnboardingTaskResponse:



        employee = await self.session.get(Employee, employee_id)



        if not employee:



            raise NotFoundError("Employee not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and employee.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        task = OnboardingTask(



            employee_id=employee_id,



            organization_id=employee.organization_id,



            title=req.title,



            description=req.description,



            category=req.category,



            assigned_to_role=req.assigned_to_role,



            deadline=req.deadline,



            hr_remarks=req.hr_remarks,



            is_completed=False,



        )



        self.session.add(task)



        await self.session.commit()



        await self.session.refresh(task)



        return OnboardingTaskResponse.model_validate(task)







    async def update_onboarding_task(



        self, user: User, task_id: uuid.UUID, req: OnboardingTaskUpdateRequest,



    ) -> OnboardingTaskResponse:



        task = await self.session.get(OnboardingTask, task_id)



        if not task:



            raise NotFoundError("Task not found")







        org_ids = await self.get_user_org_ids(user)



        if org_ids is not None and task.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        if req.is_completed is not None:



            task.is_completed = req.is_completed



            task.completed_at = datetime.now(timezone.utc) if req.is_completed else None



            task.completed_by_id = user.id if req.is_completed else None







        if req.hr_remarks is not None:



            task.hr_remarks = req.hr_remarks



        if req.deadline is not None:



            task.deadline = req.deadline







        await self.session.commit()



        await self.session.refresh(task)



        return OnboardingTaskResponse.model_validate(task)







    async def candidate_get_onboarding(self, candidate_user: User) -> EmployeeResponse | None:



        stmt = (



            select(Employee)



            .options(selectinload(Employee.tasks))



            .where(Employee.user_id == candidate_user.id)



            .order_by(desc(Employee.created_at))



            .limit(1)



        )



        employee = (await self.session.execute(stmt)).scalar_one_or_none()



        if not employee:



            return None



        return await self._to_employee_response(employee)







    async def candidate_toggle_task(self, candidate_user: User, task_id: uuid.UUID) -> OnboardingTaskResponse:



        task = await self.session.get(OnboardingTask, task_id)



        if not task:



            raise NotFoundError("Task not found")







        # Verify task belongs to this employee



        employee = await self.session.get(Employee, task.employee_id)



        if not employee or employee.user_id != candidate_user.id:



            raise ForbiddenError("Access denied to this task.")







        task.is_completed = not task.is_completed



        task.completed_at = datetime.now(timezone.utc) if task.is_completed else None



        task.completed_by_id = candidate_user.id if task.is_completed else None







        await self.session.commit()



        await self.session.refresh(task)



        return OnboardingTaskResponse.model_validate(task)







    async def complete_onboarding(self, hr_user: User, employee_id: uuid.UUID) -> EmployeeResponse:



        stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.id == employee_id)



        employee = (await self.session.execute(stmt)).scalar_one_or_none()



        if not employee:



            raise NotFoundError("Employee not found")







        org_ids = await self.get_user_org_ids(hr_user)



        if org_ids is not None and employee.organization_id not in org_ids:



            raise ForbiddenError("Access denied.")







        # Activate employee



        employee.employment_status = EmploymentStatus.ACTIVE.value



        employee.onboarding_status = OnboardingStatus.COMPLETED.value



        employee.onboarding_completed_at = datetime.now(timezone.utc)







        # Mark all pending tasks as complete



        for t in employee.tasks:



            if not t.is_completed:



                t.is_completed = True



                t.completed_at = datetime.now(timezone.utc)



                t.completed_by_id = hr_user.id







        # Dispatch congratulatory notification



        await self.dispatch_notification(



            user_id=employee.user_id,



            title="Onboarding Completed - Welcome Aboard!",



            message=f"Congratulations! Your onboarding for {employee.designation} is officially complete. You are now an active team member.",



            notification_type=NotificationType.ONBOARDING_COMPLETED.value,



            action_link="/candidate/offers-onboarding",



        )







        await self.session.commit()



        await self.session.refresh(employee)



        return await self._to_employee_response(employee)







    # ─────────────────────────────────────────────────────────────────────────



    # Admin Stats



    # ─────────────────────────────────────────────────────────────────────────







    async def get_admin_stats(self, user: User) -> dict[str, Any]:



        org_ids = await self.get_user_org_ids(user)







        emp_q = select(func.count(Employee.id))



        offer_q = select(func.count(JobOffer.id))



        docs_q = select(func.count(CandidateDocument.id))







        if org_ids is not None:



            emp_q = emp_q.where(Employee.organization_id.in_(org_ids))



            offer_q = offer_q.where(JobOffer.organization_id.in_(org_ids))



            docs_q = docs_q.where(CandidateDocument.organization_id.in_(org_ids))







        total_employees = (await self.session.execute(emp_q)).scalar_one() or 0



        total_offers = (await self.session.execute(offer_q)).scalar_one() or 0



        total_documents = (await self.session.execute(docs_q)).scalar_one() or 0







        # Department breakdown



        dept_q = select(Employee.department, func.count(Employee.id)).group_by(Employee.department)



        if org_ids is not None:



            dept_q = dept_q.where(Employee.organization_id.in_(org_ids))



        dept_counts = dict((await self.session.execute(dept_q)).all())







        return {



            "total_employees": total_employees,



            "total_offers": total_offers,



            "total_documents_processed": total_documents,



            "department_breakdown": dept_counts,



        }







    # ─────────────────────────────────────────────────────────────────────────



    # Response Model Serialization Helpers



    # ─────────────────────────────────────────────────────────────────────────







    async def _to_offer_response(self, offer: JobOffer) -> JobOfferResponse:



        cand = await self.session.get(User, offer.candidate_id)



        job = await self.session.get(Job, offer.job_id)



        org = await self.session.get(Organization, offer.organization_id)



        creator = await self.session.get(User, offer.created_by_id) if offer.created_by_id else None







        return JobOfferResponse(



            id=offer.id,



            application_id=offer.application_id,



            candidate_id=offer.candidate_id,



            candidate_name=cand.full_name if cand else None,



            candidate_email=cand.email if cand else None,



            job_id=offer.job_id,



            job_title=job.title if job else None,



            organization_id=offer.organization_id,



            organization_name=org.name if org else None,



            created_by_id=offer.created_by_id,



            created_by_name=creator.full_name if creator else None,



            designation=offer.designation,



            department=offer.department,



            employment_type=offer.employment_type,



            offered_salary=offer.offered_salary,



            currency=offer.currency,



            work_location=offer.work_location,



            reporting_manager=offer.reporting_manager,



            joining_date=offer.joining_date,



            probation_period_months=offer.probation_period_months,



            benefits_summary=offer.benefits_summary,



            additional_terms=offer.additional_terms,



            offer_expiry_date=offer.offer_expiry_date,



            hr_remarks=offer.hr_remarks,



            status=offer.status,



            sent_at=offer.sent_at,



            viewed_at=offer.viewed_at,



            responded_at=offer.responded_at,



            decline_reason=offer.decline_reason,



            candidate_notes=offer.candidate_notes,



            created_at=offer.created_at,



            updated_at=offer.updated_at,



        )







    async def _to_document_response(self, doc: CandidateDocument) -> CandidateDocumentResponse:



        cand = await self.session.get(User, doc.candidate_id)



        verifier = await self.session.get(User, doc.verified_by_id) if doc.verified_by_id else None







        return CandidateDocumentResponse(



            id=doc.id,



            application_id=doc.application_id,



            candidate_id=doc.candidate_id,



            candidate_name=cand.full_name if cand else None,



            candidate_email=cand.email if cand else None,



            organization_id=doc.organization_id,



            document_type=doc.document_type,



            document_title=doc.document_title,



            file_url=doc.file_url,



            file_name=doc.file_name,



            file_size=doc.file_size,



            mime_type=doc.mime_type,



            status=doc.status,



            submitted_at=doc.submitted_at,



            verified_at=doc.verified_at,



            verified_by_id=doc.verified_by_id,



            verified_by_name=verifier.full_name if verifier else None,



            hr_remarks=doc.hr_remarks,



            created_at=doc.created_at,



            updated_at=doc.updated_at,



        )







    async def _to_employee_response(self, emp: Employee) -> EmployeeResponse:



        cand = await self.session.get(User, emp.user_id)



        org = await self.session.get(Organization, emp.organization_id)







        stmt = select(OnboardingTask).where(OnboardingTask.employee_id == emp.id).order_by(OnboardingTask.created_at)



        tasks_list = list((await self.session.execute(stmt)).scalars().all())



        total_tasks = len(tasks_list)



        completed_tasks = sum(1 for t in tasks_list if t.is_completed)



        progress = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0







        task_responses = [OnboardingTaskResponse.model_validate(t) for t in tasks_list]







        return EmployeeResponse(



            id=emp.id,



            employee_id=emp.employee_id,



            user_id=emp.user_id,



            user_name=cand.full_name if cand else None,



            user_email=cand.email if cand else None,



            application_id=emp.application_id,



            organization_id=emp.organization_id,



            organization_name=org.name if org else None,



            designation=emp.designation,



            department=emp.department,



            employment_type=emp.employment_type,



            work_location=emp.work_location,



            reporting_manager=emp.reporting_manager,



            joining_date=emp.joining_date,



            employment_status=emp.employment_status,



            onboarding_status=emp.onboarding_status,



            onboarding_completed_at=emp.onboarding_completed_at,



                        profile_picture_url=emp.profile_picture_url,
            joining_status=getattr(emp, "joining_status", "pending") or "pending",
            joining_confirmed_at=getattr(emp, "joining_confirmed_at", None),
            joining_remarks=getattr(emp, "joining_remarks", None),
            checklist_template=getattr(emp, "checklist_template", "standard") or "standard",
            onboarding_deadline=getattr(emp, "onboarding_deadline", None),
            activated_at=getattr(emp, "activated_at", None),



            created_at=emp.created_at,



            updated_at=emp.updated_at,



            total_tasks=total_tasks,



            completed_tasks=completed_tasks,



            onboarding_progress_percent=progress,



            tasks=task_responses,



        )





    async def _record_timeline_event(
        self,
        event_type: str,
        action: str = "",
        resource_type: str = "application",
        resource_id: str = "",
        details: dict | None = None,
        user_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        *,
        application_id: uuid.UUID | str | None = None,
        title: str | None = None,
        description: str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        status: str = "completed",
    ) -> AuditLog:
        if application_id is not None:
            resource_id = str(application_id)
            resource_type = "application"
        if title:
            action = title
        if details is None:
            details = {}
        if description:
            details["description"] = description
        if actor_name:
            details["actor_name"] = actor_name
        if actor_role:
            details["actor_role"] = actor_role
        if status:
            details["status"] = status

        audit = AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            event_type=event_type,
            action=action or event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self.session.add(audit)
        return audit

    async def get_recruiter_post_hiring_tracker(self, user: User) -> list[RecruiterPostHiringCandidateItem]:
        roles = await self.get_user_roles(user)
        is_recruiter_only = "recruiter" in roles and not any(r in roles for r in ["super_admin", "admin", "hr", "hr_manager"])

        stmt = (
            select(JobApplication)
            .join(Job, JobApplication.job_id == Job.id)
            .options(selectinload(JobApplication.candidate), selectinload(JobApplication.job))
        )
        if is_recruiter_only:
            stmt = stmt.where(Job.recruiter_id == user.id)
        else:
            org_ids = await self.get_user_org_ids(user)
            if org_ids is not None:
                stmt = stmt.where(Job.organization_id.in_(org_ids))

        stmt = stmt.where(
            JobApplication.status.in_([
                ApplicationStatus.SELECTED.value,
                ApplicationStatus.OFFERED.value,
                ApplicationStatus.HIRED.value,
            ])
        ).order_by(desc(JobApplication.updated_at))

        apps = (await self.session.execute(stmt)).scalars().all()
        result: list[RecruiterPostHiringCandidateItem] = []

        for app in apps:
            candidate = await self.session.get(User, app.candidate_id)
            job = await self.session.get(Job, app.job_id)
            if not candidate or not job:
                continue

            # Offer
            offer_stmt = select(JobOffer).where(JobOffer.application_id == app.id).order_by(desc(JobOffer.updated_at)).limit(1)
            offer = (await self.session.execute(offer_stmt)).scalar_one_or_none()

            # Documents
            docs_stmt = select(CandidateDocument).where(CandidateDocument.application_id == app.id)
            docs = (await self.session.execute(docs_stmt)).scalars().all()
            docs_submitted = sum(1 for d in docs if d.status in ["submitted", "verified", "resubmission_required"])
            docs_verified = sum(1 for d in docs if d.status == "verified")
            has_resubmit = any(d.status == "resubmission_required" for d in docs)
            
            doc_status = "Pending Upload"
            if docs_verified >= 4:
                doc_status = "Verified"
            elif has_resubmit:
                doc_status = "Resubmission Requested"
            elif docs_submitted > 0:
                doc_status = "Under Review"

            # Employee / Onboarding
            emp_stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.application_id == app.id).limit(1)
            emp = (await self.session.execute(emp_stmt)).scalar_one_or_none()

            onboarding_status = "Not Started"
            onb_percent = 0
            emp_status = "Pending"
            emp_code = None

            if emp:
                total_t = len(emp.tasks) if emp.tasks else 0
                done_t = sum(1 for t in emp.tasks if t.is_completed) if emp.tasks else 0
                onb_percent = round((done_t / total_t) * 100) if total_t > 0 else 0
                if onb_percent == 100:
                    onboarding_status = "Completed"
                elif onb_percent > 0:
                    onboarding_status = "In Progress"
                else:
                    onboarding_status = "Not Started"

                emp_status = "Active" if emp.employment_status == EmploymentStatus.ACTIVE.value else "Onboarding"
                emp_code = emp.employee_id

            joining_d = emp.joining_date if emp else (offer.joining_date if offer else None)

            result.append(
                RecruiterPostHiringCandidateItem(
                    application_id=app.id,
                    candidate_id=candidate.id,
                    candidate_name=candidate.full_name,
                    candidate_email=candidate.email,
                    job_id=job.id,
                    job_title=job.title,
                    department=job.department,
                    hr_hiring_decision="HIRED",
                    offer_id=offer.id if offer else None,
                    offer_status=offer.status if offer else "pending",
                    offer_sent_at=offer.sent_at if offer else None,
                    offer_accepted_at=offer.responded_at if (offer and offer.status == "accepted") else None,
                    joining_date=joining_d,
                    document_submission_status=doc_status,
                    documents_submitted=docs_submitted,
                    documents_verified=docs_verified,
                    documents_total=4,
                    onboarding_status=onboarding_status,
                    onboarding_progress_percent=onb_percent,
                    employee_status=emp_status,
                    employee_id_code=emp_code,
                    updated_at=app.updated_at,
                )
            )

        return result

    async def get_post_hiring_timeline(self, application_id: uuid.UUID, user: User) -> list[PostHiringTimelineEvent]:
        roles = await self.get_user_roles(user)
        app = await self.session.get(JobApplication, application_id)
        if not app:
            raise NotFoundError("Application not found")

        # Security check: candidate only views own
        if "candidate" in roles and not any(r in roles for r in ["super_admin", "admin", "hr", "hr_manager", "recruiter"]):
            if app.candidate_id != user.id:
                raise ForbiddenError("Access denied.")

        job = await self.session.get(Job, app.job_id)
        candidate = await self.session.get(User, app.candidate_id)
        cand_name = candidate.full_name if candidate else "Candidate"
        job_title = job.title if job else "Position"

        events: list[PostHiringTimelineEvent] = []

        # Application Selected / Hired
        if app.decided_at or app.advanced_to_hr_at or app.created_at:
            hired_time = app.decided_at or app.advanced_to_hr_at or app.created_at
            events.append(
                PostHiringTimelineEvent(
                    id=f"app-hired-{app.id}",
                    timestamp=_normalize_dt(hired_time),
                    event_type="hiring.decision",
                    title="Candidate Selected by HR",
                    description=f"{cand_name} was approved and selected for {job_title}.",
                    actor_name="HR Operations",
                    actor_role="hr",
                    status="completed",
                )
            )

        # Offer
        offer_stmt = select(JobOffer).where(JobOffer.application_id == app.id).order_by(desc(JobOffer.updated_at)).limit(1)
        offer = (await self.session.execute(offer_stmt)).scalar_one_or_none()
        if offer:
            if offer.created_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"offer-created-{offer.id}",
                        timestamp=_normalize_dt(offer.created_at),
                        event_type="offer.created",
                        title="Job Offer Letter Drafted",
                        description=f"Official employment offer drafted for {offer.designation}.",
                        actor_name="HR Manager",
                        actor_role="hr",
                        status="completed",
                    )
                )
            if offer.sent_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"offer-sent-{offer.id}",
                        timestamp=_normalize_dt(offer.sent_at),
                        event_type="offer.sent",
                        title="Job Offer Sent to Candidate",
                        description=f"Official job offer sent to {cand_name}.",
                        actor_name="HR Manager",
                        actor_role="hr",
                        status="completed",
                    )
                )
            if offer.viewed_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"offer-viewed-{offer.id}",
                        timestamp=_normalize_dt(offer.viewed_at),
                        event_type="offer.viewed",
                        title="Candidate Viewed Offer",
                        description=f"{cand_name} reviewed the employment offer terms.",
                        actor_name=cand_name,
                        actor_role="candidate",
                        status="completed",
                    )
                )
            if offer.status == "accepted" and offer.responded_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"offer-accepted-{offer.id}",
                        timestamp=_normalize_dt(offer.responded_at),
                        event_type="offer.accepted",
                        title="Candidate Accepted Offer",
                        description=f"{cand_name} signed and accepted the job offer.",
                        actor_name=cand_name,
                        actor_role="candidate",
                        status="completed",
                    )
                )
            elif offer.status == "declined" and offer.responded_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"offer-declined-{offer.id}",
                        timestamp=_normalize_dt(offer.responded_at),
                        event_type="offer.declined",
                        title="Candidate Declined Offer",
                        description=f"{cand_name} declined the offer.",
                        actor_name=cand_name,
                        actor_role="candidate",
                        status="completed",
                    )
                )

        # Documents
        docs_stmt = select(CandidateDocument).where(CandidateDocument.application_id == app.id)
        docs = (await self.session.execute(docs_stmt)).scalars().all()
        for doc in docs:
            if doc.file_name and doc.updated_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"doc-up-{doc.id}",
                        timestamp=_normalize_dt(doc.updated_at),
                        event_type="document.uploaded",
                        title=f"Document Submitted: {doc.document_type.replace('_', ' ').title()}",
                        description=f"{cand_name} uploaded {doc.document_title}.",
                        actor_name=cand_name,
                        actor_role="candidate",
                        status="completed",
                    )
                )
            if doc.verified_at:
                if doc.status == "verified":
                    events.append(
                        PostHiringTimelineEvent(
                            id=f"doc-ver-{doc.id}",
                            timestamp=_normalize_dt(doc.verified_at),
                            event_type="document.verified",
                            title=f"Document Verified: {doc.document_type.replace('_', ' ').title()}",
                            description=f"HR verified and approved {doc.document_title}.",
                            actor_name="HR Operations",
                            actor_role="hr",
                            status="completed",
                        )
                    )
                elif doc.status == "resubmission_required":
                    events.append(
                        PostHiringTimelineEvent(
                            id=f"doc-rej-{doc.id}",
                            timestamp=_normalize_dt(doc.verified_at),
                            event_type="document.rejected",
                            title=f"Resubmission Requested: {doc.document_type.replace('_', ' ').title()}",
                            description=f"HR requested re-upload: {doc.hr_remarks or 'Correction needed.'}",
                            actor_name="HR Operations",
                            actor_role="hr",
                            status="action_required",
                        )
                    )

        # Employee & Onboarding
        emp_stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.application_id == app.id).limit(1)
        emp = (await self.session.execute(emp_stmt)).scalar_one_or_none()
        if emp:
            if emp.created_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"emp-created-{emp.id}",
                        timestamp=_normalize_dt(emp.created_at),
                        event_type="onboarding.started",
                        title="Employee Onboarding Initiated",
                        description=f"Assigned Employee ID #{emp.employee_id}. Onboarding tasks assigned.",
                        actor_name="HR Manager",
                        actor_role="hr",
                        status="completed",
                    )
                )
            if emp.tasks:
                for t in emp.tasks:
                    if t.is_completed and t.completed_at:
                        events.append(
                            PostHiringTimelineEvent(
                                id=f"task-done-{t.id}",
                                timestamp=_normalize_dt(t.completed_at),
                                event_type="onboarding.task_completed",
                                title=f"Onboarding Task: {t.title}",
                                description=f"Task completed by {cand_name}.",
                                actor_name=cand_name,
                                actor_role="candidate",
                                status="completed",
                            )
                        )
            if emp.employment_status == EmploymentStatus.ACTIVE.value and emp.updated_at:
                events.append(
                    PostHiringTimelineEvent(
                        id=f"emp-active-{emp.id}",
                        timestamp=_normalize_dt(emp.updated_at),
                        event_type="employee.activated",
                        title="Employee Profile Activated",
                        description=f"{cand_name} is now officially an Active Employee at the organization.",
                        actor_name="HR Operations",
                        actor_role="hr",
                        status="completed",
                    )
                )

        # Deduplicate and sort chronologically
        seen_keys = set()
        unique_events: list[PostHiringTimelineEvent] = []
        for e in sorted(events, key=lambda x: _normalize_dt(x.timestamp)):
            key = f"{e.event_type}_{e.timestamp.strftime('%Y%m%d%H%M')}_{e.title}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_events.append(e)

        return unique_events


    async def confirm_joining(
        self, hr_user: User, employee_id: uuid.UUID, req: JoiningConfirmRequest
    ) -> EmployeeResponse:
        stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.id == employee_id)
        employee = (await self.session.execute(stmt)).scalar_one_or_none()
        if not employee:
            raise NotFoundError("Employee record not found")

        org_ids = await self.get_user_org_ids(hr_user)
        if org_ids is not None and employee.organization_id not in org_ids:
            raise ForbiddenError("Access denied.")

        employee.joining_status = req.joining_status
        employee.joining_confirmed_at = datetime.now(timezone.utc)
        employee.joining_confirmed_by_id = hr_user.id
        if req.remarks:
            employee.joining_remarks = req.remarks
        if req.joining_date:
            employee.joining_date = req.joining_date

        if req.joining_status in ["no_show", "cancelled"]:
            employee.employment_status = EmploymentStatus.TERMINATED.value
            employee.onboarding_status = "cancelled"

        # Record timeline event
        await self._record_timeline_event(
            application_id=employee.application_id,
            event_type="JOINING_CONFIRMED" if req.joining_status == "confirmed" else "JOINING_CANCELLED",
            title=f"Joining {req.joining_status.capitalize()}",
            description=f"Candidate joining confirmed for {employee.designation} by HR ({hr_user.full_name})." if req.joining_status == "confirmed" else f"Candidate marked as {req.joining_status}: {req.remarks or 'No remarks provided'}.",
            actor_name=hr_user.full_name,
            actor_role="HR Manager",
            status="completed",
        )

        # Notify candidate and recruiter
        await self.dispatch_notification(
            user_id=employee.user_id,
            title="Joining Confirmed - Welcome!",
            message=f"HR has officially confirmed your scheduled start date for {employee.designation}.",
            notification_type=NotificationType.JOINING_CONFIRMED.value,
            action_link="/candidate/offers-onboarding",
        )

        await self.session.commit()
        await self.session.refresh(employee)
        return await self._to_employee_response(employee)

    async def activate_employee(
        self, hr_user: User, employee_id: uuid.UUID
    ) -> EmployeeResponse:
        stmt = select(Employee).options(selectinload(Employee.tasks)).where(Employee.id == employee_id)
        employee = (await self.session.execute(stmt)).scalar_one_or_none()
        if not employee:
            raise NotFoundError("Employee record not found")

        org_ids = await self.get_user_org_ids(hr_user)
        if org_ids is not None and employee.organization_id not in org_ids:
            raise ForbiddenError("Access denied.")

        if employee.employment_status == EmploymentStatus.ACTIVE.value:
            raise ValidationError("Employee is already activated.")

        # Require confirmed joining status before activation
        if employee.joining_status != "confirmed":
            raise ValidationError("Joining must be confirmed by HR before activating the employee profile.")

        employee.employment_status = EmploymentStatus.ACTIVE.value
        employee.onboarding_status = OnboardingStatus.COMPLETED.value
        employee.onboarding_completed_at = datetime.now(timezone.utc)
        employee.activated_at = datetime.now(timezone.utc)
        employee.activated_by_id = hr_user.id

        # Mark all tasks as completed
        for t in employee.tasks:
            if not t.is_completed:
                t.is_completed = True
                t.status = "completed"
                t.completed_at = datetime.now(timezone.utc)
                t.completed_by_id = hr_user.id

        # Update application status
        if employee.application_id:
            app = await self.session.get(JobApplication, employee.application_id)
            if app:
                app.status = ApplicationStatus.HIRED.value

        # Record timeline event
        await self._record_timeline_event(
            application_id=employee.application_id,
            event_type="EMPLOYEE_ACTIVATED",
            title="Employee Activated",
            description=f"{employee.employee_id} officially transitioned to Active Full-Time Staff.",
            actor_name=hr_user.full_name,
            actor_role="HR Manager",
            status="completed",
        )

        # Notify employee
        await self.dispatch_notification(
            user_id=employee.user_id,
            title="Account Activated as Full-Time Employee",
            message=f"Congratulations! Your profile has been activated as an employee ({employee.employee_id}). Welcome to the team!",
            notification_type=NotificationType.EMPLOYEE_ACTIVATED.value,
            action_link="/hr/employees",
        )

        await self.session.commit()
        await self.session.refresh(employee)
        return await self._to_employee_response(employee)

    async def candidate_submit_task(
        self, candidate_user: User, task_id: uuid.UUID, req: CandidateTaskSubmitRequest
    ) -> OnboardingTaskResponse:
        task = await self.session.get(OnboardingTask, task_id)
        if not task:
            raise NotFoundError("Onboarding task not found")

        emp = await self.session.get(Employee, task.employee_id)
        if not emp or emp.user_id != candidate_user.id:
            raise ForbiddenError("You can only submit tasks assigned to your onboarding profile.")

        task.status = "pending_approval"
        task.submission_notes = req.submission_notes
        if req.attachment_url:
            task.attachment_url = req.attachment_url

        await self._record_timeline_event(
            application_id=emp.application_id,
            event_type="TASK_SUBMITTED",
            title=f"Task Submitted: {task.title}",
            description=f"Candidate submitted completion evidence for '{task.title}'. Awaiting HR approval.",
            actor_name=candidate_user.full_name,
            actor_role="Candidate",
            status="in_progress",
        )

        await self.session.commit()
        await self.session.refresh(task)
        return OnboardingTaskResponse.model_validate(task)

    async def review_task(
        self, hr_user: User, task_id: uuid.UUID, req: TaskReviewRequest
    ) -> OnboardingTaskResponse:
        task = await self.session.get(OnboardingTask, task_id)
        if not task:
            raise NotFoundError("Onboarding task not found")

        org_ids = await self.get_user_org_ids(hr_user)
        if org_ids is not None and task.organization_id not in org_ids:
            raise ForbiddenError("Access denied.")

        emp = await self.session.get(Employee, task.employee_id)
        task.status = req.status
        task.hr_remarks = req.hr_remarks

        if req.status == "completed":
            task.is_completed = True
            task.completed_at = datetime.now(timezone.utc)
            task.completed_by_id = hr_user.id
        elif req.status == "rejected":
            task.is_completed = False

        # If all tasks are completed, update employee onboarding status
        if emp:
            stmt = select(OnboardingTask).where(OnboardingTask.employee_id == emp.id)
            all_tasks = list((await self.session.execute(stmt)).scalars().all())
            if all(t.is_completed for t in all_tasks):
                emp.onboarding_status = OnboardingStatus.COMPLETED.value
                emp.onboarding_completed_at = datetime.now(timezone.utc)

        # Notify candidate
        if emp:
            await self.dispatch_notification(
                user_id=emp.user_id,
                title="Onboarding Task Approved" if req.status == "completed" else "Onboarding Task Action Required",
                message=f"Task '{task.title}' was reviewed by HR: {req.hr_remarks or ('Marked ' + req.status)}",
                notification_type=NotificationType.ONBOARDING_ASSIGNED.value,
                action_link="/candidate/offers-onboarding",
            )

        await self.session.commit()
        await self.session.refresh(task)
        return OnboardingTaskResponse.model_validate(task)

    async def send_task_reminder(self, hr_user: User, task_id: uuid.UUID) -> dict[str, str]:
        task = await self.session.get(OnboardingTask, task_id)
        if not task:
            raise NotFoundError("Onboarding task not found")

        emp = await self.session.get(Employee, task.employee_id)
        if not emp:
            raise NotFoundError("Employee profile not found")

        await self.dispatch_notification(
            user_id=emp.user_id,
            title=f"Reminder: {task.title}",
            message=f"Friendly reminder to complete your onboarding task: '{task.title}'. Deadline: {task.deadline.strftime('%b %d, %Y') if task.deadline else 'Soon'}.",
            notification_type=NotificationType.ONBOARDING_ASSIGNED.value,
            action_link="/candidate/offers-onboarding",
        )
        return {"status": "success", "message": "Reminder sent successfully"}
