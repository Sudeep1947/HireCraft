"""Response schemas for application-centric Fairness & Bias Intelligence (Phase 7).

Fairness is a *population* property, not a property of one applicant. These
schemas are built to make that impossible to get wrong in a consumer:

* There is no per-candidate fairness score anywhere in this module. The unit of
  analysis is ``FairnessPopulation`` -- the job's screened population -- and the
  application under review is only a member of it, identified by
  ``application_is_in_population``.
* Fairness is never merged with the match score. No field here combines them and
  none may be added that does.
* Every metric travels with its ``metric_status`` and ``status_reason``. A
  metric that could not be computed is present with a null value and a stated
  reason, never silently replaced with a favourable number and never omitted so
  a caller can assume it is absent rather than unavailable.
* ``methodology`` and ``grouping_note`` are part of the payload, not UI copy, so
  a consumer cannot render a disparity figure without the statement that it
  indicates where to investigate and does not establish causation.
* Nothing here is a hiring decision, and no field is derived from application
  status or rank.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Reusing the same state vocabulary as explainability so a recruiter sees one
# consistent set of screening states across the screening workflow.
FairnessScreeningStateValue = Literal[
    "not_started", "queued", "running", "completed", "failed", "skipped", "unknown",
]

FairnessSectionAvailability = Literal[
    "available", "insufficient_data", "no_screening_data", "unavailable",
]

FairnessGroupMetricStatus = Literal[
    "available", "insufficient_sample", "no_demographic_data", "unknown",
]

FairnessCrossGroupMetricStatus = Literal[
    "available", "identical_rates", "insufficient_data", "no_reference_group",
]


class FairnessSection(BaseModel):
    """Per-section availability, so one missing source never breaks the page."""

    status: FairnessSectionAvailability
    reason: str | None = None


class FairnessContextApplication(BaseModel):
    """The application whose fairness context is being viewed.

    ``status`` is the real hiring-lifecycle status, included so a consumer can
    show it unchanged. Fairness analysis never reads or writes it.
    """

    id: str
    job_id: str
    status: str
    applied_at: str | None = None


class FairnessContextJob(BaseModel):
    id: str
    title: str = ""
    company: str = ""


class FairnessScreeningState(BaseModel):
    """Whether this application's screening can contribute to the analysis."""

    effective_status: FairnessScreeningStateValue
    screened: bool
    message: str


class FairnessPopulation(BaseModel):
    """The population the fairness metrics actually describe.

    Stated explicitly so a recruiter-facing surface can never imply that a
    metric belongs to the individual candidate being viewed.
    """

    job_id: str
    job_title: str
    applications: int
    screened: int
    unscreened: int
    application_is_in_population: bool
    application_screening_included: bool
    scope: str
    note: str


class FairnessScoreDistribution(BaseModel):
    """Descriptive statistics of the job's screening scores.

    Deliberately *not* labelled as group fairness metrics: these are properties
    of the score distribution. ``note`` is returned so a consumer is told the
    distinction rather than having to know it.
    """

    average: float
    minimum: int
    maximum: int
    median: float
    std_dev: float
    positive_outcome_threshold: int
    note: str


class FairnessGroupOutcome(BaseModel):
    """One self-reported demographic group's screening outcome rate."""

    group_value: str
    sample_size: int
    positive_outcome_count: int | None = None
    positive_outcome_rate: float | None = None
    metric_status: FairnessGroupMetricStatus
    status_reason: str | None = None


class FairnessCrossGroupMetric(BaseModel):
    """SPD or DI across groups, against the reference group."""

    metric_name: str
    metric_label: str
    value: float | None = None
    reference_group: str | None = None
    groups_compared: list[str] = Field(default_factory=list)
    metric_status: FairnessCrossGroupMetricStatus
    status_reason: str | None = None


class FairnessCoverage(BaseModel):
    """How much of the population supplied a usable attribute value.

    Reported so a low-coverage analysis cannot be read as a clean bill of
    health. ``attributes_inferred`` is always False: the platform never guesses a
    protected attribute.
    """

    group_dimension: str
    attribute_source: str
    attributes_inferred: bool
    population: int
    candidates_with_demographic: int
    candidates_missing_demographic: int
    demographic_coverage_pct: float
    minimum_group_size: int
    positive_outcome_threshold: int


class FairnessGroupAnalysis(BaseModel):
    """The protected-group comparison for a job's screened population."""

    metric_status: str
    status_reason: str | None = None
    reference_group: str | None = None
    coverage: FairnessCoverage
    group_outcomes: list[FairnessGroupOutcome] = Field(default_factory=list)
    cross_group_metrics: list[FairnessCrossGroupMetric] = Field(default_factory=list)
    methodology: str
    grouping_note: str


class FairnessAlertView(BaseModel):
    """A review alert raised by the engine. Never a decision."""

    type: str
    severity: str
    message: str
    recommendation: str


class FairnessFinding(BaseModel):
    term: str
    category: str
    suggestion: str


class FairnessSuggestion(BaseModel):
    category: str
    suggestion: str
    priority: str


class JobDescriptionBiasView(BaseModel):
    """Job-description bias analysis, from the existing JD analysis engine.

    This describes the *job posting*, not the candidate: it is the same signal
    for every applicant to the role, and it does not vary with the individual
    being viewed.
    """

    job_id: str
    bias_score: int
    overall_assessment: str
    total_issues: int
    issue_counts: dict[str, int]
    findings: list[FairnessFinding] = Field(default_factory=list)
    suggestions: list[FairnessSuggestion] = Field(default_factory=list)
    note: str


class AdversarialContextView(BaseModel):
    """Whether a *previously executed* adversarial test exists for this job.

    The existing engine computes adversarial variants on demand and does not
    persist them, so there is no stored result to show and this phase does not
    trigger one: a recruiter opening an application must not silently launch a
    perturbation run. ``run_on_demand`` records where an explicit run lives.
    """

    status: Literal["no_stored_result"]
    tested: bool
    stability_score: float | None = None
    sensitivity: str | None = None
    reason: str
    run_on_demand_endpoint: str


class ApplicationFairnessContextResponse(BaseModel):
    """Fairness context for one application. Recruiter/HR only.

    Assembled from the existing ``FairnessEngine``; this response adds no
    fairness calculation of its own. Read-only: nothing in this flow changes a
    match score, an application status, a ranking or a screening result.
    """

    application: FairnessContextApplication
    job: FairnessContextJob
    screening_state: FairnessScreeningState
    population: FairnessPopulation
    sections: dict[str, FairnessSection]
    score_distribution: FairnessScoreDistribution | None = None
    group_analysis: FairnessGroupAnalysis | None = None
    alerts: list[FairnessAlertView] = Field(default_factory=list)
    job_description_bias: JobDescriptionBiasView | None = None
    adversarial: AdversarialContextView
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Fairness analysis is decision support for human review. It reports "
        "measured differences across the analyzed population, does not "
        "establish that any individual was treated unfairly, and does not "
        "make or change any hiring decision."
    )
