import enum


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "organization_admin"
    HR_MANAGER = "hr_manager"
    RECRUITER = "recruiter"
    CANDIDATE = "candidate"

    @classmethod
    def public_registration_roles(cls) -> set[str]:
        return {cls.CANDIDATE.value}

    @classmethod
    def organization_roles(cls) -> set[str]:
        return {cls.ORG_ADMIN.value, cls.HR_MANAGER.value, cls.RECRUITER.value}

    @classmethod
    def privileged_roles(cls) -> set[str]:
        return {cls.SUPER_ADMIN.value, cls.ORG_ADMIN.value, cls.HR_MANAGER.value, cls.RECRUITER.value}


# ─── Phase 12 – Assessment Platform ──────────────────────────────────


class AssessmentMode(str, enum.Enum):
    QUICK_TEST = "quick_test"
    TECHNICAL = "technical"
    APTITUDE = "aptitude"
    CODING = "coding"
    FULL_INTERVIEW = "full_technical_interview"
    CAMPUS = "campus_placement"
    EXPERIENCED = "experienced_developer"
    SYSTEM_DESIGN = "system_design"
    CUSTOM = "custom"


class AssessmentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AttemptStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ABANDONED = "abandoned"

    @classmethod
    def from_value(cls, value: str) -> "AttemptStatus | None":
        try:
            return cls(value)
        except ValueError:
            return None

    @classmethod
    def finished(cls) -> set[str]:
        """Statuses from which no further attempt work is possible.

        The platform already had a terminal set; this names it so the
        application integration and the attempt service agree on what "over" is
        rather than each spelling out its own literals.
        """
        return {cls.COMPLETED.value, cls.EXPIRED.value, cls.ABANDONED.value}


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    APTITUDE_QUANTITATIVE = "aptitude_quantitative"
    APTITUDE_LOGICAL = "aptitude_logical"
    APTITUDE_VERBAL = "aptitude_verbal"
    TECHNICAL_THEORY = "technical_theory"
    CODING = "coding"
    DEBUGGING = "debugging"
    CODE_OUTPUT = "code_output"
    SQL_MCQ = "sql_mcq"
    SQL_QUERY = "sql_query"
    SQL_DEBUG = "sql_debug"
    DATABASE_DESIGN = "database_design"
    SYSTEM_DESIGN = "system_design"
    SCENARIO = "scenario"
    CASE_STUDY = "case_study"
    RESUME_BASED = "resume_based"
    PROJECT_BASED = "project_based"
    BEHAVIORAL = "behavioral"
    SITUATIONAL_JUDGMENT = "situational_judgment"

    @classmethod
    def objective(cls) -> set[str]:
        """Auto-gradable against a stored correct answer."""
        return {
            cls.MCQ.value, cls.APTITUDE_QUANTITATIVE.value, cls.APTITUDE_LOGICAL.value,
            cls.APTITUDE_VERBAL.value, cls.TECHNICAL_THEORY.value, cls.CODE_OUTPUT.value,
            cls.SQL_MCQ.value, cls.SQL_DEBUG.value,
        }

    @classmethod
    def subjective(cls) -> set[str]:
        return {
            cls.SYSTEM_DESIGN.value, cls.SCENARIO.value, cls.CASE_STUDY.value,
            cls.RESUME_BASED.value, cls.PROJECT_BASED.value, cls.BEHAVIORAL.value,
            cls.SITUATIONAL_JUDGMENT.value, cls.DATABASE_DESIGN.value,
        }


class AssessmentDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class SkillCategory(str, enum.Enum):
    PROGRAMMING_LANGUAGES = "programming_languages"
    FRAMEWORKS = "frameworks"
    DATABASES = "databases"
    CLOUD = "cloud"
    DEVOPS = "devops"
    AI_ML = "ai_ml"
    TOOLS = "tools"
    SOFT_SKILLS = "soft_skills"


