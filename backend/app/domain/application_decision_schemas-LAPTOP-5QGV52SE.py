"""Phase 8 recruiter decision contracts and the candidate-safe projection.

The candidate-facing text in this module is the *only* source of candidate
decision communication. It is a fixed, reviewed projection of the controlled
``RejectionReason`` code plus the job title. It never reads
``JobApplication.decision_comment`` (the private recruiter note), the screening
score, the AI recommendation, ranking data, fairness context, protected
attributes, or anything about other candidates, so an internal comment cannot
leak by construction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import ApplicationDecisionType, ApplicationStatus, RejectionReason

# ── Recruiter-facing labels for the controlled rejection vocabulary ────────
REJECTION_REASON_RECRUITER_LABELS: dict[RejectionReason, str] = {
    RejectionReason.MISSING_REQUIRED_SKILL: "Missing a required skill",
    RejectionReason.INSUFFICIENT_EXPERIENCE: "Insufficient relevant experience",
    RejectionReason.EDUCATION_REQUIREMENT: "Education requirement not met",
    RejectionReason.LOW_JOB_MATCH: "Profile does not match this role's core requirements",
    RejectionReason.FAILED_ASSESSMENT: "Did not meet the assessment requirements",
    RejectionReason.FAILED_INTERVIEW: "Did not progress after the interview stage",
    RejectionReason.POSITION_FILLED: "Position has been filled",
    RejectionReason.OTHER: "Other (recorded in the internal note only)",
}

# ── Candidate-facing approved messages, keyed by reason code ───────────────
# Written for candidates: factual, respectful, no ranking, no protected
# attributes, no fairness language, no other-candidate information, and no
# reproduction of recruiter prose. ``{job_title}`` is the only substitution.
REJECTION_REASON_CANDIDATE_MESSAGES: dict[RejectionReason, str] = {
    RejectionReason.MISSING_REQUIRED_SKILL: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates whose experience includes the core skills this "
        "role requires."
    ),
    RejectionReason.INSUFFICIENT_EXPERIENCE: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates who have more directly relevant experience for "
        "the responsibilities in this role."
    ),
    RejectionReason.EDUCATION_REQUIREMENT: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates who meet the education requirements listed for "
        "this role."
    ),
    RejectionReason.LOW_JOB_MATCH: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates whose background aligns more closely with the "
        "core requirements of this role."
    ),
    RejectionReason.FAILED_ASSESSMENT: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates who met the requirements of the assessment for "
        "this role."
    ),
    RejectionReason.FAILED_INTERVIEW: (
        "After reviewing your application for {job_title}, we decided to move "
        "forward with candidates who progressed further in our interview process."
    ),
    RejectionReason.POSITION_FILLED: (
        "The position for {job_title} has been filled. We appreciate the time you "
        "invested in applying."
    ),
    RejectionReason.OTHER: (
        "After reviewing your application for {job_title}, we have decided not to "
        "progress your application at this time."
    ),
}

# Candidate-facing status wording. The stored status stays ``rejected``; only
# the label the candidate reads is softened, which keeps the API truthful
# without exposing a blunt internal term.
CANDIDATE_STATUS_LABELS: dict[ApplicationStatus, str] = {
    ApplicationStatus.APPLIED: "Applied",
    ApplicationStatus.UNDER_REVIEW: "Under Review",
    ApplicationStatus.SHORTLISTED: "Shortlisted",
    ApplicationStatus.INTERVIEW_SCHEDULED: "Interview Scheduled",
    ApplicationStatus.INTERVIEWED: "Interview Completed",
    ApplicationStatus.REJECTED: "Not Selected",
    # Phase 13: "Selected", never "Hired". The stored status is ``selected`` and
    # the label must not imply the candidate already has the job.
    ApplicationStatus.SELECTED: "Selected",
    ApplicationStatus.OFFERED: "Offer",
    ApplicationStatus.HIRED: "Hired",
    ApplicationStatus.WITHDRAWN: "Withdrawn",
}

# Non-rejection candidate messages, so every committed decision produces one
# coherent candidate-visible outcome.
CANDIDATE_STATUS_MESSAGES: dict[ApplicationStatus, str] = {
    ApplicationStatus.UNDER_REVIEW: (
        "Your application for {job_title} is still under review. No decision has "
        "been made yet."
    ),
    ApplicationStatus.SHORTLISTED: (
        "Your application for {job_title} has been shortlisted. The hiring team "
        "will be in touch about the next step."
    ),
    ApplicationStatus.REJECTED: "",  # resolved from the rejection reason code
    # Phase 11: the interview stages. Both are factual statements about process
    # progress and promise nothing about the outcome, so a candidate who is
    # interviewed is never told or implied that they advanced.
    ApplicationStatus.INTERVIEW_SCHEDULED: (
        "An interview has been scheduled for your application to {job_title}. "
        "You will be contacted with the details."
    ),
    ApplicationStatus.INTERVIEWED: (
        "Your interview for {job_title} has been completed. The hiring team is "
        "reviewing the outcome and will be in touch about the next step."
    ),
    # Phase 13: states the decision the recruiter actually made. It deliberately
    # does not say the candidate is hired, does not promise an offer, and
    # reveals nothing about how they compared to anyone else.
    ApplicationStatus.SELECTED: (
        "You have been selected for {job_title}. The hiring team will be in "
        "touch about the next step."
    ),
}

# Shown when an application is rejected but no controlled reason code was
# recorded (for example a rejection made before Phase 8, or through the legacy
# status endpoint). It states the outcome without inventing a reason.
CANDIDATE_REASON_UNAVAILABLE = (
    "Your application for {job_title} was reviewed and was not selected at this "
    "time. No further detail was provided for this decision."
)


def candidate_rejection_message(
    reason: RejectionReason | None, job_title: str,
) -> str | None:
    """Project a validated reason code into approved candidate-facing text.

    Returns ``None`` when there is no recorded reason, so a candidate never
    receives a fabricated explanation. A reason code that is not part of the
    controlled vocabulary also yields ``None`` rather than free text.
    """
    if reason is None:
        return None
    template = REJECTION_REASON_CANDIDATE_MESSAGES.get(reason)
    if template is None:
        return None
    return template.format(job_title=job_title or "this role")


def candidate_status_message(
    status: ApplicationStatus, job_title: str, reason: RejectionReason | None,
) -> str | None:
    """Candidate-facing outcome text for any decision-backed status."""
    if status == ApplicationStatus.REJECTED:
        return (
            candidate_rejection_message(reason, job_title)
            or CANDIDATE_REASON_UNAVAILABLE.format(job_title=job_title or "this role")
        )
    template = CANDIDATE_STATUS_MESSAGES.get(status)
    if template is None:
        return None
    return template.format(job_title=job_title or "this role")


# ── Recruiter decision input ───────────────────────────────────────────────

class ApplicationDecisionCreate(BaseModel):
    """Recruiter-submitted decision.

    ``rejection_reason`` must be one of the controlled ``RejectionReason``
    values and is mandatory for ``reject``. ``internal_note`` is private to
    staff: it is stored on the application and never projected to a candidate.
    The AI cannot select a reason; the recruiter must send it.
    """

    decision: ApplicationDecisionType
    rejection_reason: RejectionReason | None = None
    internal_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _validate_reason_requirement(self) -> "ApplicationDecisionCreate":
        if self.decision.requires_rejection_reason and self.rejection_reason is None:
            raise ValueError(
                "A rejection reason is required when rejecting an application"
            )
        if (
            not self.decision.requires_rejection_reason
            and self.rejection_reason is not None
        ):
            raise ValueError(
                "A rejection reason may only be supplied when rejecting an "
                "application"
            )
        return self


# ── Recruiter decision output ──────────────────────────────────────────────

class RejectionReasonOption(BaseModel):
    value: RejectionReason
    label: str
    # Exactly what the candidate will be shown, so the recruiter can confirm the
    # candidate-facing wording before committing.
    candidate_message: str


class ApplicationDecisionOption(BaseModel):
    decision: ApplicationDecisionType
    label: str
    description: str
    target_status: ApplicationStatus
    requires_rejection_reason: bool
    available: bool
    unavailable_reason: str | None = None
    # Phase 13: the exact candidate-facing wording this decision would produce,
    # so the recruiter can confirm it before committing rather than the UI
    # guessing at the text. ``None`` for a decision that sends no notification
    # (keep under review) or that has no wording until a reason is chosen.
    candidate_message: str | None = None


class ApplicationDecisionResult(BaseModel):
    """Outcome of a recorded decision, for the recruiter UI."""

    application_id: uuid.UUID
    decision: ApplicationDecisionType
    previous_status: ApplicationStatus
    status: ApplicationStatus
    changed_status: bool
    rejection_reason: RejectionReason | None = None
    rejection_reason_label: str | None = None
    internal_note: str | None = None
    candidate_status_label: str
    candidate_message: str | None = None
    decided_at: datetime | None = None
    decided_by: uuid.UUID | None = None


class ApplicationDecisionOptions(BaseModel):
    """Server-authoritative decision affordances for one application.

    The UI renders these instead of hardcoding a transition table, so the
    backend lifecycle rules stay the single source of truth.
    """

    application_id: uuid.UUID
    current_status: ApplicationStatus
    status_is_final: bool
    options: list[ApplicationDecisionOption]
    rejection_reasons: list[RejectionReasonOption]


class ApplicationDecisionHistoryItem(BaseModel):
    """One immutable decision/status record, staff-visible only."""

    id: uuid.UUID
    decision: ApplicationDecisionType | None
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    rejection_reason: RejectionReason | None = None
    rejection_reason_label: str | None = None
    internal_note: str | None = None
    changed_by: uuid.UUID | None = None
    changed_by_name: str | None = None
    changed_at: datetime


class ApplicationDecisionHistory(BaseModel):
    application_id: uuid.UUID
    status: ApplicationStatus
    decided_by: uuid.UUID | None = None
    decided_at: datetime | None = None
    rejection_reason: RejectionReason | None = None
    internal_note: str | None = None
    candidate_message: str | None = None
    history: list[ApplicationDecisionHistoryItem]


# ── Candidate view (explicit allowlist, no internal fields) ────────────────

class CandidateApplicationDecisionResponse(BaseModel):
    """Everything a candidate may ever see about a decision.

    Deliberately excludes: internal_note, decided_by, decision history,
    recruiter identity, screening score, AI recommendation, ranking position,
    fairness context, protected attributes, and audit data.
    """

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    status: ApplicationStatus
    status_label: str
    decision_outcome: str
    rejection_reason: RejectionReason | None = None
    candidate_message: str | None = None
    decided_at: datetime | None = None
    is_decision_final: bool
