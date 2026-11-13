"""application decisions - structured rejection reason code + notification dedupe

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-26

Both changes are additive and nullable, so no existing row is rewritten and
no data is lost:

- ``job_applications.decision_reason_code`` stores the validated
  ``RejectionReason`` code the recruiter selected. The candidate-facing text is
  derived from this controlled code, never from recruiter prose, so an internal
  comment can never leak to a candidate.
- ``notifications.dedupe_key`` gives the existing notification system an
  idempotency key. Uniqueness makes concurrent dispatchers safe, and NULL rows
  (all pre-existing notifications) remain valid and unconstrained.
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_applications",
        sa.Column("decision_reason_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("dedupe_key", sa.String(255), nullable=True),
    )
    op.create_index(
        "uq_notifications_dedupe_key",
        "notifications",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_dedupe_key", table_name="notifications")
    op.drop_column("notifications", "dedupe_key")
    op.drop_column("job_applications", "decision_reason_code")
