"""Natural Language Simulation Service.

Orchestrates the full NL simulation pipeline:
1. Interpret natural language → structured intent
2. Load job context → build proposal
3. Validate proposed configuration
4. Create scenario on confirmation
5. Execute simulation via existing engine
6. Generate grounded explanation of results

Architecture:

    SimulationIntent
          ↓
    Job Context + Baseline Config
          ↓
    Proposal Generation
          ↓
    Configuration Validation
          ↓
    Scenario Creation (on confirm)
          ↓
    Existing Simulation Engine
          ↓
    Result Grounding → NL Explanation
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.enums import AuditEventType, SimulationStatus
from app.domain.models import Job, User
from app.domain.simulation_intent_schemas import (
    ChangeType,
    Clarification,
    EducationChange,
    ExperienceChange,
    IntentStatus,
    NLConfirmRequest,
    NLConfirmResponse,
    NLExplainRequest,
    NLExplainResponse,
    NLInterpretRequest,
    NLInterpretResponse,
    PresetChange,
    ProposalChange,
    RequirementChange,
    RequirementOperation,
    ScoringWeightChange,
    ShortlistChange,
    SimulationIntent,
    ThresholdChange,
)
from app.domain.simulation_schemas import (
    SimulationConfiguration,
    SimulationScoringWeights,
    SimulationScenarioCreate,
)
from app.services.audit_service import AuditService
from app.services.simulation.configuration_validator import (
    DEFAULT_SHORTLIST_SIZE,
    DEFAULT_THRESHOLD,
    WEIGHT_DIMENSIONS,
    SimulationConfigurationValidator,
)
from app.services.simulation.execution_service import SimulationExecutionService
from app.services.simulation.simulation_intent_interpreter import (
    SimulationIntentInterpreter,
)
from app.services.simulation.simulation_service import SimulationScenarioService

logger = get_logger(__name__)

# ─── Preset Configurations ──────────────────────────────────────────

PRESETS: dict[str, dict[str, Any]] = {
    "SKILLS_FOCUSED": {
        "scoring_weights": {
            "skills": 0.50,
            "experience": 0.15,
            "education": 0.10,
            "projects": 0.15,
            "certifications": 0.05,
            "location": 0.02,
            "employment_type": 0.01,
            "semantic": 0.02,
        }
    },
    "EXPERIENCE_FOCUSED": {
        "scoring_weights": {
            "skills": 0.25,
            "experience": 0.45,
            "education": 0.10,
            "projects": 0.10,
            "certifications": 0.05,
            "location": 0.02,
            "employment_type": 0.01,
            "semantic": 0.02,
        }
    },
    "BALANCED": {
        "scoring_weights": {
            "skills": 0.35,
            "experience": 0.25,
            "education": 0.15,
            "projects": 0.15,
            "certifications": 0.05,
            "location": 0.02,
            "employment_type": 0.01,
            "semantic": 0.02,
        }
    },
    "PROJECT_FOCUSED": {
        "scoring_weights": {
            "skills": 0.30,
            "experience": 0.15,
            "education": 0.10,
            "projects": 0.35,
            "certifications": 0.05,
            "location": 0.02,
            "employment_type": 0.01,
            "semantic": 0.02,
        }
    },
}

# ─── Weight Display Names ────────────────────────────────────────────

WEIGHT_LABELS: dict[str, str] = {
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "certifications": "Certifications",
    "location": "Location",
    "employment_type": "Employment Type",
    "semantic": "Semantic Match",
}


class SimulationNLService:
    """Orchestrates the natural-language simulation pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._interpreter = SimulationIntentInterpreter()

    async def interpret(
        self,
        request: NLInterpretRequest,
        current_user: User,
    ) -> NLInterpretResponse:
        """Interpret a natural-language request into a structured proposal."""
        # Load job context
        job = await self._load_job(request.job_id, current_user)

        # Load baseline config from the job's latest simulation or defaults
        baseline_config = await self._load_baseline_config(job)

        # Interpret via LLM / deterministic parser
        job_context = self._build_job_context(job, baseline_config)
        intent = await self._interpreter.interpret(
            message=request.message,
            job_id=request.job_id,
            job_context=job_context,
        )

        # Audit the interpretation
        await self._audit(
            AuditEventType.SIMULATION_NL_REQUEST,
            current_user,
            {
                "job_id": str(request.job_id),
                "message_length": len(request.message),
                "intent_status": intent.status.value,
                "changes_count": len(intent.changes),
                "confidence": intent.confidence,
            },
        )

        # If ambiguous or unsupported, return as-is
        if intent.status in (IntentStatus.AMBIGUOUS, IntentStatus.UNSUPPORTED):
            return NLInterpretResponse(
                intent=intent,
                requires_confirmation=False,
                can_execute=False,
                message=self._build_clarification_message(intent),
            )

        # Build proposal from intent + baseline
        proposal = self._build_proposal(intent, baseline_config)

        # Validate the proposed configuration
        proposed_config = self._apply_intent_to_config(intent, baseline_config)
        valid, issues = SimulationConfigurationValidator.validate(proposed_config)

        if not valid:
            return NLInterpretResponse(
                intent=intent,
                proposal=proposal,
                validation_errors=[
                    {"field": iss.field, "message": iss.message} for iss in issues
                ],
                requires_confirmation=True,
                can_execute=False,
                message="The proposed configuration has validation issues.",
            )

        # Mark as validated
        intent.status = IntentStatus.VALIDATED
        return NLInterpretResponse(
            intent=intent,
            proposal=proposal,
            requires_confirmation=True,
            can_execute=True,
            message=self._build_proposal_message(intent, proposal),
        )

    async def confirm(
        self,
        request: NLConfirmRequest,
        current_user: User,
    ) -> NLConfirmResponse:
        """Confirm and create a simulation scenario from the interpreted intent."""
        job = await self._load_job(request.job_id, current_user)
        baseline_config = await self._load_baseline_config(job)

        # Build configuration
        if request.edited_config:
            config_dict = request.edited_config
        else:
            config_dict = self._apply_intent_to_config(request.intent, baseline_config)

        # Validate
        valid, issues = SimulationConfigurationValidator.validate(config_dict)
        if not valid:
            error_msgs = "; ".join(i.message for i in issues)
            raise ValueError(f"Configuration validation failed: {error_msgs}")

        # Create scenario
        scenario_service = SimulationScenarioService(self._db)
        create_data = SimulationScenarioCreate(
            job_id=request.job_id,
            name=request.scenario_name,
            description=request.scenario_description
            or f"Created via natural language: {request.intent.natural_language_request[:200]}",
            simulation_config=SimulationConfiguration(**config_dict),
            metadata={
                "source": "natural_language",
                "nl_request": request.intent.natural_language_request[:1000],
                "intent_changes": [
                    c.model_dump() for c in request.intent.changes
                ],
                "nl_prompt_version": "v1",
            },
        )

        try:
            scenario = await scenario_service.create_scenario(current_user, create_data)
        except Exception as exc:
            logger.error("Failed to create scenario: %s", exc, exc_info=True)
            raise

        # Audit
        await self._audit(
            AuditEventType.SIMULATION_NL_CONFIRMED,
            current_user,
            {
                "job_id": str(request.job_id),
                "scenario_id": str(scenario.id),
                "changes_count": len(request.intent.changes),
            },
        )

        return NLConfirmResponse(
            scenario_id=scenario.id,
            status=scenario.status,
            message=f"Scenario '{scenario.name}' created. You can now run the simulation.",
            requires_execution=True,
        )

    async def explain(
        self,
        request: NLExplainRequest,
        current_user: User,
    ) -> NLExplainResponse:
        """Generate a grounded natural-language explanation of results."""
        # Load execution results
        from sqlalchemy import select as sa_select
        from app.domain.simulation_models import (
            SimulationExecution,
            SimulationResult,
        )

        execution_id = request.execution_id
        if not execution_id:
            # Find latest completed execution
            stmt = (
                sa_select(SimulationExecution)
                .where(SimulationExecution.scenario_id == request.scenario_id)
                .where(SimulationExecution.status == "completed")
                .order_by(SimulationExecution.completed_at.desc())
                .limit(1)
            )
            result = await self._db.execute(stmt)
            execution = result.scalar_one_or_none()
            if not execution:
                return NLExplainResponse(
                    explanation="No completed simulation found for this scenario.",
                    data_sources=[],
                    scenario_id=request.scenario_id,
                )
            execution_id = execution.id

        # Load scenario for context
        from app.domain.simulation_models import SimulationScenario
        stmt = sa_select(SimulationScenario).where(
            SimulationScenario.id == request.scenario_id
        )
        result = await self._db.execute(stmt)
        scenario = result.scalar_one_or_none()

        if not scenario:
            return NLExplainResponse(
                explanation="Scenario not found.",
                data_sources=[],
                scenario_id=request.scenario_id,
            )

        # Load results
        stmt = (
            sa_select(SimulationResult)
            .where(SimulationResult.execution_id == execution_id)
            .order_by(SimulationResult.simulation_rank)
            .limit(20)
        )
        result = await self._db.execute(stmt)
        results = list(result.scalars().all())

        # Load comparison data if available
        from app.domain.simulation_models import SimulationImpact
        stmt = sa_select(SimulationImpact).where(
            SimulationImpact.execution_id == execution_id
        )
        result = await self._db.execute(stmt)
        impacts = list(result.scalars().all())

        # Build grounded context for explanation
        explanation_context = self._build_explanation_context(
            scenario, results, impacts, request.question
        )

        # Use LLM to generate explanation from grounded data
        explanation = await self._generate_grounded_explanation(
            explanation_context, request.question
        )

        return NLExplainResponse(
            explanation=explanation,
            data_sources=["simulation_results", "simulation_impacts", "scenario_config"],
            scenario_id=request.scenario_id,
            execution_id=execution_id,
        )

    # ─── Internal Helpers ───────────────────────────────────────────

    async def _load_job(self, job_id: uuid.UUID, user: User) -> Any:
        """Load and authorize a job."""
        from app.domain.models import Job

        stmt = select(Job).where(Job.id == job_id)
        result = await self._db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Organization isolation
        if (
            hasattr(job, "organization_id")
            and job.organization_id
            and hasattr(user, "organization_id")
            and user.organization_id
            and job.organization_id != user.organization_id
        ):
            raise PermissionError("Access denied: job belongs to another organization")

        return job

    async def _load_baseline_config(self, job: Any) -> dict:
        """Load the baseline simulation config for a job.

        Checks for an existing simulation's baseline, otherwise returns defaults.
        """
        from sqlalchemy import select as sa_select
        from app.domain.simulation_models import SimulationScenario

        stmt = (
            sa_select(SimulationScenario)
            .where(SimulationScenario.job_id == job.id)
            .order_by(SimulationScenario.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        scenario = result.scalar_one_or_none()

        if scenario and scenario.baseline_config:
            return scenario.baseline_config

        # Default configuration
        return {
            "version": 1,
            "scoring_weights": {
                "skills": 0.40,
                "experience": 0.25,
                "education": 0.15,
                "projects": 0.20,
                "certifications": 0.00,
                "location": 0.00,
                "employment_type": 0.00,
                "semantic": 0.00,
            },
            "threshold": DEFAULT_THRESHOLD,
            "shortlist_size": DEFAULT_SHORTLIST_SIZE,
            "requirements": {
                "mandatory_skills": [],
                "preferred_skills": [],
                "experience": None,
                "education": None,
            },
        }

    def _build_job_context(self, job: Any, baseline: dict) -> dict[str, Any]:
        """Build a compact job context for the LLM."""
        weights = baseline.get("scoring_weights", {})
        reqs = baseline.get("requirements", {})
        exp = reqs.get("experience")
        edu = reqs.get("education")

        return {
            "job_id": str(job.id),
            "job_title": getattr(job, "title", "Unknown"),
            "weights": weights,
            "threshold": baseline.get("threshold", DEFAULT_THRESHOLD),
            "shortlist_size": baseline.get("shortlist_size", DEFAULT_SHORTLIST_SIZE),
            "mandatory_skills": reqs.get("mandatory_skills", []),
            "preferred_skills": reqs.get("preferred_skills", []),
            "experience": exp,
            "education": edu,
        }

    def _build_proposal(
        self, intent: SimulationIntent, baseline: dict
    ) -> list[ProposalChange]:
        """Generate human-readable proposal changes from an intent."""
        proposal: list[ProposalChange] = []
        weights = baseline.get("scoring_weights", {})
        threshold = baseline.get("threshold", DEFAULT_THRESHOLD)
        shortlist = baseline.get("shortlist_size", DEFAULT_SHORTLIST_SIZE)
        reqs = baseline.get("requirements", {})
        mandatory = reqs.get("mandatory_skills", [])
        preferred = reqs.get("preferred_skills", [])
        exp = reqs.get("experience")
        edu = reqs.get("education")

        for change in intent.changes:
            if isinstance(change, ScoringWeightChange):
                current = weights.get(change.parameter, 0.0)
                proposal.append(ProposalChange(
                    category="Scoring Weight",
                    label=f"{WEIGHT_LABELS.get(change.parameter, change.parameter)} weight",
                    baseline=f"{current * 100:.0f}%",
                    proposed=f"{change.value * 100:.0f}%",
                    change_type="modified",
                ))

            elif isinstance(change, ThresholdChange):
                proposal.append(ProposalChange(
                    category="Threshold",
                    label="Minimum qualification score",
                    baseline=str(threshold),
                    proposed=str(change.value),
                    change_type="modified",
                ))

            elif isinstance(change, ShortlistChange):
                proposal.append(ProposalChange(
                    category="Shortlist",
                    label="Shortlist size",
                    baseline=str(shortlist),
                    proposed=str(change.value),
                    change_type="modified",
                ))

            elif isinstance(change, RequirementChange):
                op = change.operation
                skill = change.skill
                if op == RequirementOperation.ADD or op == RequirementOperation.PROMOTE:
                    target = change.target or "mandatory"
                    current_list = mandatory if target == "mandatory" else preferred
                    proposal.append(ProposalChange(
                        category="Skill Requirement",
                        label=f"{skill}",
                        baseline="not required",
                        proposed=f"{target}",
                        change_type="added",
                    ))
                elif op == RequirementOperation.REMOVE:
                    in_list = "mandatory" if skill in mandatory else "preferred" if skill in preferred else "not required"
                    proposal.append(ProposalChange(
                        category="Skill Requirement",
                        label=f"{skill}",
                        baseline=in_list,
                        proposed="removed",
                        change_type="removed",
                    ))
                elif op == RequirementOperation.DEMOTE:
                    proposal.append(ProposalChange(
                        category="Skill Requirement",
                        label=f"{skill}",
                        baseline="mandatory",
                        proposed=change.target or "preferred",
                        change_type="modified",
                    ))

            elif isinstance(change, ExperienceChange):
                if change.operation == "REMOVE":
                    proposal.append(ProposalChange(
                        category="Experience",
                        label="Minimum experience",
                        baseline=self._format_experience(exp),
                        proposed="removed",
                        change_type="removed",
                    ))
                elif change.operation == "SET_MIN":
                    proposal.append(ProposalChange(
                        category="Experience",
                        label="Minimum experience",
                        baseline=self._format_experience(exp),
                        proposed=f"{change.value} years",
                        change_type="modified",
                    ))
                elif change.operation == "SET_MAX":
                    proposal.append(ProposalChange(
                        category="Experience",
                        label="Maximum experience",
                        baseline=self._format_experience_max(exp),
                        proposed=f"{change.value} years",
                        change_type="modified",
                    ))

            elif isinstance(change, EducationChange):
                if change.operation == "REMOVE":
                    proposal.append(ProposalChange(
                        category="Education",
                        label="Education requirement",
                        baseline=self._format_education(edu),
                        proposed="removed",
                        change_type="removed",
                    ))
                else:
                    proposal.append(ProposalChange(
                        category="Education",
                        label="Education requirement",
                        baseline=self._format_education(edu),
                        proposed=f"{change.level or ''} {change.requirement or ''}".strip(),
                        change_type="modified",
                    ))

            elif isinstance(change, PresetChange):
                preset = PRESETS.get(change.preset.upper(), {})
                preset_weights = preset.get("scoring_weights", {})
                proposal.append(ProposalChange(
                    category="Preset",
                    label=f"Apply {change.preset.upper()} preset",
                    baseline="current config",
                    proposed=json.dumps(
                        {k: f"{v*100:.0f}%" for k, v in preset_weights.items()},
                        indent=2,
                    ),
                    change_type="preset",
                ))

        return proposal

    def _apply_intent_to_config(
        self, intent: SimulationIntent, baseline: dict
    ) -> dict:
        """Apply intent changes to the baseline configuration."""
        import copy
        config = copy.deepcopy(baseline)

        weights = config.get("scoring_weights", {})
        reqs = config.get("requirements", {})

        for change in intent.changes:
            if isinstance(change, ScoringWeightChange):
                weights[change.parameter] = change.value

            elif isinstance(change, ThresholdChange):
                config["threshold"] = change.value

            elif isinstance(change, ShortlistChange):
                config["shortlist_size"] = change.value

            elif isinstance(change, RequirementChange):
                mandatory = reqs.get("mandatory_skills", [])
                preferred = reqs.get("preferred_skills", [])

                # Normalize skill name
                from app.services.simulation.configuration_validator import normalize_skill
                skill = normalize_skill(change.skill)

                if change.operation in (RequirementOperation.ADD, RequirementOperation.PROMOTE):
                    target = change.target or "mandatory"
                    # Remove from current lists first
                    mandatory = [s for s in mandatory if normalize_skill(s) != skill]
                    preferred = [s for s in preferred if normalize_skill(s) != skill]
                    if target == "mandatory":
                        mandatory.append(change.skill)
                    else:
                        preferred.append(change.skill)

                elif change.operation == RequirementOperation.REMOVE:
                    mandatory = [s for s in mandatory if normalize_skill(s) != skill]
                    preferred = [s for s in preferred if normalize_skill(s) != skill]

                elif change.operation == RequirementOperation.DEMOTE:
                    mandatory = [s for s in mandatory if normalize_skill(s) != skill]
                    preferred = [s for s in preferred if normalize_skill(s) != skill]
                    preferred.append(change.skill)

                reqs["mandatory_skills"] = mandatory
                reqs["preferred_skills"] = preferred

            elif isinstance(change, ExperienceChange):
                if change.operation == "REMOVE":
                    reqs["experience"] = None
                else:
                    exp = reqs.get("experience") or {}
                    if change.operation == "SET_MIN":
                        exp["minimum_years"] = change.value
                    elif change.operation == "SET_MAX":
                        exp["maximum_years"] = change.value
                    reqs["experience"] = exp

            elif isinstance(change, EducationChange):
                if change.operation == "REMOVE":
                    reqs["education"] = None
                else:
                    edu = reqs.get("education") or {}
                    if change.level:
                        edu["level"] = change.level
                    if change.requirement:
                        edu["requirement"] = change.requirement
                    reqs["education"] = edu

            elif isinstance(change, PresetChange):
                preset = PRESETS.get(change.preset.upper(), {})
                if "scoring_weights" in preset:
                    weights.update(preset["scoring_weights"])

        config["scoring_weights"] = weights
        config["requirements"] = reqs
        return config

    def _build_clarification_message(self, intent: SimulationIntent) -> str:
        """Build a user-friendly message for ambiguous/unsupported requests."""
        if intent.clarifications_required:
            questions = "\n".join(
                f"• {c.question}" for c in intent.clarifications_required
            )
            return f"I need some clarification:\n{questions}"

        if intent.unsupported_requests:
            unsupported = "\n".join(f"• {u}" for u in intent.unsupported_requests)
            return (
                "I can't process the following requests:\n"
                f"{unsupported}\n\n"
                "The simulation system supports: scoring weights, thresholds, "
                "shortlist sizes, skill requirements, experience, and education changes."
            )

        return "I couldn't fully interpret your request. Please try rephrasing."

    def _build_proposal_message(
        self, intent: SimulationIntent, proposal: list[ProposalChange]
    ) -> str:
        """Build a confirmation message for a valid proposal."""
        lines = [f"I'll simulate the following {len(proposal)} change(s):"]
        for p in proposal:
            lines.append(f"  • {p.label}: {p.baseline} → {p.proposed}")
        lines.append("")
        lines.append("No live hiring data will be modified.")
        return "\n".join(lines)

    def _format_experience(self, exp: dict | None) -> str:
        if not exp:
            return "None"
        min_y = exp.get("minimum_years")
        max_y = exp.get("maximum_years")
        if min_y is not None and max_y is not None:
            return f"{min_y}-{max_y} years"
        if min_y is not None:
            return f"{min_y}+ years"
        if max_y is not None:
            return f"up to {max_y} years"
        return "None"

    def _format_experience_max(self, exp: dict | None) -> str:
        if not exp:
            return "None"
        max_y = exp.get("maximum_years")
        return f"{max_y} years" if max_y is not None else "None"

    def _format_education(self, edu: dict | None) -> str:
        if not edu:
            return "None"
        level = edu.get("level", "")
        req = edu.get("requirement", "")
        return f"{level} ({req})" if level else req or "None"

    def _build_explanation_context(
        self, scenario, results, impacts, question
    ) -> dict[str, Any]:
        """Build grounded context for LLM explanation generation."""
        # Summarize top movers
        top_movers = []
        for r in results[:10]:
            top_movers.append({
                "candidate": r.candidate_name,
                "baseline_rank": r.baseline_rank,
                "simulation_rank": r.simulation_rank,
                "rank_change": r.rank_change,
                "score_change": r.score_change,
            })

        # Summarize impacts
        impact_summary = {}
        for imp in impacts:
            impact_summary[imp.metric] = {
                "baseline": imp.baseline_value,
                "simulation": imp.simulation_value,
                "change": imp.change_value,
            }

        config = scenario.simulation_config or {}
        baseline = scenario.baseline_config or {}

        return {
            "scenario_name": scenario.name,
            "job_title": getattr(scenario.job, "title", "Unknown") if hasattr(scenario, "job") and scenario.job else "Unknown",
            "config_changes": {
                "weights": config.get("scoring_weights", {}),
                "threshold": config.get("threshold"),
                "shortlist_size": config.get("shortlist_size"),
            },
            "baseline_config": {
                "weights": baseline.get("scoring_weights", {}),
                "threshold": baseline.get("threshold"),
                "shortlist_size": baseline.get("shortlist_size"),
            },
            "total_candidates": len(results),
            "qualified": sum(1 for r in results if r.baseline_status != "disqualified"),
            "simulation_qualified": sum(1 for r in results if r.simulation_status != "disqualified"),
            "shortlisted": sum(1 for r in results if r.baseline_shortlisted),
            "simulation_shortlisted": sum(1 for r in results if r.simulation_shortlisted),
            "top_movers": top_movers,
            "impact_metrics": impact_summary,
            "question": question,
        }

    async def _generate_grounded_explanation(
        self, context: dict[str, Any], question: str
    ) -> str:
        """Use LLM to generate explanation grounded in actual data."""
        from app.ai_core.llm_client import LLMMessage

        system = (
            "You explain hiring simulation results. You MUST only state facts "
            "from the provided data. Never invent scores, rankings, or metrics. "
            "If data is missing, say so. Be concise."
        )

        prompt = (
            f"## Simulation Data\n{json.dumps(context, indent=2, default=str)}\n\n"
            f"## User Question\n{question or 'Summarize the key changes and impact.'}\n\n"
            "Based ONLY on the data above, provide a grounded explanation."
        )

        try:
            response = await llm_client.chat(
                messages=[
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return response.content
        except Exception as exc:
            logger.warning("Explanation generation failed: %s", exc)
            return self._fallback_explanation(context)

    def _fallback_explanation(self, context: dict) -> str:
        """Deterministic fallback when LLM is unavailable."""
        lines = [f"## {context.get('scenario_name', 'Simulation')} Results\n"]

        config = context.get("config_changes", {})
        baseline = context.get("baseline_config", {})

        # Compare thresholds
        old_t = baseline.get("threshold", "?")
        new_t = config.get("threshold", "?")
        if old_t != new_t:
            lines.append(f"• Threshold changed from {old_t} to {new_t}")

        # Compare shortlist
        old_s = baseline.get("shortlist_size", "?")
        new_s = config.get("shortlist_size", "?")
        if old_s != new_s:
            lines.append(f"• Shortlist size changed from {old_s} to {new_s}")

        # Candidate impact
        lines.append(f"• {context.get('total_candidates', 0)} candidates evaluated")
        lines.append(f"• {context.get('simulation_qualified', 0)} qualified (was {context.get('qualified', 0)})")
        lines.append(f"• {context.get('simulation_shortlisted', 0)} shortlisted (was {context.get('shortlisted', 0)})")

        # Top movers
        movers = context.get("top_movers", [])
        if movers:
            lines.append("\nTop movers:")
            for m in movers[:5]:
                direction = "↑" if m["rank_change"] > 0 else "↓" if m["rank_change"] < 0 else "→"
                lines.append(
                    f"  {m['candidate']}: rank {m['baseline_rank']} → {m['simulation_rank']} "
                    f"({direction} {abs(m['rank_change'])})"
                )

        return "\n".join(lines)

    async def _audit(
        self,
        event_type: AuditEventType,
        user: User,
        details: dict,
    ) -> None:
        """Record an audit event."""
        try:
            audit_svc = AuditService(self._db)
            await audit_svc.log(
                event_type=event_type,
                action=event_type.value,
                user_id=user.id,
                resource_type="simulation_nl",
                resource_id=str(details.get("scenario_id", "")),
                details=details,
            )
        except Exception:
            pass
