"""ExperimentService — CRUD, execution orchestration, and results for Phase 14.

READ-ONLY with respect to live hiring data. All analysis operates on
simulation snapshots and persisted results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    ExperimentStatus,
    ExperimentType,
)
from app.domain.simulation_experiment_schemas import (
    ExperimentCreate,
    ExperimentListItem,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentResultItem,
    ExperimentResultsResponse,
    ExperimentStatusResponse,
    ExperimentUpdate,
    FairnessSensitivityPoint,
    FairnessSensitivityResponse,
    RobustnessAnalysisResponse,
    SensitivityAnalysisResponse,
    StabilityAnalysisResponse,
    MAX_CONFIGURATIONS_PER_EXPERIMENT,
)
from app.domain.simulation_models import (
    SimulationExperiment,
    SimulationExperimentResult,
)
from app.repositories.simulation import SimulationRepository
from app.repositories.simulation_experiment import (
    SimulationExperimentRepository,
    SimulationExperimentResultRepository,
)
from app.repositories.simulation_execution import (
    SimulationExecutionRepository,
    SimulationResultRepository,
)
from app.services.audit_service import AuditService
from app.services.simulation.configuration_generator import ConfigurationGenerator
from app.services.simulation.perturbation_engine import PerturbationEngine
from app.services.simulation.sensitivity_analyzer import SensitivityAnalyzer
from app.services.simulation.robustness_analyzer import RobustnessAnalyzer
from app.services.simulation.stability_analyzer import StabilityAnalyzer

logger = get_logger(__name__)


class ExperimentService:
    """Orchestrates research experiments. READ-ONLY with respect to live data."""

    def __init__(
        self,
        session: AsyncSession,
        experiment_repo: SimulationExperimentRepository | None = None,
        result_repo: SimulationExperimentResultRepository | None = None,
        scenario_repo: SimulationRepository | None = None,
        execution_repo: SimulationExecutionRepository | None = None,
        sim_result_repo: SimulationResultRepository | None = None,
    ) -> None:
        self._session = session
        self._experiment_repo = experiment_repo or SimulationExperimentRepository(session)
        self._result_repo = result_repo or SimulationExperimentResultRepository(session)
        self._scenario_repo = scenario_repo or SimulationRepository(session)
        self._exec_repo = execution_repo or SimulationExecutionRepository(session)
        self._sim_result_repo = sim_result_repo or SimulationResultRepository(session)
        self._perturbation_engine = PerturbationEngine()
        self._config_generator = ConfigurationGenerator()
        self._sensitivity_analyzer = SensitivityAnalyzer()
        self._robustness_analyzer = RobustnessAnalyzer()
        self._stability_analyzer = StabilityAnalyzer()

    # ─── CRUD ───────────────────────────────────────────────────────

    async def create_experiment(
        self,
        user: Any,
        request: ExperimentCreate,
    ) -> ExperimentResponse:
        """Create a new research experiment."""
        scenario = await self._scenario_repo.get_with_details(request.base_scenario_id)
        if not scenario:
            raise NotFoundError("Base scenario not found.")

        # Validate same org
        if scenario.organization_id and user.organization_id:
            if str(scenario.organization_id) != str(user.organization_id):
                raise ValidationError("Scenario belongs to a different organization.")

        # Validate parameter ranges
        if len(request.parameter_ranges) > 5:
            raise ValidationError("Maximum 5 parameter dimensions allowed.")

        if request.max_configurations > MAX_CONFIGURATIONS_PER_EXPERIMENT:
            raise ValidationError(
                f"Max configurations cannot exceed {MAX_CONFIGURATIONS_PER_EXPERIMENT}."
            )

        # Estimate configuration count
        param_ranges_dict = {}
        for pr in request.parameter_ranges:
            values = self._perturbation_engine.generate_sweep_values(pr)
            param_ranges_dict[pr.dimension.value] = {
                "values": values,
                "count": len(values),
            }

        estimated = 1
        for v in param_ranges_dict.values():
            estimated *= v["count"]

        if estimated > request.max_configurations:
            raise ValidationError(
                f"The requested parameter space would generate {estimated} configurations, "
                f"exceeding the limit of {request.max_configurations}. "
                "Reduce the range or number of dimensions."
            )

        # Check concurrent experiments limit
        active_count = await self._experiment_repo.count_active_by_org(
            scenario.organization_id,
        )
        if active_count >= 3:
            raise ValidationError(
                "Maximum 3 concurrent experiments per organization. "
                "Wait for a running experiment to complete."
            )

        now = datetime.now(timezone.utc)
        experiment = SimulationExperiment(
            id=uuid.uuid4(),
            organization_id=scenario.organization_id,
            sandbox_id=request.sandbox_id,
            base_scenario_id=request.base_scenario_id,
            job_id=scenario.job_id,
            created_by=user.id,
            name=request.name,
            description=request.description,
            research_question=request.research_question,
            hypothesis=request.hypothesis,
            experiment_type=request.experiment_type.value,
            status=ExperimentStatus.DRAFT.value,
            parameters={
                "base_scenario_name": scenario.name,
                "estimated_configurations": estimated,
            },
            parameter_ranges=param_ranges_dict,
            execution_config=request.execution_config or {},
            total_configurations=0,
            completed_configurations=0,
            failed_configurations=0,
            random_seed=request.random_seed,
            experiment_version="1.0",
            created_at=now,
            updated_at=now,
        )

        self._experiment_repo.add(experiment)
        await self._session.flush()

        await self._audit(user, AuditEventType.EXPERIMENT_CREATED, experiment.id)

        return self._to_response(experiment)

    async def get_experiment(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> ExperimentResponse:
        """Get experiment details."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)
        return self._to_response(exp)

    async def list_experiments(
        self,
        user: Any,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> ExperimentListResponse:
        """List experiments for the current user."""
        org_id = getattr(user, "organization_id", None)
        items, total = await self._experiment_repo.list_by_org(
            org_id, page=page, page_size=page_size,
        )
        return ExperimentListResponse(
            items=[self._to_list_item(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_experiment(
        self,
        experiment_id: uuid.UUID,
        user: Any,
        request: ExperimentUpdate,
    ) -> ExperimentResponse:
        """Update an experiment (only DRAFT status)."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        if exp.status != ExperimentStatus.DRAFT.value:
            raise ValidationError("Can only update experiments in DRAFT status.")

        if request.name is not None:
            exp.name = request.name
        if request.description is not None:
            exp.description = request.description
        if request.research_question is not None:
            exp.research_question = request.research_question
        if request.hypothesis is not None:
            exp.hypothesis = request.hypothesis
        if request.parameter_ranges is not None:
            param_ranges_dict = {}
            for pr in request.parameter_ranges:
                values = self._perturbation_engine.generate_sweep_values(pr)
                param_ranges_dict[pr.dimension.value] = {
                    "values": values,
                    "count": len(values),
                }
            exp.parameter_ranges = param_ranges_dict
        if request.max_configurations is not None:
            pass  # stored in execution_config

        exp.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._audit(user, AuditEventType.EXPERIMENT_MODIFIED, experiment_id)

        return self._to_response(exp)

    async def delete_experiment(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> None:
        """Delete an experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        if exp.status in (ExperimentStatus.RUNNING.value, ExperimentStatus.QUEUED.value):
            raise ValidationError("Cannot delete a running or queued experiment.")

        await self._experiment_repo.delete(experiment_id)
        await self._session.flush()

    async def execute_experiment(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> ExperimentStatusResponse:
        """Execute an experiment — generates configurations and queues execution."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        if exp.status not in (ExperimentStatus.DRAFT.value, ExperimentStatus.FAILED.value):
            raise ValidationError(
                f"Experiment is in {exp.status} status. "
                "Only DRAFT or FAILED experiments can be executed."
            )

        # Load base scenario config
        scenario = await self._scenario_repo.get_with_details(exp.base_scenario_id)
        if not scenario:
            raise NotFoundError("Base scenario not found.")

        base_config = scenario.simulation_config or scenario.baseline_config or {}

        # Generate configurations
        parameter_ranges = self._parameter_ranges_from_dict(exp.parameter_ranges)
        try:
            configs = self._config_generator.generate_configurations(
                base_config,
                parameter_ranges,
                ExperimentType(exp.experiment_type),
                max_configurations=exp.total_configurations or 20,
            )
        except ValueError as e:
            raise ValidationError(str(e))

        if not configs:
            raise ValidationError(
                "No valid configurations were generated. "
                "Check parameter ranges and base scenario configuration."
            )

        # Store generated configs and update status
        exp.generated_configs = {
            "configurations": configs,
            "hashes": [self._perturbation_engine.configuration_hash(c) for c in configs],
        }
        exp.total_configurations = len(configs)
        exp.completed_configurations = 0
        exp.failed_configurations = 0
        exp.status = ExperimentStatus.READY.value
        exp.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

        await self._audit(user, AuditEventType.EXPERIMENT_EXECUTED, experiment_id)

        return ExperimentStatusResponse(
            experiment_id=str(experiment_id),
            status=exp.status,
            total_configurations=exp.total_configurations,
            completed_configurations=exp.completed_configurations,
            failed_configurations=exp.failed_configurations,
        )

    async def get_status(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> ExperimentStatusResponse:
        """Get experiment execution status."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        return ExperimentStatusResponse(
            experiment_id=str(experiment_id),
            status=exp.status,
            total_configurations=exp.total_configurations,
            completed_configurations=exp.completed_configurations,
            failed_configurations=exp.failed_configurations,
            error_message=exp.error_message,
        )

    async def cancel_experiment(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> ExperimentStatusResponse:
        """Cancel a running or queued experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        if exp.status not in (ExperimentStatus.RUNNING.value, ExperimentStatus.QUEUED.value, ExperimentStatus.READY.value):
            raise ValidationError("Experiment is not in a cancellable state.")

        exp.status = ExperimentStatus.CANCELLED.value
        exp.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

        await self._audit(user, AuditEventType.EXPERIMENT_CANCELLED, experiment_id)

        return self._to_status_response(exp)

    # ─── Results & Analysis ─────────────────────────────────────────

    async def get_results(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> ExperimentResultsResponse:
        """Get experiment results."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        results = await self._result_repo.list_by_experiment(experiment_id)
        return ExperimentResultsResponse(
            items=[
                ExperimentResultItem(
                    id=str(r.id),
                    parameter_values=r.parameter_values,
                    execution_status=r.execution_status,
                    metrics=r.metrics,
                    error_message=r.error_message,
                    created_at=r.created_at,
                )
                for r in results
            ],
            total=len(results),
        )

    async def get_sensitivity(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> SensitivityAnalysisResponse:
        """Get sensitivity analysis for an experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        results = await self._result_repo.list_by_experiment(experiment_id)
        result_dicts = [
            {
                "parameter_values": r.parameter_values,
                "metrics": r.metrics,
                "execution_status": r.execution_status,
                "configuration_hash": r.configuration_hash,
            }
            for r in results
        ]

        return self._sensitivity_analyzer.analyze(
            str(experiment_id),
            result_dicts,
            exp.parameter_ranges,
        )

    async def get_robustness(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> RobustnessAnalysisResponse:
        """Get robustness analysis for an experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        results = await self._result_repo.list_by_experiment(experiment_id)
        if not results:
            return RobustnessAnalysisResponse(
                experiment_id=str(experiment_id),
                perturbation_results=[],
                profiles=[],
                summary={"available": False},
            )

        # First result is base (no perturbation), rest are perturbed
        base = {
            "parameter_values": results[0].parameter_values,
            "metrics": results[0].metrics,
        }
        perturbed = [
            {
                "parameter_values": r.parameter_values,
                "metrics": r.metrics,
            }
            for r in results[1:]
        ]

        return self._robustness_analyzer.analyze(
            str(experiment_id), base, perturbed,
        )

    async def get_stability(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> StabilityAnalysisResponse:
        """Get stability analysis for an experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        results = await self._result_repo.list_by_experiment(experiment_id)
        result_dicts = [
            {
                "parameter_values": r.parameter_values,
                "metrics": r.metrics,
                "candidate_metrics": r.candidate_metrics,
            }
            for r in results
        ]

        return self._stability_analyzer.analyze(
            str(experiment_id), result_dicts,
        )

    async def get_fairness_sensitivity(
        self,
        experiment_id: uuid.UUID,
        user: Any,
    ) -> FairnessSensitivityResponse:
        """Get fairness sensitivity for an experiment."""
        exp = await self._experiment_repo.get_with_details(experiment_id)
        if not exp:
            raise NotFoundError("Experiment not found.")
        self._check_access(exp, user)

        results = await self._result_repo.list_by_experiment(experiment_id)
        points: list[FairnessSensitivityPoint] = []

        for r in results:
            metrics = r.metrics or {}
            param_vals = r.parameter_values or {}
            threshold_val = param_vals.get("threshold")

            points.append(FairnessSensitivityPoint(
                parameter_value=threshold_val,
                spd=metrics.get("spd"),
                di=metrics.get("disparate_impact_ratio"),
                eod=metrics.get("equal_opportunity_difference"),
                selection_rates=metrics.get("selection_rates"),
            ))

        return FairnessSensitivityResponse(
            experiment_id=str(experiment_id),
            dimension="threshold",
            points=points,
            summary={
                "data_points": len(points),
                "available": any(p.spd is not None for p in points),
            },
        )

    # ─── Internal helpers ───────────────────────────────────────────

    def _check_access(self, exp: SimulationExperiment, user: Any) -> None:
        if hasattr(user, "organization_id") and exp.organization_id:
            if str(getattr(user, "organization_id", None)) != str(exp.organization_id):
                raise NotFoundError("Experiment not found.")

    def _parameter_ranges_from_dict(
        self, param_ranges: dict[str, Any],
    ) -> list:
        from app.domain.enums import SensitivityDimension
        from app.domain.simulation_experiment_schemas import ParameterRange

        ranges = []
        for dim_name, dim_data in param_ranges.items():
            try:
                dim = SensitivityDimension(dim_name)
            except ValueError:
                continue
            values = dim_data.get("values") or []
            ranges.append(ParameterRange(
                dimension=dim,
                values=values,
            ))
        return ranges

    def _to_response(self, exp: SimulationExperiment) -> ExperimentResponse:
        scenario = getattr(exp, "base_scenario", None)
        return ExperimentResponse(
            id=str(exp.id),
            organization_id=str(exp.organization_id) if exp.organization_id else None,
            sandbox_id=str(exp.sandbox_id) if exp.sandbox_id else None,
            base_scenario_id=str(exp.base_scenario_id),
            job_id=str(exp.job_id),
            created_by=str(exp.created_by),
            name=exp.name,
            description=exp.description,
            research_question=exp.research_question,
            hypothesis=exp.hypothesis,
            experiment_type=exp.experiment_type,
            status=exp.status,
            parameters=exp.parameters or {},
            parameter_ranges=exp.parameter_ranges or {},
            execution_config=exp.execution_config,
            generated_configs=exp.generated_configs,
            result_summary=exp.result_summary,
            sensitivity_results=exp.sensitivity_results,
            robustness_results=exp.robustness_results,
            stability_results=exp.stability_results,
            fairness_sensitivity_results=exp.fairness_sensitivity_results,
            candidate_stability_results=exp.candidate_stability_results,
            error_message=exp.error_message,
            total_configurations=exp.total_configurations,
            completed_configurations=exp.completed_configurations,
            failed_configurations=exp.failed_configurations,
            random_seed=exp.random_seed,
            experiment_version=exp.experiment_version,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            completed_at=exp.completed_at,
        )

    def _to_list_item(self, exp: SimulationExperiment) -> ExperimentListItem:
        scenario = getattr(exp, "base_scenario", None)
        job = getattr(exp, "job", None)
        creator = getattr(exp, "creator", None)
        return ExperimentListItem(
            id=str(exp.id),
            name=exp.name,
            description=exp.description,
            experiment_type=exp.experiment_type,
            status=exp.status,
            base_scenario_name=scenario.name if scenario else "",
            job_title=job.title if job else "",
            total_configurations=exp.total_configurations,
            completed_configurations=exp.completed_configurations,
            failed_configurations=exp.failed_configurations,
            created_by_name=creator.full_name if creator else "",
            created_at=exp.created_at,
            completed_at=exp.completed_at,
        )

    def _to_status_response(self, exp: SimulationExperiment) -> ExperimentStatusResponse:
        return ExperimentStatusResponse(
            experiment_id=str(exp.id),
            status=exp.status,
            total_configurations=exp.total_configurations,
            completed_configurations=exp.completed_configurations,
            failed_configurations=exp.failed_configurations,
            error_message=exp.error_message,
        )

    async def _audit(
        self,
        user: Any,
        event_type: AuditEventType,
        experiment_id: uuid.UUID,
    ) -> None:
        try:
            audit_svc = AuditService(self._session)
            await audit_svc.log(
                event_type=event_type,
                action=event_type.value,
                user_id=user.id,
                resource_type="simulation_experiment",
                resource_id=str(experiment_id),
                details={"experiment_id": str(experiment_id)},
            )
        except Exception:
            pass
