"""Response schemas for application-specific Explainable AI (Phase 6).

One authoritative explanation model, two authorized presentation layers.

Both responses are built from the *same* internal explanation payload that
:class:`app.services.screening.application_explanation_service.ApplicationExplanationService`
produces. The recruiter response exposes the internal view; the candidate
response is an explicit allowlist projection that is assembled field by field
in ``_project_candidate``. The internal payload is therefore never serialized
straight to a candidate, so a newly added internal field cannot leak by
accident the way a shared permissive model would.

Shared invariants enforced by both schemas:

* ``score.overall_score`` is copied verbatim from the stored
  ``ScreeningResult.overall_match_score``. It is never recomputed here or in
  the frontend, so the explanation can never disagree with the screening it
  explains.
* Absence of evidence is reported as absence. Optional intelligence sections
  carry an ``available``/``reason`` pair instead of an invented value.
* Nothing in these schemas is a hiring decision. Explainability answers "why
  did the system produce this screening result?"; the recruiter decision is a
  separate, later workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.screening_schemas import ScreeningDimensionScore

ScreeningExplanationState = Literal[
    "not_started", "queued", "running", "completed", "failed", "skipped", "unknown",
]


# ─── Shared building blocks ────────────────────────────────────────
# Everything below is safe for both roles: it is either a stored screening
# value or a quote from the candidate's own resume.


class ExplanationSection(BaseModel):
    """Per-section availability so one missing source never breaks the page."""

    available: bool
    reason: str | None = None


class ExplanationEvidence(BaseModel):
    """A verifiable quote from the candidate's own resume.

    Sources are limited to the candidate's resume content. There is no source
    for recruiter notes, internal system state or any other party's data.
    """

    source: str
    quote: str
    context: str | None = None
    section: str | None = None


class ExplanationFeature(BaseModel):
    """One explainability dimension and its share of the overall result.

    ``weight`` is the engine's configured dimension weight. It is recruiter-only:
    the candidate projection omits the field, and the service's candidate-safety
    assertion treats any weight key in a candidate payload as a violation.
    """

    category: str
    label: str
    score: int
    contribution_pct: float
    impact: str
    impact_description: str
    method: str | None = None
    weight: float | None = None


class CandidateExplanationFeature(BaseModel):
    """Candidate-safe dimension breakdown.

    Deliberately a separate model from :class:`ExplanationFeature` so the
    recruiter-only ``weight`` field cannot appear in a candidate response even
    as ``null``. A shared model would leak the field's existence and give the
    frontend a value it must remember not to render.
    """

    category: str
    label: str
    score: int
    contribution_pct: float
    impact: str
    impact_description: str
    method: str | None = None


class ExplanationFactor(BaseModel):
    """A positive or negative factor, with the evidence behind it (if any)."""

    category: str
    score: int
    contribution_pct: float
    reason: str
    evidence: list[ExplanationEvidence] = Field(default_factory=list)
    evidence_available: bool = False


class ExplanationEvidenceStrength(BaseModel):
    """A skill the evidence engine found genuine support for.

    Sourced from the Phase 3 candidate intelligence strengths. Deliberately not
    an :class:`ExplanationFactor`: that type carries screening contribution
    weights, and the evidence engine produces no such number. Inventing one
    would misrepresent a depth judgement as a score.
    """

    title: str
    category: str | None = None
    depth: str = ""
    confidence: str = ""
    reason: str = ""
    evidence: list[ExplanationEvidence] = Field(default_factory=list)
    evidence_available: bool = False


class ExplanationRequirement(BaseModel):
    """Requirement-level match result from the existing evidence-grounded fit."""

    requirement: str
    requirement_type: str
    level: str
    category: str | None = None
    status: str
    evidence_strength: str
    reason: str
    evidence: list[ExplanationEvidence] = Field(default_factory=list)


class ExplanationSkillAlignment(BaseModel):
    """Required -> candidate -> matched/missing, from existing skill intelligence.

    ``matched_skills`` / ``missing_*_skills`` come from the stored
    ``ScreeningResult``; the four gap buckets come from the Phase 2 fit
    engine's ``skill_gaps``. No second skill-matching algorithm exists here.
    """

    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    supported_skills: list[str] = Field(default_factory=list)
    partial_evidence_skills: list[str] = Field(default_factory=list)
    skills_without_evidence: list[str] = Field(default_factory=list)
    insufficient_information_skills: list[str] = Field(default_factory=list)


class ExplanationAlignment(BaseModel):
    """Experience alignment against this job's stated requirement."""

    status: str
    required_years: float | None = None
    relevant_years: float | None = None
    total_years: float | None = None
    relevance_basis: str | None = None
    reason: str = ""


