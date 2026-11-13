"""Phase 13: Simulation Reports & Decision Intelligence.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sandbox_id", sa.Uuid(), sa.ForeignKey("hiring_strategy_sandboxes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("scenario_id", sa.Uuid(), sa.ForeignKey("simulation_scenarios.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("execution_id", sa.Uuid(), sa.ForeignKey("simulation_executions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("report_type", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="requested", nullable=False, index=True),
        sa.Column("format", sa.String(20), server_default="web", nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("report_data", sa.JSON(), nullable=True),
        sa.Column("file_reference", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_version", sa.String(30), server_default="1.0", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_simulation_reports_org_status", "simulation_reports", ["organization_id", "status"])
    op.create_index("ix_simulation_reports_type_format", "simulation_reports", ["report_type", "format"])


def downgrade() -> None:
    op.drop_index("ix_simulation_reports_type_format", "simulation_reports")
    op.drop_index("ix_simulation_reports_org_status", "simulation_reports")
    op.drop_table("simulation_reports")
