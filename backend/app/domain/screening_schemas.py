import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.fit_schemas import FitResponse
from app.domain.intel_schemas import (
    EvidenceIntelligenceResponse,
    JobContextBlock,
)


class ScreeningConfig(BaseModel):
    weights: "ScreeningWeights | None" = None


class ScreeningWeights(BaseModel):
    skills: float = Field(default=0.30, ge=0.0, le=1.0)
    experience: float = Field(default=0.20, ge=0.0, le=1.0)
    education: float = Field(default=0.15, ge=0.0, le=1.0)
    projects: float = Field(default=0.10, ge=0.0, le=1.0)
    certifications: float = Field(default=0.10, ge=0.0, le=1.0)
    location: float = Field(default=0.05, ge=0.0, le=1.0)
    employment_type: float = Field(default=0.05, ge=0.0, le=1.0)
    semantic: float = Field(default=0.05, ge=0.0, le=1.0)


DEFAULT_WEIGHTS = ScreeningWeights()


class ScreeningResultResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    application_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None
    overall_match_score: int
    skill_match_score: int
    experience_match_score: int
    education_match_score: int
    project_match_score: int
    certification_match_score: int
    location_match_score: int
    employment_type_match_score: int
    semantic_match_score: int
    matched_skills: list[str] | None
    missing_required_skills: list[str] | None
    missing_preferred_skills: list[str] | None
    strengths: list[str] | None
    weaknesses: list[str] | None
    recommendation: str
    strength_level: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScreeningDimensionScore(BaseModel):
    """One stored screening dimension, exposed with its source column.

    The value is exactly what ``ScreeningResult`` persisted; nothing is
    recomputed or rescaled here.
    """

    key: str
    label: str
    score: int
    source_column: str


class ScreeningExecutionState(BaseModel):
    """Screening execution state for an application (not hiring status)."""

    effective_status: str
    recorded_status: str
    attempts: int = 0
    task_id: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ScreeningApplicationContext(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    status: str
    applied_at: datetime
    updated_at: datetime | None = None
    cover_letter: str | None = None
    decision_reason: str | None = None
    decision_comment: str | None = None
    decided_at: datetime | None = None
    screening: ScreeningExecutionState


class ScreeningCandidateContext(BaseModel):
    id: uuid.UUID
    name: str = ""
    email: str = ""
    resume_id: uuid.UUID | None = None
    has_resume: bool = False


class ScreeningJobContext(BaseModel):
    id: uuid.UUID
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_required: str | None = None
    education_required: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)


class ScreeningFreshness(BaseModel):
    """Which artifacts the stored screening result was produced from."""

    screened_at: datetime | None = None
    screening_resume_id: uuid.UUID | None = None
    application_resume_id: uuid.UUID | None = None
    resume_matches_application: bool | None = None
    engine_version: str | None = None
    fit_engine_version: str | None = None
    evidence_engine_version: str | None = None


class ScreeningIntelligenceSection(BaseModel):
    """Per-section availability so one gap never breaks the whole detail."""

    available: bool
    reason: str | None = None


class ApplicationScreeningDetailResponse(BaseModel):
    """Read-only recruiter view of one application's screening context.

    Every nested payload is an existing platform contract: the stored
    ``ScreeningResult``, the Phase 2 ``FitResponse`` and the Phase 3
    evidence intelligence response. No score is recalculated here.
    """

    application: ScreeningApplicationContext
    candidate: ScreeningCandidateContext
    job: ScreeningJobContext
    screening_result: ScreeningResultResponse | None = None
    match_breakdown: list[ScreeningDimensionScore] = Field(default_factory=list)
    evidence_intelligence: EvidenceIntelligenceResponse | None = None
    evidence_intelligence_section: ScreeningIntelligenceSection
    fit: FitResponse | None = None
    fit_section: ScreeningIntelligenceSection
    job_context: JobContextBlock | None = None
    job_context_section: ScreeningIntelligenceSection
    freshness: ScreeningFreshness
    limitations: list[str] = Field(default_factory=list)


class CandidateRankingResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str = ""
    candidate_email: str = ""
    screening_result_id: uuid.UUID
    rank: int
    previous_rank: int | None
    rank_change: int
    overall_score: int
    strength_level: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillGapResponse(BaseModel):
    id: uuid.UUID
    screening_result_id: uuid.UUID
    missing_required_skills: list[str] | None
    missing_preferred_skills: list[str] | None
    experience_gap_description: str | None
    education_gap_description: str | None
    certification_gap_description: str | None
    skill_suggestions: list[str] | None
    improvement_suggestions: list[str] | None
    interview_readiness_score: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateComparisonRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=5)


