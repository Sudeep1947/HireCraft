"""Hiring Strategy Sandbox Service (Phase 12).

Orchestrates sandbox CRUD, strategy management, branching, duplication,
and comparison delegation. Reuses existing simulation infrastructure.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.enums import AuditEventType, SimulationStatus
from app.domain.hiring_strategy_sandbox_models import (
    HiringStrategySandbox,
    SandboxStrategy,
)
from app.domain.hiring_strategy_sandbox_schemas import (
    SandboxActivityItem,
    SandboxActivityResponse,
    SandboxCompareRequest,
    SandboxCreate,
    SandboxListResponse,
    SandboxListItem,
    SandboxResponse,
    SandboxUpdate,
    StrategyCreate,
    StrategyDuplicate,
    StrategyListResponse,
    StrategyListItem,
    StrategyResponse,
    StrategyUpdate,
)
from app.domain.models import User
from app.domain.simulation_models import SimulationScenario
from app.domain.simulation_schemas import SimulationConfiguration, SimulationScenarioCreate
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.sandbox import SandboxRepository, SandboxStrategyRepository
from app.repositories.simulation import SimulationRepository
from app.services.audit_service import AuditService
from app.services.simulation.configuration_validator import SimulationConfigurationValidator
from app.services.simulation.simulation_service import SimulationScenarioService

logger = get_logger(__name__)


class HiringStrategySandboxService:
    """Manages the Hiring Strategy Sandbox workspace."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._sandbox_repo = SandboxRepository(db)
        self._strategy_repo = SandboxStrategyRepository(db)
        self._scenario_repo = SimulationRepository(db)
        self._membership_repo = OrganizationMembershipRepository(db)

    # ─── Sandbox CRUD ─────────────────────────────────────────────

    async def create_sandbox(
        self, user: User, data: SandboxCreate,
    ) -> SandboxResponse:
        """Create a new sandbox with a baseline snapshot from the job."""
        job = await self._load_job(data.job_id, user)
        baseline = self._build_baseline_snapshot(job)

        sandbox = await self._sandbox_repo.create(
            organization_id=job.organization_id,
            job_id=job.id,
            created_by=user.id,
            name=data.name,
            description=data.description,
            status="active",
            baseline_snapshot=baseline,
        )

        await self._audit(AuditEventType.SANDBOX_CREATED, user, sandbox)
        logger.info("Sandbox created: id=%s user=%s job=%s", sandbox.id, user.id, job.id)

        return self._to_sandbox_response(sandbox, job)

    async def get_sandbox(
        self, user: User, sandbox_id: uuid.UUID,
    ) -> SandboxResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        return self._to_sandbox_response(sandbox, sandbox.job)

    async def list_sandboxes(self, user: User) -> SandboxListResponse:
        memberships = await self._membership_repo.get_user_organizations(user.id)
        org_ids = [m.organization_id for m in memberships]
        sandboxes = await self._sandbox_repo.list_visible(user.id, org_ids)

        items = []
        for sb in sandboxes:
            strategy_count = await self._sandbox_repo.count_strategies(sb.id)
            completed_count = await self._sandbox_repo.count_completed_strategies(sb.id)
            items.append(SandboxListItem(
                id=sb.id,
                organization_id=sb.organization_id,
                job_id=sb.job_id,
                created_by=sb.created_by,
                name=sb.name,
                status=sb.status,
                job_title=getattr(sb.job, "title", "") if sb.job else "",
                company=getattr(sb.job, "company", "") if sb.job else "",
                created_by_name=getattr(sb.creator, "full_name", "") if sb.creator else "",
                strategy_count=strategy_count,
                completed_count=completed_count,
                created_at=sb.created_at,
                updated_at=sb.updated_at,
            ))

        return SandboxListResponse(items=items, total=len(items))

    async def update_sandbox(
        self, user: User, sandbox_id: uuid.UUID, data: SandboxUpdate,
    ) -> SandboxResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        if data.name is not None:
            sandbox.name = data.name
        if data.description is not None:
            sandbox.description = data.description
        sandbox = await self._sandbox_repo.save(sandbox)
        await self._audit(AuditEventType.SANDBOX_UPDATED, user, sandbox)
        return self._to_sandbox_response(sandbox, sandbox.job)

    async def archive_sandbox(
        self, user: User, sandbox_id: uuid.UUID,
    ) -> SandboxResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        sandbox.status = "archived"
        sandbox.archived_at = datetime.now(timezone.utc)
        sandbox = await self._sandbox_repo.save(sandbox)
        await self._audit(AuditEventType.SANDBOX_ARCHIVED, user, sandbox)
        return self._to_sandbox_response(sandbox, sandbox.job)

    async def delete_sandbox(
        self, user: User, sandbox_id: uuid.UUID,
    ) -> None:
        sandbox = await self._load_sandbox(sandbox_id, user)
        await self._sandbox_repo.delete(sandbox)

    # ─── Strategy Management ──────────────────────────────────────

    async def create_strategy(
        self, user: User, sandbox_id: uuid.UUID, data: StrategyCreate,
    ) -> StrategyResponse:
        """Create a new strategy by creating a simulation scenario inside the sandbox."""
        sandbox = await self._load_sandbox(sandbox_id, user)

        # Build configuration
        if data.simulation_config:
            config_dict = data.simulation_config
            valid, issues = SimulationConfigurationValidator.validate(config_dict)
            if not valid:
                raise ValueError(f"Configuration validation failed: {'; '.join(i.message for i in issues)}")
            sim_config = SimulationConfiguration(**config_dict)
        else:
            # Default to baseline
            sim_config = SimulationConfiguration(**sandbox.baseline_snapshot)

        # Create scenario
        scenario_svc = SimulationScenarioService(self._db)
        create_data = SimulationScenarioCreate(
            job_id=sandbox.job_id,
            name=data.name,
            description=data.description,
            simulation_config=sim_config,
            metadata={"sandbox_id": str(sandbox.id), "source": "sandbox"},
        )
        scenario = await scenario_svc.create_scenario(user, create_data)

        # Link to sandbox
        strategy = await self._strategy_repo.create(
            sandbox_id=sandbox.id,
            scenario_id=scenario.id,
            parent_strategy_id=None,
            branch_name=None,
            tags=data.tags if data.tags else None,
            notes=data.notes,
            sort_order=0,
        )

        await self._audit(AuditEventType.SCENARIO_ADDED_TO_SANDBOX, user, sandbox, {
            "strategy_id": str(strategy.id),
            "scenario_id": str(scenario.id),
            "name": data.name,
        })

        return self._to_strategy_response(strategy)

    async def duplicate_strategy(
        self, user: User, sandbox_id: uuid.UUID,
        strategy_id: uuid.UUID, data: StrategyDuplicate,
    ) -> StrategyResponse:
        """Duplicate or branch an existing strategy."""
        sandbox = await self._load_sandbox(sandbox_id, user)
        source_strategy = await self._load_strategy(strategy_id, sandbox_id)

        source_scenario = await self._scenario_repo.get_with_details(source_strategy.scenario_id)
        if not source_scenario:
            raise ValueError("Source scenario not found")

        # Copy configuration from source
        config = source_scenario.simulation_config or source_scenario.baseline_config

        # Create new scenario
        scenario_svc = SimulationScenarioService(self._db)
        create_data = SimulationScenarioCreate(
            job_id=sandbox.job_id,
            name=data.name,
            description=data.description or f"{'Branch' if data.branch else 'Copy'} of {source_scenario.name}",
            simulation_config=SimulationConfiguration(**config),
            metadata={
                "sandbox_id": str(sandbox.id),
                "source": "sandbox_duplicate",
                "source_strategy_id": str(strategy_id),
                "source_scenario_id": str(source_strategy.scenario_id),
                "is_branch": data.branch,
            },
        )
        scenario = await scenario_svc.create_scenario(user, create_data)

        # Link to sandbox with lineage
        strategy = await self._strategy_repo.create(
            sandbox_id=sandbox.id,
            scenario_id=scenario.id,
            parent_strategy_id=strategy_id if data.branch else None,
            branch_name=data.name if data.branch else None,
            tags=data.tags if data.tags else None,
            notes=data.notes,
            sort_order=0,
        )

        event = AuditEventType.SCENARIO_BRANCHED if data.branch else AuditEventType.SCENARIO_DUPLICATED
        await self._audit(event, user, sandbox, {
            "strategy_id": str(strategy.id),
            "scenario_id": str(scenario.id),
            "source_strategy_id": str(strategy_id),
            "is_branch": data.branch,
        })

        return self._to_strategy_response(strategy)

    async def update_strategy(
        self, user: User, sandbox_id: uuid.UUID,
        strategy_id: uuid.UUID, data: StrategyUpdate,
    ) -> StrategyResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        strategy = await self._load_strategy(strategy_id, sandbox_id)

        if data.name is not None or data.tags is not None or data.notes is not None:
            if data.name is not None:
                # Update scenario name too
                scenario = await self._scenario_repo.get(strategy.scenario_id)
                if scenario:
                    scenario.name = data.name
                    await self._scenario_repo.save(scenario)
            if data.tags is not None:
                strategy.tags = data.tags
            if data.notes is not None:
                strategy.notes = data.notes
            strategy = await self._strategy_repo.save(strategy)

        return self._to_strategy_response(strategy)

    async def remove_strategy(
        self, user: User, sandbox_id: uuid.UUID, strategy_id: uuid.UUID,
    ) -> None:
        sandbox = await self._load_sandbox(sandbox_id, user)
        strategy = await self._load_strategy(strategy_id, sandbox_id)
        await self._strategy_repo.delete(strategy)

    async def list_strategies(
        self, user: User, sandbox_id: uuid.UUID,
    ) -> StrategyListResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        strategies = await self._strategy_repo.list_by_sandbox(sandbox_id)

        items = []
        for s in strategies:
            scenario = s.scenario
            config = scenario.simulation_config if scenario else {}
            weights = config.get("scoring_weights", {}) if config else {}
            items.append(StrategyListItem(
                id=s.id,
                scenario_id=s.scenario_id,
                parent_strategy_id=s.parent_strategy_id,
                branch_name=s.branch_name,
                name=scenario.name if scenario else "",
                status=scenario.status if scenario else "unknown",
                tags=s.tags,
                created_at=s.created_at,
                updated_at=s.updated_at,
                job_title=getattr(scenario.job, "title", "") if scenario and hasattr(scenario, "job") and scenario.job else "",
                threshold=config.get("threshold", 0) if config else 0,
                shortlist_size=config.get("shortlist_size", 0) if config else 0,
                skills_weight=weights.get("skills", 0) if weights else 0,
                experience_weight=weights.get("experience", 0) if weights else 0,
                total_candidates=scenario.total_candidates if scenario and hasattr(scenario, "total_candidates") else 0,
                qualified_candidates=scenario.qualified_candidates if scenario and hasattr(scenario, "qualified_candidates") else 0,
                shortlisted_candidates=scenario.shortlisted_candidates if scenario and hasattr(scenario, "shortlisted_candidates") else 0,
            ))

        return StrategyListResponse(items=items, total=len(items))

    async def get_strategy(
        self, user: User, sandbox_id: uuid.UUID, strategy_id: uuid.UUID,
    ) -> StrategyResponse:
        sandbox = await self._load_sandbox(sandbox_id, user)
        strategy = await self._load_strategy(strategy_id, sandbox_id)
        return self._to_strategy_response(strategy)

    async def compare_strategies(
        self, user: User, sandbox_id: uuid.UUID, data: SandboxCompareRequest,
    ) -> dict:
        """Delegate to Phase 10 comparison after validating sandbox membership."""
        sandbox = await self._load_sandbox(sandbox_id, user)

        # Validate all strategies belong to this sandbox
        scenario_ids = []
        for sid in data.strategy_ids:
            strategy = await self._load_strategy(sid, sandbox_id)
            scenario_ids.append(strategy.scenario_id)

        # Delegate to Phase 10 comparison service
        from app.domain.simulation_comparison_schemas import SimulationComparisonRequest
        from app.services.simulation.multi_scenario_comparison_service import MultiScenarioComparisonService

        comparison_svc = MultiScenarioComparisonService(self._db)
        request = SimulationComparisonRequest(scenario_ids=scenario_ids)
        result = await comparison_svc.compare(request)

        await self._audit(AuditEventType.SANDBOX_COMPARISON_STARTED, user, sandbox, {
            "strategy_ids": [str(s) for s in data.strategy_ids],
            "scenario_ids": [str(s) for s in scenario_ids],
        })

        return result.model_dump()

    async def get_activity(
        self, user: User, sandbox_id: uuid.UUID,
    ) -> SandboxActivityResponse:
        """Get recent activity for a sandbox from audit logs."""
        sandbox = await self._load_sandbox(sandbox_id, user)

        # Query audit events related to this sandbox
        from sqlalchemy import select
        from app.domain.models import AuditLog

        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == "hiring_strategy_sandbox",
                AuditLog.resource_id == str(sandbox_id),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(50)
        )
        result = await self._db.execute(stmt)
        logs = list(result.scalars().all())

        items = []
        for log in logs:
            items.append(SandboxActivityItem(
                timestamp=log.created_at,
                event_type=log.event_type,
                description=self._activity_description(log.event_type, log.details),
                user_name="",
                metadata=log.details,
            ))

        return SandboxActivityResponse(items=items)

    # ─── Helpers ──────────────────────────────────────────────────

    async def _load_job(self, job_id: uuid.UUID, user: User):
        from app.domain.models import Job
        from sqlalchemy import select
        stmt = select(Job).where(Job.id == job_id)
        result = await self._db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        # Organization isolation
        if (
            hasattr(job, "organization_id") and job.organization_id
            and hasattr(user, "organization_id") and user.organization_id
            and job.organization_id != user.organization_id
        ):
            raise PermissionError("Access denied: job belongs to another organization")
        return job

    async def _load_sandbox(self, sandbox_id: uuid.UUID, user: User) -> HiringStrategySandbox:
        sandbox = await self._sandbox_repo.get_with_details(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_id} not found")
        # Organization isolation
        if sandbox.organization_id and hasattr(user, "organization_id") and user.organization_id:
            if sandbox.organization_id != user.organization_id:
                if not await self._is_platform_admin(user):
                    raise PermissionError("Access denied: sandbox belongs to another organization")
        return sandbox

    async def _load_strategy(self, strategy_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxStrategy:
        strategy = await self._strategy_repo.get_with_scenario(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        if str(strategy.sandbox_id) != str(sandbox_id):
            raise ValueError("Strategy does not belong to this sandbox")
        return strategy

    async def _is_platform_admin(self, user: User) -> bool:
        from app.domain.enums import RoleName
        return any(r.name == RoleName.SUPER_ADMIN.value for r in getattr(user, "roles", []))

    def _build_baseline_snapshot(self, job) -> dict:
        """Build a baseline snapshot from the job's current configuration."""
        from app.services.simulation.simulation_service import SimulationScenarioService
        return SimulationScenarioService._build_baseline(job)

    def _to_sandbox_response(self, sandbox: HiringStrategySandbox, job) -> SandboxResponse:
        return SandboxResponse(
            id=sandbox.id,
            organization_id=sandbox.organization_id,
            job_id=sandbox.job_id,
            created_by=sandbox.created_by,
            name=sandbox.name,
            description=sandbox.description,
            status=sandbox.status,
            baseline_snapshot=sandbox.baseline_snapshot,
            metadata_json=sandbox.metadata_json,
            job_title=getattr(job, "title", "") if job else "",
            company=getattr(job, "company", "") if job else "",
            created_by_name=getattr(sandbox.creator, "full_name", "") if hasattr(sandbox, "creator") and sandbox.creator else "",
            archived_at=sandbox.archived_at,
            created_at=sandbox.created_at,
            updated_at=sandbox.updated_at,
        )

    def _to_strategy_response(self, strategy: SandboxStrategy) -> StrategyResponse:
        return StrategyResponse(
            id=strategy.id,
            sandbox_id=strategy.sandbox_id,
            scenario_id=strategy.scenario_id,
            parent_strategy_id=strategy.parent_strategy_id,
            branch_name=strategy.branch_name,
            name=strategy.scenario.name if strategy.scenario else "",
            description=strategy.scenario.description if strategy.scenario else None,
            tags=strategy.tags,
            notes=strategy.notes,
            sort_order=strategy.sort_order,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )

    def _activity_description(self, event_type: str, details: dict | None) -> str:
        details = details or {}
        name = details.get("name", "")
        if event_type == AuditEventType.SANDBOX_CREATED.value:
            return f"Created sandbox '{name}'"
        if event_type == AuditEventType.SCENARIO_ADDED_TO_SANDBOX.value:
            return f"Added strategy '{name}'"
        if event_type == AuditEventType.SCENARIO_BRANCHED.value:
            return f"Branched strategy '{name}'"
        if event_type == AuditEventType.SCENARIO_DUPLICATED.value:
            return f"Duplicated strategy '{name}'"
        if event_type == AuditEventType.SANDBOX_COMPARISON_STARTED.value:
            return "Started comparison"
        return event_type.replace("_", " ").title()

    async def _audit(self, event_type: AuditEventType, user: User, sandbox: HiringStrategySandbox, details: dict | None = None):
        try:
            audit_svc = AuditService(self._db)
            await audit_svc.log(
                event_type=event_type,
                action=event_type.value,
                user_id=user.id,
                organization_id=sandbox.organization_id,
                resource_type="hiring_strategy_sandbox",
                resource_id=str(sandbox.id),
                details=details or {},
            )
        except Exception:
            pass
