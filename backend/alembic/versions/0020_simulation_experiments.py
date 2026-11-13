"""Phase 14: simulation_experiments, simulation_experiment_results tables

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sandbox_id", sa.Uuid(), sa.ForeignKey("hiring_strategy_sandboxes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("base_scenario_id", sa.Uuid(), sa.ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("research_question", sa.Text(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("experiment_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default="draft"),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("parameter_ranges", sa.JSON(), nullable=False),
        sa.Column("execution_config", sa.JSON(), nullable=True),
        sa.Column("generated_configs", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("sensitivity_results", sa.JSON(), nullable=True),
        sa.Column("robustness_results", sa.JSON(), nullable=True),
        sa.Column("stability_results", sa.JSON(), nullable=True),
        sa.Column("fairness_sensitivity_results", sa.JSON(), nullable=True),
        sa.Column("candidate_stability_results", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_configurations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_configurations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_configurations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("experiment_version", sa.String(30), nullable=False, server_default="1.0"),
        sa.Column("configuration_hash", sa.String(64), nullable=True, index=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "simulation_experiment_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("simulation_experiments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("simulation_scenario_id", sa.Uuid(), sa.ForeignKey("simulation_scenarios.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("simulation_execution_id", sa.Uuid(), sa.ForeignKey("simulation_executions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("parameter_values", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=True),
        sa.Column("execution_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("candidate_metrics", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("simulation_experiment_results")
    op.drop_table("simulation_experiments")