class CandidateComparisonItem(BaseModel):
    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    overall_match_score: int
    skill_match_score: int
    experience_match_score: int
    education_match_score: int
    project_match_score: int
    certification_match_score: int
    matched_skills: list[str] | None
    missing_required_skills: list[str] | None
    strengths: list[str] | None
    weaknesses: list[str] | None
    recommendation: str
    strength_level: str


class CandidateComparisonResponse(BaseModel):
    job_id: uuid.UUID
    job_title: str
    candidates: list[CandidateComparisonItem]


class CandidateMatchReportResponse(BaseModel):
    job_id: uuid.UUID
    job_title: str
    candidate_id: uuid.UUID
    candidate_name: str
    screening: ScreeningResultResponse | None
    skill_gap: SkillGapResponse | None
    interview_readiness_score: int | None
    improvement_suggestions: list[str] | None


class RankingListResponse(BaseModel):
    items: list[CandidateRankingResponse]
    total: int
    job_id: uuid.UUID
    job_title: str


class ScreeningTriggerResponse(BaseModel):
    message: str
    job_id: uuid.UUID
    candidates_screened: int


class ScoringWeightsResponse(BaseModel):
    weights: ScreeningWeights
    total: float


# ─── AI Search ────────────────────────────────────────────────────────

class AISearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    job_id: uuid.UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AISearchResultItem(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    overall_score: int = 0
    relevance_score: int = 0
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    recommendation: str = "not_screened"
    strength_level: str = "low"
    experience_years: float = 0
    location: str = ""
    has_screening: bool = False


class AISearchResponse(BaseModel):
    results: list[AISearchResultItem]
    total: int
    query_skills: list[str] = []
    query_years: int | None = None
    query_location: str | None = None
    job_id: str | None = None
    job_title: str | None = None


# ─── Candidate AI Summary ─────────────────────────────────────────────

class CandidateAISummaryResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    professional_summary: str
    top_skills: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    career_highlights: list[str]
    risk_factors: list[str]
    experience_level: str
    technical_expertise: str
    leadership_potential: str
    learning_ability: str
    total_experience_years: float
    education_summary: list[str]
    certification_count: int
    project_count: int
    job_match_score: int | None = None
    hiring_recommendation: str | None = None
    matched_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    strengths_from_screening: list[str] | None = None
    weaknesses_from_screening: list[str] | None = None
    interview_readiness: int | None = None
    improvement_suggestions: list[str] | None = None


# ─── Job AI Summary ───────────────────────────────────────────────────

class JobAISummaryResponse(BaseModel):
    job_id: str
    job_title: str
    total_applicants: int
    total_screened: int
    average_score: float
    top_candidates: list[dict]
    score_distribution: dict
    recommendation_breakdown: dict
    most_common_matched_skills: list[dict] | None = None
    most_common_missing_skills: list[dict] | None = None


# ─── Top Candidates ───────────────────────────────────────────────────

class TopCandidateItem(BaseModel):
    rank: int
    candidate_id: str
    candidate_name: str
    candidate_email: str
    overall_score: int
    strength_level: str
    recommendation: str
    skill_match: int = 0
    experience_match: int = 0
    matched_skills: list[str] = []
    rank_change: int = 0


class TopCandidatesResponse(BaseModel):
    job_id: str | None = None
    job_title: str | None = None
    candidates: list[TopCandidateItem]
    total_ranked: int = 0
    total_jobs: int = 0


# ─── Hiring Recommendation ───────────────────────────────────────────

class HiringRecommendationExplanation(BaseModel):
    title: str
    summary: str
    factors: list[str]
    next_steps: list[str]
    score_breakdown: dict


class HiringRecommendationResponse(BaseModel):
    job_id: str
    job_title: str
    candidate_id: str
    candidate_name: str
    recommendation: str
    overall_score: int
    confidence_score: int
    strength_level: str
    explanation: HiringRecommendationExplanation
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    weaknesses: list[str]
    interview_readiness: int | None = None
    improvement_suggestions: list[str] = []


# ─── Recruiter AI Dashboard ───────────────────────────────────────────

class RecruiterDashboardSummaryResponse(BaseModel):
    total_jobs: int
    total_applications: int
    total_screened: int
    average_score: float
    job_summaries: list[dict]
    recent_rankings: list[dict]


# ─── XAI (Explainable AI) ──────────────────────────────────────────

class FeatureImportanceItem(BaseModel):
    category: str
    label: str
    score: int
    weight: float
    contribution_pct: float
    impact: str
    impact_description: str
    shap_value: float | None = None
    method: str | None = None


class FactorItem(BaseModel):
    category: str
    score: int
    contribution_pct: float
    reason: str


class ConfidenceScore(BaseModel):
    score: int
    level: str
    description: str
    data_completeness_pct: float
    data_points_available: int
    data_points_max: int


class ImprovementSuggestion(BaseModel):
    skill: str
    priority: str
    reason: str


class CertificationSuggestion(BaseModel):
    area: str
    suggestion: str
    priority: str


class CandidateExplanationResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    job_id: str
    job_title: str
    overall_score: int
    feature_importance: list[FeatureImportanceItem]
    positive_factors: list[FactorItem]
    negative_factors: list[FactorItem]
    reasoning_summary: str
    confidence: ConfidenceScore
    improvement_suggestions: dict
    strengths: list[str]
    weaknesses: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation: str
    strength_level: str
    shap_available: bool
    lime_available: bool


class FeatureImportanceResponse(BaseModel):
    candidate_id: str
    job_id: str
    overall_score: int
    features: list[FeatureImportanceItem]
    method: str


class ConfidenceResponse(BaseModel):
    candidate_id: str
    job_id: str
    overall_score: int
    confidence: ConfidenceScore


class RecommendationsResponse(BaseModel):
    candidate_id: str
    job_id: str
    overall_score: int
    recommendations: dict


class CandidateCompareRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=5)
    job_id: uuid.UUID


