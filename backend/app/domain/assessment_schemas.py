"""Phase 12 – Assessment Platform schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentSectionConfig(BaseModel):
    question_type: str = Field(..., description="QuestionType value, e.g. mcq / coding / sql_query")
    count: int = Field(5, ge=1, le=50)
    skills: list[str] = Field(default_factory=list)
    difficulty: str = Field("medium", description="easy | medium | hard | expert | mixed")
    time_limit_seconds: int | None = None
    points_per_question: float = Field(1.0, ge=0.1)


class AssessmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = None
    job_id: uuid.UUID | None = None
    mode: str = "custom"
    duration_minutes: int = Field(45, ge=5, le=480)
    sections: list[AssessmentSectionConfig] = Field(..., min_length=1)
    passing_score: int = Field(60, ge=0, le=100)
    negative_marking: float = Field(0.0, ge=0.0, le=2.0)
    allowed_attempts: int = Field(1, ge=1, le=10)
    adaptive: bool = False
    shuffle_questions: bool = True
    shuffle_options: bool = False


class AssessmentGenerateRequest(AssessmentCreateRequest):
    pass


class QuestionPublic(BaseModel):
    id: uuid.UUID
    question_type: str
    skill: str
    topic: str
    difficulty: str
    question_text: str
    options: list[str] = []
    code_snippet: str | None = None
    language: str | None = None
    starter_code: str | None = None
    tables: list | None = None
    schema_sql: str | None = None
    estimated_time_seconds: int = 90
    points: float = 1.0
    section: str = "general"
    order_index: int = 0


class AssessmentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    job_id: uuid.UUID | None = None
    job_title: str | None = None
    mode: str
    status: str
    duration_minutes: int
    passing_score: int
    negative_marking: float
    allowed_attempts: int
    adaptive: bool
    shuffle_questions: bool
    shuffle_options: bool
    created_by: uuid.UUID | None = None
    question_count: int = 0
    attempt_count: int = 0
    created_at: datetime | None = None


class AssessmentListResponse(BaseModel):
    items: list[AssessmentResponse]
    total: int


class AttemptStartResponse(BaseModel):
    attempt_id: uuid.UUID
    assessment_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    expires_at: datetime | None = None
    total_questions: int
    instructions: list[str] = []
    sections: list[str] = []


class AnswerSubmitRequest(BaseModel):
    question_id: uuid.UUID
    answer: dict = Field(default_factory=dict)
    time_taken_seconds: int | None = None


class EvaluationOut(BaseModel):
    score: float
    is_correct: bool | None = None
    feedback: str | None = None
    dimensions: dict | None = None


class AnswerResultResponse(BaseModel):
    answer_id: uuid.UUID
    evaluation: EvaluationOut
    correct_answer_revealed: bool = False
    explanation: str | None = None
    next_question: QuestionPublic | None = None
    questions_remaining: int = 0
    progress: dict = Field(default_factory=dict)


class CodeRunRequest(BaseModel):
    question_id: uuid.UUID
    language: str = "python"
    code: str


class TestResultOut(BaseModel):
    index: int
    passed: bool
    input_preview: str | None = None
    expected: str | None = None
    received: str | None = None
    hidden: bool = True


class CodeRunResponse(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: int = 0
    passed_count: int = 0
    total_count: int = 0
    test_results: list[TestResultOut] = []
    timed_out: bool = False
    sandbox_mode: str = "local"


class IntegrityEventRequest(BaseModel):
    event_type: str
    detail: str | None = None


class SectionScoreOut(BaseModel):
    section: str
    question_type: str
    earned: float
    possible: float
    percentage: float
    accuracy: float | None = None


class ResultResponse(BaseModel):
    attempt_id: uuid.UUID
    assessment_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str
    submitted_at: datetime | None = None
    overall_score: float
    passing_score: int
    passed: bool
    section_scores: list[SectionScoreOut] = []
    skill_scores: dict = {}
    strong_skills: list[str] = []
    weak_skills: list[str] = []
    recommended_topics: list[str] = []
    accuracy: float = 0.0
    time_management: float = 0.0
    readiness_level: str = "not_ready"
    recommendation: str = "consider"
    ai_summary: str | None = None
    integrity_flags: int = 0
    per_question: list[dict] = []


class AttemptListItem(BaseModel):
    attempt_id: uuid.UUID
    assessment_id: uuid.UUID
    assessment_title: str
    mode: str
    status: str
    started_at: datetime | None = None
    expires_at: datetime | None = None
    submitted_at: datetime | None = None
    overall_score: float | None = None
    passed: bool | None = None
    # Phase 12. Set when the attempt was assigned from an application, so the
    # candidate's list can say which application the task belongs to. ``None``
    # for a self-started practice attempt, which belongs to no application.
    application_id: uuid.UUID | None = None
    #: When the recruiter scheduled the assessment (the assignment time). ``None``
    #: for a self-started practice attempt, which nobody scheduled. This is the
    #: schedule the candidate sees; it is not a deadline, because the attempt has
    #: none until the candidate starts it.
    scheduled_at: datetime | None = None
    #: The date and time the recruiter scheduled this assessment for. ``None`` when
    #: no time was chosen, which is a real state rather than a missing value: the
    #: candidate is told the assessment is waiting, not that it is due at some
    #: invented moment. Never defaulted from ``scheduled_at``, because "the moment
    #: it was assigned" and "the time it is due" are different facts.
    scheduled_for: datetime | None = None
    #: The link the candidate opens to take this attempt. Returned by the API so
    #: the page and the notification both point at exactly the same place rather
    #: than each rebuilding a route.
    assessment_link: str | None = None
    #: Job the assignment belongs to, when it came from an application, so the
    #: candidate can tell which role an assessment is for.
    job_title: str | None = None


class AttemptListResponse(BaseModel):
    items: list[AttemptListItem]
    total: int


class CandidateComparisonRow(BaseModel):
    candidate_id: uuid.UUID
    candidate_name: str
    attempts: int
    best_score: float
    latest_score: float
    recommendation: str


class AnalyticsResponse(BaseModel):
    assessment_id: uuid.UUID
    title: str
    total_assigned: int
    completed: int
    in_progress: int
    completion_rate: float
    average_score: float
    pass_rate: float
    median_time_minutes: float
    skill_performance: dict = {}
    question_accuracy: list[dict] = []
    difficulty_performance: dict = {}
    coding_success_rate: float = 0.0
    candidates: list[CandidateComparisonRow] = []
