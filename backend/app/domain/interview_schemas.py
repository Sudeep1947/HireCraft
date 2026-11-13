import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Request Schemas ───────────────────────────────────────────────


class InterviewGenerateRequest(BaseModel):
    job_id: uuid.UUID
    categories: list[str] = Field(
        default=["technical", "behavioral"],
        description="Question categories to generate",
    )
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|mixed)$")
    count: int = Field(default=10, ge=1, le=50)
    candidate_id: uuid.UUID | None = Field(
        default=None,
        description="If provided, generates personalized questions",
    )


class InterviewScheduleRequest(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=180)
    categories: list[str] = Field(default=["technical", "behavioral"])
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|mixed)$")
    question_count: int = Field(default=10, ge=1, le=50)


class InterviewStartRequest(BaseModel):
    interview_id: uuid.UUID


class InterviewAnswerRequest(BaseModel):
    question_id: uuid.UUID
    answer_text: str = Field(..., min_length=1, max_length=10000)
    time_taken_seconds: int | None = Field(default=None, ge=0)


class InterviewCompleteRequest(BaseModel):
    interview_id: uuid.UUID


class ScorecardCreateRequest(BaseModel):
    technical_skills: int = Field(default=0, ge=0, le=100)
    communication: int = Field(default=0, ge=0, le=100)
    teamwork: int = Field(default=0, ge=0, le=100)
    leadership: int = Field(default=0, ge=0, le=100)
    problem_solving: int = Field(default=0, ge=0, le=100)
    culture_fit: int = Field(default=0, ge=0, le=100)
    learning_ability: int = Field(default=0, ge=0, le=100)
    recommendation: str = Field(default="consider")
    hiring_confidence: int = Field(default=50, ge=0, le=100)
    recruiter_notes: str | None = None


class InterviewNotesRequest(BaseModel):
    notes: str = Field(..., min_length=1, max_length=10000)


class CodingAssessmentGenerateRequest(BaseModel):
    interview_id: uuid.UUID
    category: str = Field(default="coding")
    difficulty: str = Field(default="medium")
    count: int = Field(default=3, ge=1, le=10)


class CodingSubmissionRequest(BaseModel):
    assessment_id: uuid.UUID
    solution: str = Field(..., min_length=1)


# ─── Response Schemas ──────────────────────────────────────────────


class QuestionResponse(BaseModel):
    id: uuid.UUID
    question_text: str
    category: str
    difficulty: str
    order_index: int
    context: dict | None = None

    model_config = {"from_attributes": True}


class EvaluationResponse(BaseModel):
    id: uuid.UUID
    technical_accuracy: int
    completeness: int
    communication: int
    problem_solving: int
    confidence: int
    relevance: int
    overall_score: int
    feedback: str | None = None
    improvement_suggestions: list[str] | None = None
    follow_up_questions: list[str] | None = None

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    id: uuid.UUID
    answer_text: str
    time_taken_seconds: int | None = None
    evaluation: EvaluationResponse | None = None

    model_config = {"from_attributes": True}


class QuestionWithAnswerResponse(BaseModel):
    id: uuid.UUID
    question_text: str
    category: str
    difficulty: str
    order_index: int
    context: dict | None = None
    answer: AnswerResponse | None = None

    model_config = {"from_attributes": True}


