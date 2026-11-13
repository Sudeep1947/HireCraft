"""SimulationShortlistService — optional, human-confirmed shortlist action.

This is an integration layer between a completed simulation's hypothetical
ranking and the EXISTING live application-status workflow. It deliberately does
NOT create a second shortlist engine, ranking engine, or audit framework.

Contract:

* The simulation stays immutable. ``scenario.status`` remains ``completed``;
  only the live ``job_applications`` are updated, and only through the same
  path the recruiter-facing ``PATCH .../applications/{id}/status`` endpoint
  uses (``RecruiterJobService.update_application_status``).
* Nothing mutates live data unless the recruiter explicitly calls ``apply``
  with an explicit confirmation. Viewing results, changing parameters, and
  opening/cancelling shortlist dialogs never reach this service.
* The operation is idempotent: applications already ``shortlisted`` are
  skipped, so duplicate requests never double-apply.
* Every submitted candidate id is validated server-side: simulation access,
  job access, execution completion, candidate/job application relationship,
  membership in the simulated pool, and current live state.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.enums import (
    ApplicationStatus,
    AuditEventType,
    SimulationStatus,
)
from app.domain.models import Job, User
from app.domain.simulation_models import SimulationExecution, SimulationScenario
from app.domain.simulation_schemas import (
    SimulationShortlistApplyRequest,
    SimulationShortlistApplyResponse,
    SimulationShortlistCandidateResult,
)
from app.repositories.jobs.job import JobApplicationRepository
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)
from app.services.audit_service import AuditService
from app.services.jobs.recruiter_job_service import RecruiterJobService
from app.services.simulation.simulation_service import SimulationScenarioService

logger = logging.getLogger(__name__)
AUDIT_LOGGER = logging.getLogger("audit")

SHORTLIST_STATUS = ApplicationStatus.SHORTLISTED.value

# Live states from which moving a candidate onto the shortlist is a safe,
# forward transition. Anything "ahead of" shortlist or terminal is treated as
# a conflict so we never blindly overwrite newer workflow decisions.
SHORTLISTABLE_FROM = {
    ApplicationStatus.APPLIED.value,
    ApplicationStatus.UNDER_REVIEW.value,
}

NOT_SHORTLISTABLE_FROM = {
    ApplicationStatus.INTERVIEW_SCHEDULED.value,
    ApplicationStatus.REJECTED.value,
    ApplicationStatus.OFFERED.value,
    ApplicationStatus.HIRED.value,
    ApplicationStatus.WITHDRAWN.value,
}


class SimulationShortlistService:
    def __init__(
        self,
        session: AsyncSession,
        scenario_service: SimulationScenarioService | None = None,
        exec_repo: SimulationExecutionRepository | None = None,
        result_repo: SimulationResultRepository | None = None,
        app_repo: JobApplicationRepository | None = None,
        recruiter_job_service: RecruiterJobService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._session = session
        self._scenario_service = scenario_service or SimulationScenarioService(session)
        self._exec_repo = exec_repo or SimulationExecutionRepository(session)
        self._result_repo = result_repo or SimulationResultRepository(session)
        self._app_repo = app_repo or JobApplicationRepository(session)
        self._recruiter_job_service = recruiter_job_service or RecruiterJobService(session)
        self._audit_service = audit_service or AuditService(session)

    async def apply_shortlist(
        self,
        user: User,
        simulation_id: uuid.UUID,
        data: SimulationShortlistApplyRequest,
    ) -> SimulationShortlistApplyResponse:
        """Apply the recruiter's explicitly confirmed shortlist selection.

        Raises 403/404/409/422 instead of silently skipping any candidate, so a
        single failed candidate rolls the whole request back (the request
        session commits only after the endpoint returns).
        """
        scenario = await self._load_scenario(simulation_id)
        await self._scenario_service._require_view(user, scenario)

        execution = await self._resolve_completed_execution(scenario, data.execution_id)

        job = await self._session.get(Job, scenario.job_id)
        if not job:
            raise NotFoundError("Job not found")

        if job.recruiter_id != user.id:
            raise ForbiddenError(
                "You do not have permission to shortlist candidates for this job",
            )

        # Never trust the frontend: the candidate must belong to this job's
        # application pool AND be part of the executed hypothetical ranking.
        results = await self._result_repo.list_by_execution(execution.id)
        simulated_ids = {r.candidate_id for r in results}
        name_by_id = {r.candidate_id: r.candidate_name for r in results}

        candidate_ids = list(dict.fromkeys(data.candidate_ids))
        unknown = [str(cid) for cid in candidate_ids if cid not in simulated_ids]
        if unknown:
            raise ValidationError(
                "One or more candidates were not part of this simulation's job pool",
                extra={"candidate_ids": unknown},
            )

        # Pass 1 — validate current live state for every candidate before any
        # mutation, so conflicts fail atomically (nothing is half-applied).
        to_update: list[tuple] = []
        skipped: list[SimulationShortlistCandidateResult] = []
        conflict_ids: list[dict] = []
        for candidate_id in candidate_ids:
            app = await self._app_repo.get_by_job_and_candidate(job.id, candidate_id)
            if not app:
                raise ValidationError(
                    f"Candidate {candidate_id} has no application for this job",
                )
            if app.status in NOT_SHORTLISTABLE_FROM:
                conflict_ids.append(
                    {"candidate_id": str(candidate_id), "status": app.status},
                )
                continue
            if app.status == SHORTLIST_STATUS:
                skipped.append(
                    SimulationShortlistCandidateResult(
                        candidate_id=candidate_id,
                        candidate_name=name_by_id.get(candidate_id, ""),
                        application_id=app.id,
                        previous_status=SHORTLIST_STATUS,
                        new_status=SHORTLIST_STATUS,
                        updated=False,
                    ),
                )
                continue
            to_update.append((candidate_id, app, app.status))

        if conflict_ids:
            raise ConflictError(
                "Live applications changed since this simulation ran; "
                "review the current state before shortlisting. Affected "
                "candidates can no longer be moved onto the shortlist.",
                extra={
                    "conflicts": conflict_ids,
                    "simulation_id": str(scenario.id),
                    "job_id": str(job.id),
                },
            )

        # Pass 2 — reuse the existing shortlist workflow (status transition +
        # candidate notification), exactly as the recruiter status endpoint does.
        updated: list[SimulationShortlistCandidateResult] = []
        for candidate_id, app, previous_status in to_update:
            await self._recruiter_job_service.update_application_status(
                app.id, user, SHORTLIST_STATUS,
            )
            updated.append(
                SimulationShortlistCandidateResult(
                    candidate_id=candidate_id,
                    candidate_name=name_by_id.get(candidate_id, ""),
                    application_id=app.id,
                    previous_status=previous_status,
                    new_status=SHORTLIST_STATUS,
                    updated=True,
                ),
            )

        await self._audit_service.log(
            event_type=AuditEventType.SIMULATION_SHORTLIST_APPLIED,
            action="simulation_shortlist_applied",
            user_id=user.id,
            organization_id=scenario.organization_id,
            resource_type="simulation_execution",
            resource_id=str(execution.id),
            details={
                "simulation_id": str(scenario.id),
                "job_id": str(job.id),
                "execution_id": str(execution.id),
                "candidate_ids": [str(cid) for cid in candidate_ids],
                "updated_applications": [
                    {
                        "application_id": str(u.application_id),
                        "candidate_id": str(u.candidate_id),
                        "previous_status": u.previous_status,
                        "new_status": u.new_status,
                    }
                    for u in updated
                ],
                "updated_count": len(updated),
                "skipped_count": len(skipped),
            },
        )
        AUDIT_LOGGER.info(
            "SIMULATION_SHORTLIST_APPLIED | user=%s simulation=%s job=%s "
            "updated=%d skipped=%d",
            user.id, scenario.id, job.id, len(updated), len(skipped),
        )
        logger.info(
            "Simulation shortlist applied: user=%s simulation=%s updated=%d skipped=%d",
            user.id, scenario.id, len(updated), len(skipped),
        )

        return SimulationShortlistApplyResponse(
            simulation_id=scenario.id,
            execution_id=execution.id,
            job_id=job.id,
            scenario_status=scenario.status,
            shortlist_status="applied",
            applied=True,
            updated=updated,
            skipped=skipped,
        )

    # ─── internals ────────────────────────────────────────────────────

    async def _load_scenario(self, simulation_id: uuid.UUID) -> SimulationScenario:
        return await self._scenario_service._load_or_404(simulation_id)

    async def _resolve_completed_execution(
        self,
        scenario: SimulationScenario,
        execution_id: uuid.UUID | None,
    ) -> SimulationExecution:
        if execution_id is not None:
            execution = await self._exec_repo.get_for_scenario(scenario.id, execution_id)
            if not execution:
                raise NotFoundError("Simulation execution not found")
        else:
            execution = await self._exec_repo.latest_completed(scenario.id)
            if not execution:
                raise ConflictError(
                    "No completed execution is available to shortlist from. "
                    "Run the simulation first.",
                )
        if execution.status != SimulationStatus.COMPLETED.value:
            raise ConflictError(
                "Only a completed execution can be applied to the live "
                f"shortlist (status: {execution.status}).",
            )
        return execution