class Proficiency(str, enum.Enum):
    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    NATIVE = "native"


class SkillProficiency(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class NotificationType(str, enum.Enum):
    WELCOME = "welcome"
    PROFILE_UPDATED = "profile_updated"
    RESUME_UPLOADED = "resume_uploaded"
    AVATAR_CHANGED = "avatar_changed"
    NEW_FEATURE = "new_feature"
    APPLICATION_STATUS = "application_status"
    RESUME_PARSED = "resume_parsed"
    # Phase 11: interview lifecycle events for a candidate. Separate from
    # APPLICATION_STATUS so an interview update is distinguishable from a hiring
    # decision, and so each can carry its own dedupe key.
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_RESCHEDULED = "interview_rescheduled"
    INTERVIEW_CANCELLED = "interview_cancelled"
    INTERVIEW_COMPLETED = "interview_completed"
    # Phase 12: assessment lifecycle events for a candidate. Also separate from
    # APPLICATION_STATUS. An assessment result is decision-support evidence, and
    # its notification says so: it never announces a hiring outcome, because
    # the recruiter owns that.
    ASSESSMENT_ASSIGNED = "assessment_assigned"
    ASSESSMENT_COMPLETED = "assessment_completed"
    # A reschedule is its own event, exactly as an interview reschedule is. It
    # needs a separate value because the candidate is being told a *new* time, and
    # because the dedupe key is per-event: a reschedule of attempt 1 must not be
    # suppressed as a duplicate of the original assignment of that same attempt.
    ASSESSMENT_RESCHEDULED = "assessment_rescheduled"
    GENERAL = "general"
    # Post-Hiring & Onboarding Notifications
    OFFER_CREATED = "offer_created"
    OFFER_SENT = "offer_sent"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    OFFER_EXPIRING = "offer_expiring"
    DOCUMENT_SUBMITTED = "document_submitted"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_RESUBMIT = "document_resubmit"
    JOINING_CONFIRMED = "joining_confirmed"
    ONBOARDING_ASSIGNED = "onboarding_assigned"
    OFFER_VIEWED = "offer_viewed"
    ONBOARDING_STARTED = "onboarding_started"
    ONBOARDING_COMPLETED = "onboarding_completed"
    EMPLOYEE_ACTIVATED = "employee_activated" 


class ResumeStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SimulationStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def editable_states(cls) -> set[str]:
        """States that may still be edited through the Phase 1 CRUD API."""
        return {cls.DRAFT.value, cls.CANCELLED.value}


class SimulationEducationLevel(str, enum.Enum):
    """Education levels aligned with the platform's screening education scale."""
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"


class SimulationEducationRequirement(str, enum.Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    # Phase 11: recorded when an application-linked interview reaches
    # ``completed``. It is a factual statement that the interview happened, not
    # a verdict: it is reached by the recruiter marking the interview done and
    # never carries a hiring decision. Final selection/rejection stays with the
    # Phase 8 decision endpoints.
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    # Phase 13: the recruiter's explicit positive decision. Reached only by a
    # human through the decision endpoint, never by a score, an AI
    # recommendation, an assessment result or an interview signal.
    #
    # Deliberately distinct from OFFERED and HIRED. It records "we chose this
    # candidate" while the offer has not yet been extended and the candidate has
    # not yet started, so selecting is never conflated with hiring. It is
    # non-terminal: the recruiter may still extend the offer (OFFERED) or the
    # process can still fall through (REJECTED, typically position_filled).
    SELECTED = "selected"
    OFFERED = "offered"
    HIRED = "hired"
    WITHDRAWN = "withdrawn"

    @classmethod
    def from_value(cls, value: str) -> "ApplicationStatus | None":
        try:
            return cls(value)
        except ValueError:
            return None


class ScreeningStatus(str, enum.Enum):
    """Execution state of *automatic* application screening.

    Deliberately separate from ``ApplicationStatus``: screening is decision
    support and never drives the hiring lifecycle. ``SKIPPED`` is recorded when
    an application is already finalized by the time the worker runs.
    """
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @classmethod
    def from_value(cls, value: str) -> "ScreeningStatus | None":
        try:
            return cls(value)
        except ValueError:
            return None


class RejectionReason(str, enum.Enum):
    """Canonical rejection vocabulary recorded with a REJECTED decision.

    Phase 8 wires this existing vocabulary into the recruiter decision flow:
    the recruiter selects one of these codes, the code is validated server-side
    and stored in ``JobApplication.decision_reason_code``, and the candidate
    facing text is a fixed approved projection of the code (never the internal
    comment). Stored as the enum ``value`` string.
    """
    MISSING_REQUIRED_SKILL = "missing_required_skill"
    INSUFFICIENT_EXPERIENCE = "insufficient_experience"
    EDUCATION_REQUIREMENT = "education_requirement"
    LOW_JOB_MATCH = "low_job_match"
    FAILED_ASSESSMENT = "failed_assessment"
    FAILED_INTERVIEW = "failed_interview"
    POSITION_FILLED = "position_filled"
    OTHER = "other"

    @classmethod
    def from_value(cls, value: str) -> "RejectionReason | None":
        try:
            return cls(value)
        except ValueError:
            return None


class ApplicationDecisionType(str, enum.Enum):
    """Explicit human decisions a recruiter may record on an application.

    A decision is never inferred from a screening score, an AI recommendation
    or a fairness metric. Each value maps to exactly one application status
    (``ApplicationStatus``) or to a recorded no-status-change review, and the
    mapping is resolved server-side by the decision service.
    """
    KEEP_UNDER_REVIEW = "keep_under_review"
    SHORTLIST = "shortlist"
    REJECT = "reject"
    # Phase 13: the explicit positive decision, distinct from being hired.
    # Enumerating it here is what makes it a decision at all: the decision
    # service iterates this enum to build the server-authoritative option list,
    # so a SELECT can only ever be recorded by a person acting on the endpoint.
    SELECT = "select"
    HIRE = "hire"

    @property
    def target_status(self) -> ApplicationStatus:
        """The status this decision produces, or the status it re-affirms.

        ``KEEP_UNDER_REVIEW`` maps to ``UNDER_REVIEW``: it is a deliberate
        "continue reviewing" decision, not a status change, so the lifecycle
        service records it as a decision without a transition.
        """
        return {
            ApplicationDecisionType.KEEP_UNDER_REVIEW: ApplicationStatus.UNDER_REVIEW,
            ApplicationDecisionType.SHORTLIST: ApplicationStatus.SHORTLISTED,
            ApplicationDecisionType.REJECT: ApplicationStatus.REJECTED,
            ApplicationDecisionType.SELECT: ApplicationStatus.SELECTED,
            ApplicationDecisionType.HIRE: ApplicationStatus.HIRED,
        }[self]

    @property
    def requires_rejection_reason(self) -> bool:
        return self is ApplicationDecisionType.REJECT

    @classmethod
    def from_value(cls, value: str | None) -> "ApplicationDecisionType | None":
        if not value:
            return None
        val_str = str(value).lower().strip()
        if val_str in ("hire", "hired"):
            return cls.HIRE
        if val_str in ("select", "selected"):
            return cls.SELECT
        try:
            return cls(val_str)
        except ValueError:
            return None


class StrengthLevel(str, enum.Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    LOW = "low"


class HiringRecommendation(str, enum.Enum):
    STRONGLY_RECOMMEND = "strongly_recommend"
    RECOMMEND = "recommend"
    CONSIDER = "consider"
    NOT_RECOMMENDED = "not_recommended"

    @classmethod
    def from_value(cls, value: str | None) -> "HiringRecommendation | None":
        if not value:
            return None
        val_str = str(value).lower().strip()
        try:
            return cls(val_str)
        except ValueError:
            pass
        if "strongly" in val_str:
            return cls.STRONGLY_RECOMMEND
        if "not" in val_str or "reject" in val_str:
            return cls.NOT_RECOMMENDED
        if "recommend" in val_str or "hire" in val_str or "select" in val_str:
            return cls.RECOMMEND
        if "consider" in val_str or "borderline" in val_str:
            return cls.CONSIDER
        return None


class InterviewType(str, enum.Enum):
    MOCK = "mock"
    RECRUITER_SCHEDULED = "recruiter_scheduled"

    @classmethod
    def from_value(cls, value: str | None) -> "InterviewType | None":
        if not value:
            return cls.RECRUITER_SCHEDULED
        val = str(value).lower().strip()
        if val in ("mock", "ai_mock", "practice"):
            return cls.MOCK
        if val in ("recruiter_scheduled", "recruiter", "hr", "hr_scheduled", "scheduled"):
            return cls.RECRUITER_SCHEDULED
        try:
            return cls(value)
        except ValueError:
            return cls.RECRUITER_SCHEDULED


class InterviewStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @classmethod
    def from_value(cls, value: str) -> "InterviewStatus | None":
        """Resolve a stored status string, or ``None`` if unrecognized.

        Callers use this to read a persisted value without raising on legacy or
        unexpected data, mirroring ``ApplicationStatus.from_value``.
        """
        try:
            return cls(value)
        except ValueError:
            return None


class InterviewStage(str, enum.Enum):
    """Which hiring stage an interview belongs to.

    Deliberately separate from both ``InterviewStatus`` (scheduled / in progress
    / completed / cancelled) and ``ApplicationStatus``. Stage answers "whose
    interview is this", status answers "what is happening with this interview",
    and application status answers "where is this candidate in the funnel". A
    recruiter interview and an HR interview are two different interviews that can
    each be independently scheduled, cancelled or completed, so collapsing stage
    into the interview status would make "completed recruiter interview, HR
    interview not yet scheduled" inexpressible.

    ``RECRUITER`` is the default so every interview that predates this field --
    and every interview created without naming a stage -- keeps exactly the
    meaning it had: a first-round interview driven by the recruiter.
    """

    RECRUITER = "recruiter"
    HR = "hr"

    @classmethod
    def from_value(cls, value: str) -> "InterviewStage | None":
        try:
            return cls(value)
        except ValueError:
            return None

    @classmethod
    def default(cls) -> "InterviewStage":
        return cls.RECRUITER


class QuestionCategory(str, enum.Enum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    HR = "hr"
    SITUATIONAL = "situational"
    CODING = "coding"
    SYSTEM_DESIGN = "system_design"
    PROBLEM_SOLVING = "problem_solving"


class QuestionDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CodingProblemType(str, enum.Enum):
    CODING = "coding"
    MCQ = "mcq"
    SQL = "sql"
    DEBUGGING = "debugging"
    ALGORITHM = "algorithm"


class ReportType(str, enum.Enum):
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"
    HR = "hr"
    ADMIN = "admin"
    EXECUTIVE = "executive"


class ExportFormat(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


class SimulationReportType(str, enum.Enum):
    SIMULATION = "simulation"
    CANDIDATE_IMPACT = "candidate_impact"
    FAIRNESS_IMPACT = "fairness_impact"
    COMPARISON = "comparison"
    SANDBOX = "sandbox"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"


class SimulationReportStatus(str, enum.Enum):
    REQUESTED = "requested"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationReportFormat(str, enum.Enum):
    WEB = "web"
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"


class AlertType(str, enum.Enum):
    HIRING_DELAY = "hiring_delay"
    LOW_VOLUME = "low_volume"
    BIAS_WARNING = "bias_warning"
    SECURITY_EVENT = "security_event"
    SYSTEM_HEALTH = "system_health"
    SCHEDULE_CONFLICT = "schedule_conflict"
    JOB_EXPIRING = "job_expiring"


class InsightCategory(str, enum.Enum):
    HIRING_DEMAND = "hiring_demand"
    CANDIDATE_SUCCESS = "candidate_success"
    SKILL_TREND = "skill_trend"
    BOTTLENECK = "bottleneck"
    PERFORMANCE = "performance"
    TREND = "trend"


# ── Phase 1: Identity + Organization + Authorization ───────────────


class AccountStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class OrganizationStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class MembershipStatus(str, enum.Enum):
    INVITED = "invited"
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ── Employee Access Request ────────────────────────────────────────


class AccessRequestStatus(str, enum.Enum):
    """State machine for employee organization access requests."""
    PENDING_EMAIL_VERIFICATION = "pending_email_verification"
    EMAIL_VERIFIED = "email_verified"
    PENDING_ADMIN_APPROVAL = "pending_admin_approval"
    APPROVED = "approved"
    ACCOUNT_ACTIVATION_PENDING = "account_activation_pending"
    ACTIVATED = "activated"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @classmethod
    def terminal(cls) -> set[str]:
        return {cls.ACTIVATED.value, cls.REJECTED.value, cls.EXPIRED.value, cls.CANCELLED.value}

    @classmethod
    def active(cls) -> set[str]:
        return {
            cls.PENDING_EMAIL_VERIFICATION.value,
            cls.EMAIL_VERIFIED.value,
            cls.PENDING_ADMIN_APPROVAL.value,
            cls.APPROVED.value,
            cls.ACCOUNT_ACTIVATION_PENDING.value,
        }


class AccessRequestRole(str, enum.Enum):
    """Roles that can be requested/assigned via access request flow."""
    HR_MANAGER = "hr_manager"
    RECRUITER = "recruiter"


class AuditEventType(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    EMAIL_VERIFICATION = "email_verification"
    INVITATION_CREATED = "invitation_created"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    MEMBERSHIP_SUSPENDED = "membership_suspended"
    MEMBERSHIP_REVOKED = "membership_revoked"
    MEMBERSHIP_REACTIVATED = "membership_reactivated"
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    ACCOUNT_REACTIVATED = "account_reactivated"
    AUTHORIZATION_FAILURE = "authorization_failure"
    TOKEN_REFRESH = "token_refresh"
    LOGOUT_ALL = "logout_all"
    SIMULATION_CREATED = "simulation_created"
    SIMULATION_UPDATED = "simulation_updated"
    SIMULATION_DELETED = "simulation_deleted"
    SIMULATION_VALIDATED = "simulation_validated"
    SIMULATION_STATUS_CHANGED = "simulation_status_changed"
    SIMULATION_RUN_STARTED = "simulation_run_started"
    SIMULATION_RUN_COMPLETED = "simulation_run_completed"
    SIMULATION_RUN_FAILED = "simulation_run_failed"
    SIMULATION_RUN_CANCELLED = "simulation_run_cancelled"
    RANKING_IMPACT_VIEWED = "ranking_impact_viewed"
    REQUIREMENT_IMPACT_VIEWED = "requirement_impact_viewed"
    REQUIREMENT_IMPACT_ANALYSIS_GENERATED = "requirement_impact_analysis_generated"
    THRESHOLD_IMPACT_VIEWED = "threshold_impact_viewed"
    SHORTLIST_IMPACT_VIEWED = "shortlist_impact_viewed"
    THRESHOLD_SHORTLIST_IMPACT_VIEWED = "threshold_shortlist_impact_viewed"
    FAIRNESS_IMPACT_VIEWED = "fairness_impact_viewed"
    EXPLAINABILITY_IMPACT_VIEWED = "explainability_impact_viewed"
    SKILL_IMPACT_VIEWED = "skill_impact_viewed"
    SIMULATION_COMPARISON_CREATED = "simulation_comparison_created"
    SIMULATION_SHORTLIST_APPLIED = "simulation_shortlist_applied"
    SIMULATION_NL_REQUEST = "simulation_nl_request"
    SIMULATION_NL_PROPOSAL_CREATED = "simulation_nl_proposal_created"
    SIMULATION_NL_CONFIRMED = "simulation_nl_confirmed"
    SIMULATION_NL_CANCELLED = "simulation_nl_cancelled"
    SANDBOX_CREATED = "sandbox_created"
    SANDBOX_UPDATED = "sandbox_updated"
    SANDBOX_ARCHIVED = "sandbox_archived"
    SCENARIO_ADDED_TO_SANDBOX = "scenario_added_to_sandbox"
    SCENARIO_BRANCHED = "scenario_branched"
    SCENARIO_DUPLICATED = "scenario_duplicated"
    SANDBOX_COMPARISON_STARTED = "sandbox_comparison_started"
    SIMULATION_REPORT_CREATED = "simulation_report_created"
    SIMULATION_REPORT_VIEWED = "simulation_report_viewed"
    SIMULATION_REPORT_EXPORTED = "simulation_report_exported"
    SIMULATION_REPORT_DELETED = "simulation_report_deleted"
    SIMULATION_REPORT_GENERATION_FAILED = "simulation_report_generation_failed"
    EXPERIMENT_CREATED = "experiment_created"
    EXPERIMENT_MODIFIED = "experiment_modified"
    EXPERIMENT_EXECUTED = "experiment_executed"
    EXPERIMENT_CANCELLED = "experiment_cancelled"
    EXPERIMENT_VIEWED = "experiment_viewed"
    EXPERIMENT_EXPORTED = "experiment_exported"
    EXPERIMENT_REPORT_GENERATED = "experiment_report_generated"
    ACCESS_REQUEST_CREATED = "access_request_created"
    ACCESS_EMAIL_VERIFIED = "access_email_verified"
    ACCESS_REQUEST_APPROVED = "access_request_approved"
    ACCESS_REQUEST_REJECTED = "access_request_rejected"
    ACCESS_REQUEST_EXPIRED = "access_request_expired"
    ACCESS_REQUEST_CANCELLED = "access_request_cancelled"
    ACCOUNT_ACTIVATION_STARTED = "account_activation_started"
    ACCOUNT_ACTIVATED = "account_activated"
    APPLICATION_CREATED = "application_created"
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    APPLICATION_SCREENED = "application_screened"
    APPLICATION_SCREENING_FAILED = "application_screening_failed"
    APPLICATION_EXPLANATION_VIEWED = "application_explanation_viewed"
    CANDIDATE_EXPLANATION_VIEWED = "candidate_explanation_viewed"
    APPLICATION_FAIRNESS_CONTEXT_VIEWED = "application_fairness_context_viewed"
    # Phase 8: explicit, human recruiter decisions. Distinct from
    # APPLICATION_STATUS_CHANGED, which is logged for every transition.
    APPLICATION_DECISION_RECORDED = "application_decision_recorded"
    APPLICATION_REJECTED = "application_rejected"
    # Phase 13: the explicit positive decision. Recorded alongside
    # APPLICATION_DECISION_RECORDED so "who selected this candidate" stays
    # answerable, and kept distinct from the generic status change.
    APPLICATION_SELECTED = "application_selected"
    # Phase 11: application-linked interview lifecycle. Distinct from
    # APPLICATION_STATUS_CHANGED, which records only the status flip the
    # lifecycle service performed.
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_RESCHEDULED = "interview_rescheduled"
    INTERVIEW_CANCELLED = "interview_cancelled"
    INTERVIEW_COMPLETED = "interview_completed"
    INTERVIEW_EVIDENCE_VIEWED = "interview_evidence_viewed"
    # Phase 14: interview-room attendance. Recorded when a participant enters the
    # shared room, so "the candidate never joined" and "we have no record either
    # way" stay distinguishable -- the difference matters when a recruiter later
    # completes an interview nobody is recorded as having attended.
    INTERVIEW_JOINED = "interview_joined"
    # Phase 15: recruiter interview stage. Recorded when a recruiter saves manual
    # technical feedback/evaluation notes on a real interview. Deliberately
    # distinct from INTERVIEW_COMPLETED: recording an assessment of an interview is
    # not the same act as asserting the interview happened, and the two must stay
    # separable in the trail.
    INTERVIEW_FEEDBACK_RECORDED = "interview_feedback_recorded"
    # Phase 15: the recruiter advanced the candidate to the HR interview stage.
    # Recorded separately from APPLICATION_STATUS_CHANGED because advancing does
    # not change the application status (it remains the factual ``interviewed``);
    # it records eligibility for a second, HR-owned interview round.
    APPLICATION_ADVANCED_TO_HR = "application_advanced_to_hr"
    # Phase 12: assessment lifecycle. ASSESSMENT_RESULT_VIEWED is recorded when
    # staff open the detailed result, so "who looked at this candidate's
    # assessment" is answerable after the fact.
    ASSESSMENT_ASSIGNED = "assessment_assigned"
    # A reschedule of an existing assignment, mirroring INTERVIEW_RESCHEDULED and
    # deliberately distinct from ASSESSMENT_ASSIGNED: "this candidate was given
    # this assessment" and "this assessment was moved to a new time" are separate
    # facts, and a reschedule updates a row rather than creating one, so nothing
    # else in the audit trail would record that the time changed.
    ASSESSMENT_RESCHEDULED = "assessment_rescheduled"
    # Revised Phase 14: HR organization-level oversight. Recorded when HR opens
    # the read-only HR application oversight view, so "which HR user reviewed
    # this candidate" stays answerable. Deliberately NOT reusing
    # APPLICATION_EXPLANATION_VIEWED or the generic APPLICATION_STATUS_CHANGED:
    # an oversight read is neither a status change nor necessarily a request for
    # the explainability payload, and the two must be distinguishable in audit.
    HR_APPLICATION_VIEWED = "hr_application_viewed"
    HR_OVERVIEW_VIEWED = "hr_overview_viewed"
    ASSESSMENT_STARTED = "assessment_started"
    ASSESSMENT_SUBMITTED = "assessment_submitted"
    ASSESSMENT_COMPLETED = "assessment_completed"
    ASSESSMENT_EVIDENCE_VIEWED = "assessment_evidence_viewed"
    ASSESSMENT_RESULT_VIEWED = "assessment_result_viewed"


# ── Phase 4: Ranking Impact Analysis ──────────────────────────────


class CandidateMovementCategory(str, enum.Enum):
    """Deterministic classification of how a candidate moved between rankings.

    Thresholds are configurable and centralized in the ranking impact analyzer.
    The default configuration uses:
        SIGNIFICANTLY_IMPROVED: rank_change >= 10
        IMPROVED: rank_change >= 3
        UNCHANGED: -2 <= rank_change <= 2
        DECLINED: rank_change <= -3
        SIGNIFICANTLY_DECLINED: rank_change <= -10
    """

    SIGNIFICANTLY_IMPROVED = "significantly_improved"
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    DECLINED = "declined"
    SIGNIFICANTLY_DECLINED = "significantly_declined"


class ImpactSeverity(str, enum.Enum):
    """Neutral magnitude categories for ranking impact visualization.

    These describe the magnitude of movement, NOT whether the change is
    good or bad. HIGH_RANK_MOVEMENT means large movement occurred — it
    must NOT mean "bad strategy" or "good strategy".
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ImpactType(str, enum.Enum):
    """Types of ranking impact analysis metrics.

    Each type represents a distinct analytical dimension of the
    simulation's effect on candidate rankings.
    """

    RANKING_DISTRIBUTION = "ranking_distribution"
    SCORE_DISTRIBUTION = "score_distribution"
    TOP_MOVERS = "top_movers"
    SHORTLIST_MOVEMENT = "shortlist_movement"
    QUALIFICATION_MOVEMENT = "qualification_movement"
    RANK_STABILITY = "rank_stability"
    THRESHOLD_IMPACT = "threshold_impact"


# ── Phase 14: Advanced Simulation & Research Intelligence ──────────


class ExperimentType(str, enum.Enum):
    """Types of controlled parameter experiments."""

    THRESHOLD_SWEEP = "threshold_sweep"
    WEIGHT_SWEEP = "weight_sweep"
    SHORTLIST_SWEEP = "shortlist_sweep"
    REQUIREMENT_SWEEP = "requirement_sweep"
    ONE_PARAMETER_SENSITIVITY = "one_parameter_sensitivity"
    MULTI_PARAMETER_SENSITIVITY = "multi_parameter_sensitivity"
    ROBUSTNESS_TEST = "robustness_test"
    FAIRNESS_SENSITIVITY = "fairness_sensitivity"
    RANKING_STABILITY = "ranking_stability"


class ExperimentStatus(str, enum.Enum):
    """Lifecycle states for a research experiment."""

    DRAFT = "draft"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PerturbationType(str, enum.Enum):
    """Types of parameter perturbations."""

    NUMERIC_DELTA = "numeric_delta"
    NUMERIC_PERCENTAGE = "numeric_percentage"
    NUMERIC_EXPLICIT = "numeric_explicit"
    CATEGORICAL = "categorical"
    REQUIREMENT_ADD = "requirement_add"
    REQUIREMENT_REMOVE = "requirement_remove"
    REQUIREMENT_PROMOTE = "requirement_promote"
    REQUIREMENT_DEMOTE = "requirement_demote"


class SensitivityDimension(str, enum.Enum):
    """Parameter dimensions that can be swept."""

    THRESHOLD = "threshold"
    SHORTLIST_SIZE = "shortlist_size"
    SKILLS_WEIGHT = "skills_weight"
    EXPERIENCE_WEIGHT = "experience_weight"
    EDUCATION_WEIGHT = "education_weight"
    PROJECTS_WEIGHT = "projects_weight"
    CERTIFICATIONS_WEIGHT = "certifications_weight"
    LOCATION_WEIGHT = "location_weight"
    EMPLOYMENT_TYPE_WEIGHT = "employment_type_weight"
    SEMANTIC_WEIGHT = "semantic_weight"
    MANDATORY_SKILLS = "mandatory_skills"
    PREFERRED_SKILLS = "preferred_skills"
    EXPERIENCE_MIN = "experience_min"
    EDUCATION_LEVEL = "education_level"


# ── Legacy role name aliases for backward compatibility ────────────


LEGACY_ROLE_MAP: dict[str, str] = {
    "admin": RoleName.ORG_ADMIN.value,
    "hr": RoleName.HR_MANAGER.value,
    "recruiter": RoleName.RECRUITER.value,
    "candidate": RoleName.CANDIDATE.value,
}


# ── Post-Hiring & Employee Onboarding Enums ────────────────────────


class OfferStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    SENT = "sent"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class DocumentType(str, enum.Enum):
    GOV_ID = "gov_id"
    ADDRESS_PROOF = "address_proof"
    EDUCATION = "education"
    PREVIOUS_EMPLOYMENT = "previous_employment"
    EXPERIENCE_CERTIFICATE = "experience_certificate"
    OTHER = "other"


class DocumentVerificationStatus(str, enum.Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    RESUBMISSION_REQUIRED = "resubmission_required"


class EmploymentStatus(str, enum.Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class OnboardingStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OnboardingTaskCategory(str, enum.Enum):
    DOCUMENTATION = "documentation"
    IT_SETUP = "it_setup"
    TRAINING = "training"
    ORIENTATION = "orientation"
    POLICY = "policy"
    HR_ADMIN = "hr_admin"
