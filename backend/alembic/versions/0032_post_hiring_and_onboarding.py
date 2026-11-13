"""Add post-hiring offer management, document verification, and employee onboarding tables

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-31

Creates job_offers, candidate_documents, employees, and onboarding_tasks tables.
Supports PostgreSQL and SQLite.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    tables = set(inspect(bind).get_table_names())
    return table_name in tables


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "job_offers"):
        op.create_table(
            "job_offers",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("candidate_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("designation", sa.String(length=255), nullable=False),
            sa.Column("department", sa.String(length=255), nullable=False),
            sa.Column("employment_type", sa.String(length=50), nullable=False, server_default="full_time"),
            sa.Column("offered_salary", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
            sa.Column("work_location", sa.String(length=255), nullable=False),
            sa.Column("reporting_manager", sa.String(length=255), nullable=True),
            sa.Column("joining_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("probation_period_months", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("benefits_summary", sa.Text(), nullable=True),
            sa.Column("additional_terms", sa.Text(), nullable=True),
            sa.Column("offer_expiry_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("hr_remarks", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("decline_reason", sa.Text(), nullable=True),
            sa.Column("candidate_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index("ix_job_offers_app", "job_offers", ["application_id"])
        op.create_index("ix_job_offers_cand", "job_offers", ["candidate_id"])
        op.create_index("ix_job_offers_org", "job_offers", ["organization_id"])
        op.create_index("ix_job_offers_status", "job_offers", ["status"])

    if not _table_exists(bind, "candidate_documents"):
        op.create_table(
            "candidate_documents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("candidate_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("document_title", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="not_submitted"),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("hr_remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index("ix_candidate_docs_app", "candidate_documents", ["application_id"])
        op.create_index("ix_candidate_docs_cand", "candidate_documents", ["candidate_id"])
        op.create_index("ix_candidate_docs_org", "candidate_documents", ["organization_id"])
        op.create_index("ix_candidate_docs_type", "candidate_documents", ["document_type"])
        op.create_index("ix_candidate_docs_status", "candidate_documents", ["status"])

    if not _table_exists(bind, "employees"):
        op.create_table(
            "employees",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("employee_id", sa.String(length=50), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("application_id", sa.String(length=36), sa.ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("designation", sa.String(length=255), nullable=False),
            sa.Column("department", sa.String(length=255), nullable=False),
            sa.Column("employment_type", sa.String(length=50), nullable=False, server_default="full_time"),
            sa.Column("work_location", sa.String(length=255), nullable=False),
            sa.Column("reporting_manager", sa.String(length=255), nullable=True),
            sa.Column("joining_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("employment_status", sa.String(length=30), nullable=False, server_default="onboarding"),
            sa.Column("onboarding_status", sa.String(length=30), nullable=False, server_default="in_progress"),
            sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("profile_picture_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.UniqueConstraint("organization_id", "employee_id", name="uq_org_employee_id"),
        )
        op.create_index("ix_employees_user", "employees", ["user_id"])
        op.create_index("ix_employees_org", "employees", ["organization_id"])
        op.create_index("ix_employees_emp_id", "employees", ["employee_id"])
        op.create_index("ix_employees_status", "employees", ["employment_status"])

    if not _table_exists(bind, "onboarding_tasks"):
        op.create_table(
            "onboarding_tasks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False, server_default="documentation"),
            sa.Column("assigned_to_role", sa.String(length=50), nullable=False, server_default="employee"),
            sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("hr_remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index("ix_onboarding_tasks_emp", "onboarding_tasks", ["employee_id"])
        op.create_index("ix_onboarding_tasks_org", "onboarding_tasks", ["organization_id"])


def downgrade() -> None:
    op.drop_table("onboarding_tasks")
    op.drop_table("employees")
    op.drop_table("candidate_documents")
    op.drop_table("job_offers")