class ExplanationEvidenceGap(BaseModel):
    """Where the profile does not currently provide enough evidence."""

    subject: str
    category: str
    note: str = ""


class ExplanationSuggestion(BaseModel):
    """An improvement suggestion, normalized to a flat, renderable list.

    Sourced from the existing XAI improvement suggestions. Nothing is invented:
    a category with no supporting data simply produces no entries.
    """

    category: Literal[
        "skill", "certification", "project", "resume", "interview",
    ]
    subject: str | None = None
    text: str
    priority: str | None = None


class ExplanationConfidence(BaseModel):
    """Confidence in the *evidence available*, not in the candidate.

    Recomputed by the existing XAI engine from stored screening data. It
    describes how much data the explanation rests on and is never presented as
    a hiring probability.
    """

    score: int
    level: str
    description: str
    data_completeness_pct: float
    data_points_available: int
    data_points_max: int


class ExplanationFreshness(BaseModel):
    """Which artifacts the explanation was derived from.

    ``screening_resume_is_current_primary`` surfaces resume-version drift
    instead of silently explaining a different resume than the one screened.
    """

    screening_resume_id: str | None = None
    application_resume_id: str | None = None
    primary_resume_id: str | None = None
    evidence_resume_id: str | None = None
    screening_resume_is_current_primary: bool | None = None
    evidence_resume_is_screening_resume: bool | None = None
    screened_at: datetime | None = None
    fit_engine_version: str | None = None
    evidence_engine_version: str | None = None
    explainability_method: str = "rule_based"


class ExplanationScreeningState(BaseModel):
    """Screening execution state, and whether an explanation can exist yet."""

    effective_status: ScreeningExplanationState
    screened: bool
    message: str


# ─── Recruiter view (internal) ─────────────────────────────────────


class RecruiterExplanationApplication(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    resume_id: str | None = None
    status: str
    applied_at: datetime | None = None
    updated_at: datetime | None = None
    screening_status: str
    screening_attempts: int = 0
    screening_error: str | None = None
    screening_started_at: datetime | None = None
    screening_completed_at: datetime | None = None


class RecruiterExplanationCandidate(BaseModel):
    id: str
    name: str = ""
    email: str = ""


class RecruiterExplanationJob(BaseModel):
    id: str
    title: str = ""
    company: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: str | None = None
    education_required: str | None = None


class RecruiterExplanationScore(BaseModel):
    """The authoritative stored score. Copied, never recomputed."""

    overall_score: int | None = None
    recommendation: str | None = None
    strength_level: str | None = None
    screened_at: datetime | None = None
    source: Literal["screening_result", "unavailable"]


class RecruiterApplicationExplanationResponse(BaseModel):
    """Internal, recruiter-facing "Why This Score?" for one application.

    Includes engine internals a candidate must never see: dimension weights,
    the fit formula, evidence review flags and suggested screening questions.
    """

    application: RecruiterExplanationApplication
    candidate: RecruiterExplanationCandidate
    job: RecruiterExplanationJob
    screening_state: ExplanationScreeningState
    score: RecruiterExplanationScore
    match_breakdown: list[ScreeningDimensionScore] = Field(default_factory=list)
    feature_importance: list[ExplanationFeature] = Field(default_factory=list)
    positive_factors: list[ExplanationFactor] = Field(default_factory=list)
    negative_factors: list[ExplanationFactor] = Field(default_factory=list)
    reasoning_summary: str = ""
    confidence: ExplanationConfidence | None = None
    improvement_suggestions: list[ExplanationSuggestion] = Field(default_factory=list)
    skill_alignment: ExplanationSkillAlignment = Field(
        default_factory=ExplanationSkillAlignment,
    )
    requirements: list[ExplanationRequirement] = Field(default_factory=list)
    experience_alignment: ExplanationAlignment | None = None
    evidence_gaps: list[ExplanationEvidenceGap] = Field(default_factory=list)
    evidence_strengths: list[ExplanationEvidenceStrength] = Field(default_factory=list)
    fit_classification: str | None = None
    fit_score: int | None = None
    fit_summary: str | None = None
    fit_summary_source: str | None = None
    fit_formula: str | None = None
    fit_weights: dict[str, float] = Field(default_factory=dict)
    review_flags: list[dict] = Field(default_factory=list)
    screening_questions: list[dict] = Field(default_factory=list)
    evidence_snapshot: dict | None = None
    explainability: ExplanationSection
    evidence_intelligence: ExplanationSection
    fit: ExplanationSection
    freshness: ExplanationFreshness
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "AI-assisted screening explanation. Decision support for human review, "
        "not a hiring decision."
    )


