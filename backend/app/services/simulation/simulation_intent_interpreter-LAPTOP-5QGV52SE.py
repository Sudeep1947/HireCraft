"""Natural-language simulation intent interpreter.

Uses the existing LLM infrastructure (LLMClient) to parse user language
into a structured SimulationIntent.  The LLM is constrained to output
JSON matching the SimulationIntent schema — it never invents numerical
results.

Architecture:

    User message → System prompt + context → LLM → JSON → SimulationIntent
                                                                  ↓
                                                          Backend validation
                                                                  ↓
                                                          Proposal generation
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.ai_core.llm_client import LLMClient, LLMMessage, llm_client
from app.core.logging import get_logger
from app.domain.simulation_intent_schemas import (
    IntentStatus,
    SimulationIntent,
)

logger = get_logger(__name__)

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
You are the Simulation Agent for an AI hiring platform. Your role is to interpret \
natural-language requests about hypothetical hiring simulations and convert them \
into structured JSON intents.

## CRITICAL RULES

1. NEVER invent numerical simulation results (scores, rankings, fairness metrics).
2. NEVER execute simulations — you only interpret intent.
3. NEVER modify live hiring configuration.
4. ALWAYS output valid JSON matching the SimulationIntent schema.
5. For ambiguous requests, ask clarifying questions — do NOT guess.
6. For unsupported operations, list them in unsupported_requests.

## SUPPORTED OPERATIONS

### Scoring Weights
Parameters: skills, experience, education, projects, certifications, location, employment_type, semantic
Values: 0.0 to 1.0 (representing 0% to 100%)
Example: "Increase experience to 40%" → {"type": "SCORING_WEIGHT", "parameter": "experience", "value": 0.4}

### Threshold
Range: 0-100 (integer)
Example: "Raise threshold to 80" → {"type": "THRESHOLD", "value": 80}

### Shortlist Size
Range: 1-500
Example: "Shortlist 20 candidates" → {"type": "SHORTLIST", "value": 20}

### Skill Requirements
Operations: ADD, REMOVE, PROMOTE, DEMOTE
Example: "Make PostgreSQL mandatory" → {"type": "REQUIREMENT", "operation": "PROMOTE", "skill": "PostgreSQL", "target": "mandatory"}

### Experience
Operations: SET_MIN, SET_MAX, REMOVE
Example: "Require at least 5 years" → {"type": "EXPERIENCE", "operation": "SET_MIN", "value": 5}

### Education
Example: "Make master's preferred" → {"type": "EDUCATION", "operation": "SET_REQUIREMENT", "level": "master", "requirement": "preferred"}

### Comparison
For multi-scenario comparison requests, use comparison_scenario_ids.

## COMPOUND REQUESTS
Handle multiple changes in a single request. Each change is a separate entry in the changes array.

## AMBIGUOUS REQUESTS
When the user says vague things like:
- "Make experience more important" → Ask for the specific numeric value
- "Focus more on skills" → Ask for the percentage
- "More selective" → Clarify which parameter(s)
- Relative changes like "increase by 10pp" are OK if the baseline is clear

## UNSUPPORTED REQUESTS
Detect and list operations the system does NOT support:
- Predicting candidate acceptance
- Automatically rejecting candidates
- Modifying candidate resumes
- Making hiring decisions
- Interview scheduling

## OUTPUT FORMAT
Return ONLY a JSON object matching this structure:
{
  "intent": "SIMULATE_HIRING_STRATEGY",
  "job_id": null,
  "changes": [...],
  "clarifications_required": [...],
  "unsupported_requests": [...],
  "assumptions": [...],
  "natural_language_request": "<original message>",
  "comparison_scenario_ids": [],
  "confidence": 0.0-1.0,
  "status": "INTERPRETED"
}

Do NOT wrap in markdown code fences. Return raw JSON only.
"""


