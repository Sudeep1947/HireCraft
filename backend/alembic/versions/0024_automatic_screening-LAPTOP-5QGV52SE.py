"""automatic application screening - execution state on job_applications

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("screening_status", sa.String(20), False, "not_started"),
    ("screening_attempts", sa.Integer(), False, "0"),
    ("screening_task_id", sa.String(255), True, None),
    ("screening_error", sa.Text(), True, None),
    ("screening_started_at", sa.DateTime(timezone=True), True, None),
    ("screening_completed_at", sa.DateTime(timezone=True), True, None),
)


def upgrade() -> None:
    for name, type_, nullable, default in _COLUMNS:
        op.add_column(
            "job_applications",
            sa.Column(
                name,
                type_,
                nullable=nullable,
                server_default=default,
            ),
        )


def downgrade() -> None:
    for name, _type, _nullable, _default in reversed(_COLUMNS):
        op.drop_column("job_applications", name)
