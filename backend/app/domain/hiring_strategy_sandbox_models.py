"""SQLAlchemy model for Hiring Strategy Sandbox (Phase 12).

A sandbox is a workspace containing multiple related hypothetical hiring
strategies. It references a job and captures a baseline configuration
snapshot at creation time. Scenarios inside the sandbox are linked via
foreign keys with parent-child lineage tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class HiringStrategySandbox(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hiring_strategy_sandboxes"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    baseline_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization | None"] = relationship(
        "Organization", backref="hiring_strategy_sandboxes",
    )
    job: Mapped["Job"] = relationship("Job", backref="hiring_strategy_sandboxes")
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], backref="hiring_strategy_sandboxes",
    )
    strategies: Mapped[list["SandboxStrategy"]] = relationship(
        "SandboxStrategy", back_populates="sandbox", cascade="all, delete-orphan",
    )


class SandboxStrategy(Base, UUIDMixin, TimestampMixin):
    """A single strategy (scenario) inside a hiring strategy sandbox.

    Links to an existing SimulationScenario via scenario_id.
    Tracks parent lineage for branching/duplication.
    """
    __tablename__ = "sandbox_strategies"

    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hiring_strategy_sandboxes.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    parent_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sandbox_strategies.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sandbox: Mapped["HiringStrategySandbox"] = relationship(
        "HiringStrategySandbox", back_populates="strategies",
    )
    scenario: Mapped["SimulationScenario"] = relationship(
        "SimulationScenario", backref="sandbox_strategies",
    )
    parent_strategy: Mapped["SandboxStrategy | None"] = relationship(
        "SandboxStrategy", remote_side="SandboxStrategy.id", backref="child_strategies",
    )