class ScorecardResponse(BaseModel):
    id: uuid.UUID
    interview_id: uuid.UUID
    technical_skills: int
    communication: int
    teamwork: int
    leadership: int
    problem_solving: int
    culture_fit: int
    learning_ability: int
    overall_score: int
    recommendation: str
    hiring_confidence: int
    recruiter_notes: str | None = None
    ai_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewDetailResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str = ""
    candidate_id: uuid.UUID
    candidate_name: str = ""
    candidate_email: str = ""
    # The application this interview was scheduled from, when it was scheduled
    # through the application-driven flow (``Interview.application_id``). Null
    # for a practice/mock interview and for any interview that predates that
    # flow -- the column is nullable for exactly that reason.
    #
    # Safe for both roles: the recruiter needs it to navigate back to the
    # application the interview belongs to, and a candidate already sees the
    # same id on their own application. It identifies *the record*, and carries
    # no score, note or decision.
    application_id: uuid.UUID | None = None
    recruiter_id: uuid.UUID | None = None
    recruiter_name: str = ""
    interview_type: str
    stage: str = "recruiter"
    status: str
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_minutes: int | None = None
    total_questions: int
    questions_answered: int
    questions: list[QuestionWithAnswerResponse] = []
    scorecard: ScorecardResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewListItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str = ""
    candidate_id: uuid.UUID
    candidate_name: str = ""
    # See ``InterviewDetailResponse.application_id``: the application this
    # interview belongs to, or None for a practice/mock interview.
    application_id: uuid.UUID | None = None
    interview_type: str
    stage: str = "recruiter"
    status: str
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    # The scheduled length and the interviewer's display name, so a list row
    # (the candidate's Interviews page, the recruiter's workspace) can render
    # "30 minutes · with Ada Lovelace" without a second request. Additive: both
    # default to a value that keeps every older client working unchanged.
    duration_minutes: int | None = None
    recruiter_name: str = ""
    total_questions: int
    questions_answered: int
    overall_score: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewListResponse(BaseModel):
    items: list[InterviewListItem]
    total: int


class InterviewGenerateResponse(BaseModel):
    interview_id: uuid.UUID
    questions: list[QuestionResponse]
    total_questions: int
    categories: list[str]
    difficulty: str


class MockInterviewStartResponse(BaseModel):
    interview_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    first_question: QuestionResponse
    total_questions: int
    message: str


class AnswerSubmitResponse(BaseModel):
    answer_id: uuid.UUID
    evaluation: EvaluationResponse
    next_question: QuestionResponse | None = None
    questions_remaining: int = 0


class InterviewCompleteResponse(BaseModel):
    interview_id: uuid.UUID
    overall_score: int
    scorecard: ScorecardResponse
    feedback_summary: str
    strong_areas: list[str]
    weak_areas: list[str]
    improvement_suggestions: list[str]


class CodingAssessmentResponse(BaseModel):
    id: uuid.UUID
    problem_title: str
    problem_description: str
    difficulty: str
    category: str
    candidate_solution: str | None = None
    is_correct: bool | None = None
    score: int

    model_config = {"from_attributes": True}


class CodingSubmissionResponse(BaseModel):
    assessment_id: uuid.UUID
    is_correct: bool
    score: int
    feedback: str
    expected_approach: str


# ─── Dashboard & Analytics ─────────────────────────────────────────


class InterviewDashboardResponse(BaseModel):
    total_interviews: int = 0
    upcoming_interviews: int = 0
    completed_interviews: int = 0
    average_score: float = 0.0
    recent_interviews: list[InterviewListItem] = []
    upcoming: list[InterviewListItem] = []
    score_distribution: dict = {}
    category_performance: dict = {}


class InterviewAnalyticsResponse(BaseModel):
    total_interviews: int = 0
    completion_rate: float = 0.0
    average_score: float = 0.0
    median_score: float = 0.0
    score_distribution: dict = {}
    category_averages: dict = {}
    difficulty_distribution: dict = {}
    recommendation_breakdown: dict = {}
    skill_performance: dict = {}
    hiring_prediction: dict = {}
    trends: list[dict] = []


class CandidateInterviewDashboardResponse(BaseModel):
    total_interviews: int = 0
    mock_interviews: int = 0
    scheduled_interviews: int = 0
    average_score: float = 0.0
    strong_areas: list[str] = []
    weak_areas: list[str] = []
    improvement_suggestions: list[str] = []
    upcoming_interviews: list[InterviewListItem] = []
    recent_scores: list[dict] = []
    learning_resources: list[dict] = []
