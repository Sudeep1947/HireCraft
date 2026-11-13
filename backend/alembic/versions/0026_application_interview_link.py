"""application <-> interview link for Phase 11

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-27

Phase 11 connects Interview Intelligence to the application-centric hiring
workflow. One additive, nullable column:

- ``interviews.application_id`` links an interview to the ``JobApplication`` it
  belongs to, so interview evidence has a single authoritative home on the
  application instead of being re-discovered from candidate+job pairs.

Nullable and ``ON DELETE SET NULL`` by design:

- **Nullable** because mock/practice interviews are not part of an application,
  and because every interview created before this migration belongs to the
  legacy job+candidate flow. Requiring the column would either invent
  applications for practice interviews or fail the migration.
- **No backfill.** An application is uniquely determined by
  ``(job_id, candidate_id)``, but a candidate may hold several interviews for
  one application, so inferring "which" application an old interview belongs to
  is a guess. The migration therefore leaves existing rows NULL rather than
  silently attaching historical interviews to applications nobody confirmed.
  Historic interviews stay fully reachable through the existing job- and
  candidate-scoped endpoints.
- **``ON DELETE SET NULL``** so removing an application preserves interview
  history rather than cascading it away, matching the application's other
  optional links (``resume``, ``decided_by``).

``interviews.status`` and ``job_applications.status`` are already ``String``
columns, so the new ``ApplicationStatus.INTERVIEWED`` value needs no schema
change and existing rows are unaffected.
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this runs on SQLite as well as PostgreSQL. The development
    # and test database is SQLite, which cannot ALTER a constraint in place and
    # would raise "No support for ALTER of constraints in SQLite dialect"; batch
    # mode copies the table, adds the column and its foreign key, and moves it
    # back. On PostgreSQL it degrades to a plain ALTER.
    with op.batch_alter_table("interviews") as batch:
        batch.add_column(
            sa.Column("application_id", sa.Uuid(), nullable=True),
        )
        batch.create_foreign_key(
            "fk_interviews_application_id",
            "job_applications",
            ["application_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_interviews_application_id", ["application_id"])


def downgrade() -> None:
    with op.batch_alter_table("interviews") as batch:
        batch.drop_index("ix_interviews_application_id")
        batch.drop_constraint("fk_interviews_application_id", type_="foreignkey")
        batch.drop_column("application_id")