# ─── Candidate view (safe) ─────────────────────────────────────────
# Deliberately a *different* model. It is assembled from an explicit
# allowlist, never by filtering the recruiter response at runtime.


class CandidateExplanationApplication(BaseModel):
    """Candidate-safe application context.

    ``status`` is the real hiring-lifecycle status, never an AI verdict, and
    never a fabricated "selected"/"rejected" claim.
    """

    id: str
    job_id: str
    status: str
    applied_at: datetime | None = None
    screening_status: str


class CandidateExplanationJob(BaseModel):
    """The public job posting the candidate already applied to."""

    id: str
    title: str = ""
    company: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: str | None = None
    education_required: str | None = None


class CandidateExplanationScore(BaseModel):
    """The candidate-safe score block.

    ``recommendation`` and ``strength_level`` are intentionally absent: those
    are internal hiring-advocacy verdicts, and showing them would imply the AI
    decided the outcome. ``match_classification`` describes alignment with
    *this role*, which is the question the candidate is actually asking.
    """

    overall_score: int | None = None
    screened_at: datetime | None = None
    source: Literal["screening_result", "unavailable"]
    match_classification: str | None = None
    match_score: int | None = None
    match_summary: str | None = None
    match_summary_source: str | None = None


class CandidateApplicationExplanationResponse(BaseModel):
    """Candidate-safe "How Your Profile Matches This Role" for one application.

    Contains only: the candidate's own application/job context, their own
    resume evidence, and the alignment of that evidence with the role.

    Never contains: recruiter notes or comments, hiring decisions or rejection
    reasons, other candidates' scores or rankings, internal shortlist
    comparisons, fairness or protected-attribute analysis, fraud or security
    signals, audit metadata, engine weights/formulas, review flags, or
    interviewer question suggestions.
    """

    application: CandidateExplanationApplication
    job: CandidateExplanationJob
    screening_state: ExplanationScreeningState
    score: CandidateExplanationScore
    matched_skills: list[str] = Field(default_factory=list)
    areas_with_limited_evidence: list[str] = Field(default_factory=list)
    skill_alignment: ExplanationSkillAlignment = Field(
        default_factory=ExplanationSkillAlignment,
    )
    aligned_areas: list[ExplanationFactor] = Field(default_factory=list)
    limited_areas: list[ExplanationFactor] = Field(default_factory=list)
    feature_importance: list[CandidateExplanationFeature] = Field(default_factory=list)
    requirements: list[ExplanationRequirement] = Field(default_factory=list)
    experience_alignment: ExplanationAlignment | None = None
    evidence_gaps: list[ExplanationEvidenceGap] = Field(default_factory=list)
    resume_evidence: list[ExplanationEvidence] = Field(default_factory=list)
    improvement_suggestions: list[ExplanationSuggestion] = Field(default_factory=list)
    confidence: ExplanationConfidence | None = None
    explainability: ExplanationSection
    evidence_intelligence: ExplanationSection
    fit: ExplanationSection
    freshness: ExplanationFreshness
    screening_notice: str = (
        "This is an automated review of the evidence in your resume against "
        "this role's requirements. It supports human review and is not a "
        "decision about your application."
    )
    limitations: list[str] = Field(default_factory=list)