class PairwiseComparison(BaseModel):
    higher_candidate: str
    higher_name: str
    higher_score: int
    lower_candidate: str
    lower_name: str
    lower_score: int
    score_difference: int
    key_differences: list[dict]
    skills_only_higher_has: list[str]
    skills_only_lower_has: list[str]
    summary: str


class CandidateCompareResponse(BaseModel):
    job_id: str
    job_title: str
    candidates: list[dict]
    pairwise_comparisons: list[PairwiseComparison]


# --- Fairness & Bias Detection ---

class FairnessMetricDetail(BaseModel):
    value: float
    description: str
    status: str


class FairnessMetricsResponse(BaseModel):
    statistical_parity_difference: FairnessMetricDetail
    disparate_impact_ratio: FairnessMetricDetail
    equal_opportunity_difference: FairnessMetricDetail
    demographic_parity: FairnessMetricDetail
    consistency_score: FairnessMetricDetail
    composite_fairness_score: FairnessMetricDetail
    data_points: int


class BiasAlert(BaseModel):
    type: str
    severity: str
    message: str
    recommendation: str
    job_id: str | None = None


class FairnessOverviewResponse(BaseModel):
    overall_fairness_score: float
    total_screened: int
    total_rankings: int
    total_jobs: int
    total_candidates: int
    bias_alerts: list[BiasAlert]
    diversity_indicators: dict
    compliance_status: str
    last_analyzed: str


class FairnessReportResponse(BaseModel):
    job_id: str
    job_title: str
    total_candidates: int
    fairness_score: float
    metrics: dict
    score_distribution: dict
    gender_distribution: dict
    location_distribution: dict
    bias_alerts: list[BiasAlert]
    recommendations: list[str]
    trend: list[dict]
    hiring_recommendations: list[dict]
    # Phase 7: real protected-group comparison for this job's screened
    # population, plus the scope and methodology that must travel with the
    # numbers so no consumer can present them without their caveats.
    group_fairness: dict | None = None
    metric_scope: str | None = None
    metric_methodology: str | None = None
    score_distribution_metrics_note: str | None = None
    message: str | None = None


class AdversarialVariant(BaseModel):
    variant_type: str
    original_value: str
    modified_value: str
    original_score: int
    modified_score: int
    score_difference: int
    bias_detected: bool


class AdversarialTestResponse(BaseModel):
    job_id: str
    candidate_id: str
    candidate_name: str
    original_score: int
    total_variants_tested: int
    biased_variants_detected: int
    stability_score: float
    bias_sensitivity: str
    variants: list[AdversarialVariant]
    recommendation: str


class JDAnalysisResponse(BaseModel):
    job_id: str
    job_title: str
    word_count: int
    bias_score: int
    ats_compatibility_score: int
    readability_score: int
    diversity_score: int
    gendered_language: list[dict]
    age_biased_language: list[dict]
    discriminatory_terms: list[dict]
    exclusive_language: list[dict]
    unnecessary_requirements: list[dict]
    total_issues: int
    inclusive_suggestions: list[dict]
    overall_assessment: str


class CandidateFairnessResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    fairness_status: str
    bias_checks_completed: bool
    total_evaluations: int
    average_score: float
    transparency_summary: list[str]
    protected_attributes_used: list[str]
    appeal_available: bool
    appeal_status: str
    last_evaluation_date: str | None