class SimulationIntentInterpreter:
    """Interprets natural-language requests into structured SimulationIntents.

    Uses the LLM for language understanding but enforces strict schema
    validation on the output.  Falls back to deterministic parsing for
    simple, unambiguous requests.
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or llm_client

    async def interpret(
        self,
        message: str,
        job_id: uuid.UUID,
        job_context: dict[str, Any] | None = None,
    ) -> SimulationIntent:
        """Parse a natural-language message into a SimulationIntent.

        1. Try deterministic parsing for simple cases (fast path).
        2. Fall back to LLM interpretation for complex requests.
        3. Validate and normalize the output.
        """
        # Fast path: simple deterministic parsing
        deterministic = self._try_deterministic_parse(message, job_id)
        if deterministic is not None:
            return deterministic

        # LLM path: complex interpretation
        return await self._llm_interpret(message, job_id, job_context)

    def _try_deterministic_parse(
        self,
        message: str,
        job_id: uuid.UUID,
    ) -> SimulationIntent | None:
        """Attempt deterministic parsing for common, unambiguous requests.

        Returns None if the request is too complex for rule-based parsing.
        This covers the majority of real-world usage without needing an LLM.
        """
        import re
        from app.domain.simulation_intent_schemas import (
            ScoringWeightChange, ThresholdChange, ShortlistChange,
            RequirementChange, RequirementOperation,
            ExperienceChange, EducationChange,
        )

        normalized = message.strip().lower()

        # ── Scoring weight changes ─────────────────────────────────
        # "experience to 40%", "increase skills to 50%", "make projects 30%"
        # "experience becomes 40%", "experience at 40%"
        weight_aliases = {
            "skills": "skills", "skill": "skills",
            "experience": "experience", "exp": "experience",
            "education": "education", "edu": "education",
            "projects": "projects", "project": "projects",
            "certifications": "certifications", "certification": "certifications", "certs": "certifications",
            "location": "location", "loc": "location",
            "employment type": "employment_type", "employment": "employment_type",
            "semantic": "semantic", "semantic match": "semantic",
        }
        # For each known weight dimension, look for "<dim> (to|becomes|at|=) <N>%"
        for alias, dim in weight_aliases.items():
            pattern = rf"\b{re.escape(alias)}\b\s+(?:to|becomes?|at|=)\s+(\d+)\s*%"
            m = re.search(pattern, normalized)
            if m:
                value = int(m.group(1)) / 100.0
                if 0.0 <= value <= 1.0:
                    changes = [ScoringWeightChange(parameter=dim, value=value)]
                    return SimulationIntent(
                        intent="SIMULATE_HIRING_STRATEGY",
                        job_id=job_id,
                        changes=changes,
                        natural_language_request=message,
                        confidence=0.95,
                    )

        # "make experience more important" — needs clarification
        if re.search(r"(make|set|increase|reduce|lower)\s+(\w[\w\s]*?)\s+(more|less)\s+(important|weighted)", normalized):
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[],
                clarifications_required=[{
                    "question": "What percentage should this weight be set to?",
                    "context": "Please specify a numeric value (e.g., 40%).",
                    "options": [],
                }],
                natural_language_request=message,
                confidence=0.5,
                status=IntentStatus.AMBIGUOUS,
            )

        # ── Threshold changes ──────────────────────────────────────
        m = re.search(
            r"(?:threshold|min(?:imum)?\s+score)\s+(?:to|from|=)?\s*(\d+)",
            normalized,
        )
        if m:
            value = int(m.group(1))
            if 0 <= value <= 100:
                return SimulationIntent(
                    intent="SIMULATE_HIRING_STRATEGY",
                    job_id=job_id,
                    changes=[ThresholdChange(value=value)],
                    natural_language_request=message,
                    confidence=0.95,
                )

        # "raise threshold by N" (relative)
        m = re.search(r"(?:raise|increase|lower|decrease|drop)\s+(?:the\s+)?threshold\s+by\s+(\d+)", normalized)
        if m:
            # We'll need baseline context — mark as needing it
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[],
                clarifications_required=[{
                    "question": f"Relative threshold changes need the current value. Please specify the target value directly (e.g., 'threshold to 80').",
                    "context": "",
                    "options": [],
                }],
                natural_language_request=message,
                confidence=0.5,
                status=IntentStatus.AMBIGUOUS,
            )

        # ── Shortlist changes ──────────────────────────────────────
        m = re.search(r"shortlist\s+(?:top\s+)?(\d+)", normalized)
        if m:
            value = int(m.group(1))
            if 1 <= value <= 500:
                return SimulationIntent(
                    intent="SIMULATE_HIRING_STRATEGY",
                    job_id=job_id,
                    changes=[ShortlistChange(value=value)],
                    natural_language_request=message,
                    confidence=0.95,
                )

        # "interview top N"
        m = re.search(r"interview\s+(?:the\s+)?(?:top\s+)?(\d+)", normalized)
        if m:
            value = int(m.group(1))
            if 1 <= value <= 500:
                return SimulationIntent(
                    intent="SIMULATE_HIRING_STRATEGY",
                    job_id=job_id,
                    changes=[ShortlistChange(value=value)],
                    natural_language_request=message,
                    confidence=0.90,
                )

        # ── Requirement changes ────────────────────────────────────
        # "make <skill> mandatory"
        m = re.search(r"make\s+([\w\s.#+]+?)\s+mandatory", normalized)
        if m:
            skill = m.group(1).strip().title()
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[RequirementChange(
                    operation=RequirementOperation.PROMOTE,
                    skill=skill,
                    target="mandatory",
                )],
                natural_language_request=message,
                confidence=0.90,
            )

        # "make <skill> preferred"
        m = re.search(r"make\s+([\w\s.#+]+?)\s+preferred", normalized)
        if m:
            skill = m.group(1).strip().title()
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[RequirementChange(
                    operation=RequirementOperation.PROMOTE,
                    skill=skill,
                    target="preferred",
                )],
                natural_language_request=message,
                confidence=0.90,
            )

        # "remove <skill> from requirements"
        m = re.search(r"remove\s+([\w\s.#+]+?)\s+(?:from|the)\s+requirements?", normalized)
        if m:
            skill = m.group(1).strip().title()
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[RequirementChange(
                    operation=RequirementOperation.REMOVE,
                    skill=skill,
                )],
                natural_language_request=message,
                confidence=0.90,
            )

        # "add <skill> as mandatory/preferred"
        m = re.search(r"add\s+([\w\s.#+]+?)\s+as\s+(mandatory|preferred)", normalized)
        if m:
            skill = m.group(1).strip().title()
            target = m.group(2)
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[RequirementChange(
                    operation=RequirementOperation.ADD,
                    skill=skill,
                    target=target,
                )],
                natural_language_request=message,
                confidence=0.90,
            )

        # ── Experience changes ─────────────────────────────────────
        m = re.search(r"(?:require|minimum)\s+(?:at\s+least\s+)?(\d+)\s+years?\s+(?:of\s+)?experience", normalized)
        if m:
            value = int(m.group(1))
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[ExperienceChange(operation="SET_MIN", value=value)],
                natural_language_request=message,
                confidence=0.90,
            )

        m = re.search(r"(?:reduce|lower|change)\s+(?:the\s+)?experience\s+(?:requirement\s+)?(?:to|by)\s+(\d+)", normalized)
        if m:
            value = int(m.group(1))
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[ExperienceChange(operation="SET_MIN", value=value)],
                natural_language_request=message,
                confidence=0.85,
            )

        m = re.search(r"remove\s+(?:the\s+)?experience\s+requirement", normalized)
        if m:
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[ExperienceChange(operation="REMOVE")],
                natural_language_request=message,
                confidence=0.90,
            )

        # ── Education changes ──────────────────────────────────────
        m = re.search(r"make\s+(a\s+)?(master'?s?|bachelor'?s?|phd|doctorate|high\s*school|associate)\s+(?:degree\s+)?(?:mandatory|required|preferred|optional)", normalized)
        if m:
            level_map = {
                "master": "master", "masters": "master", "master's": "master",
                "bachelor": "bachelor", "bachelors": "bachelor", "bachelor's": "bachelor",
                "phd": "doctorate", "doctorate": "doctorate",
                "high school": "high_school", "high_school": "high_school",
                "associate": "associate",
            }
            level_raw = m.group(2).replace("'", "").strip()
            level = level_map.get(level_raw, level_raw)
            if "mandatory" in normalized or "required" in normalized:
                req = "required"
            elif "preferred" in normalized:
                req = "preferred"
            else:
                req = "optional"
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[EducationChange(operation="SET_REQUIREMENT", level=level, requirement=req)],
                natural_language_request=message,
                confidence=0.85,
            )

        # ── Comparison requests ────────────────────────────────────
        if "compare" in normalized:
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                changes=[],
                clarifications_required=[{
                    "question": "To compare scenarios, I need at least two completed simulation scenarios. Please select them from the Compare Scenarios page, or describe two configurations to compare.",
                    "context": "Multi-scenario comparison is available via the Compare Scenarios page.",
                    "options": [],
                }],
                natural_language_request=message,
                confidence=0.7,
                status=IntentStatus.AMBIGUOUS,
            )

        # ── Fallback: unsupported / unrecognized ───────────────────
        return None

    async def _llm_interpret(
        self,
        message: str,
        job_id: uuid.UUID,
        job_context: dict[str, Any] | None = None,
    ) -> SimulationIntent:
        """Use the LLM to interpret a complex natural-language request."""
        context_block = ""
        if job_context:
            context_block = (
                "\n\n## Current Job Configuration\n"
                f"Job ID: {job_context.get('job_id')}\n"
                f"Job Title: {job_context.get('job_title', 'Unknown')}\n"
                f"Current Weights: {json.dumps(job_context.get('weights', {}), indent=2)}\n"
                f"Current Threshold: {job_context.get('threshold', 70)}\n"
                f"Current Shortlist: {job_context.get('shortlist_size', 10)}\n"
                f"Current Mandatory Skills: {job_context.get('mandatory_skills', [])}\n"
                f"Current Preferred Skills: {job_context.get('preferred_skills', [])}\n"
                f"Current Experience: {job_context.get('experience', 'None')}\n"
                f"Current Education: {job_context.get('education', 'None')}\n"
            )

        user_prompt = (
            f"{context_block}\n\n"
            f"## User Request\n{message}\n\n"
            "Convert the above request into a SimulationIntent JSON. "
            "If the request is ambiguous, set clarifications_required. "
            "If unsupported, set unsupported_requests. "
            "Output ONLY valid JSON."
        )

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]

        try:
            response = await self._client.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error("LLM interpretation failed: %s", exc)
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                natural_language_request=message,
                status=IntentStatus.UNSUPPORTED,
                unsupported_requests=[f"LLM provider error: {exc}"],
                confidence=0.0,
            )

        return self._parse_llm_response(response.content, job_id, message)

    def _parse_llm_response(
        self,
        content: str,
        job_id: uuid.UUID,
        original_message: str,
    ) -> SimulationIntent:
        """Parse and validate the LLM's JSON response into SimulationIntent."""
        # Strip markdown code fences if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON: %s", exc)
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                natural_language_request=original_message,
                status=IntentStatus.UNSUPPORTED,
                unsupported_requests=[f"Could not parse agent response as JSON"],
                confidence=0.0,
            )

        # Inject job_id if missing
        if not data.get("job_id"):
            data["job_id"] = str(job_id)

        # Validate with Pydantic
        try:
            intent = SimulationIntent(**data)
        except Exception as exc:
            logger.warning("Intent validation failed: %s", exc)
            return SimulationIntent(
                intent="SIMULATE_HIRING_STRATEGY",
                job_id=job_id,
                natural_language_request=original_message,
                status=IntentStatus.UNSUPPORTED,
                unsupported_requests=[f"Invalid intent structure: {exc}"],
                confidence=0.0,
            )

        # Enforce safety constraints
        intent = self._enforce_safety(intent)
        return intent

    def _enforce_safety(self, intent: SimulationIntent) -> SimulationIntent:
        """Enforce safety constraints on the interpreted intent."""
        # Cap confidence
        if intent.confidence > 1.0:
            intent.confidence = 1.0

        # If there are clarifications or unsupported ops, mark status
        if intent.clarifications_required:
            intent.status = IntentStatus.AMBIGUOUS
        elif intent.unsupported_requests:
            intent.status = IntentStatus.UNSUPPORTED

        return intent
