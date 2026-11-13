"""application <-> assessment attempt link for Phase 12

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-27

Phase 12 connects the existing Assessment Platform to the application-centric
hiring workflow. The assessment engine, question bank, attempt lifecycle and
grading are all untouched; this migration only adds the link that was missing.

Why no ``application_assignments`` table
----------------------------------------

The conceptual model in the phase brief is Application 1--N Assignment 1--N
Attempt -- 1 Result. The repository already has the second half of that, and its
"attempt" table carries an ``assigned`` status that no code path ever wrote and a
model default of ``assigned`` that every writer overrode. An assignment and an
attempt are therefore the same row: a recruiter creates it in ``assigned`` state
and the candidate starts it. Creating a separate assignments table would mean a
second attempt counter, a second place to enforce ``allowed_attempts``, and a
second way for a result to lose its application - all of which the brief forbids.

Columns added
-------------

- ``candidate_assessments.application_id`` links an attempt to the
  ``JobApplication`` it belongs to, so an assessment result has one
  authoritative home on the application.
- ``candidate_assessments.assigned_by`` / ``.assigned_at`` record who assigned
  the attempt and when. Both nullable: a candidate may still self-start a
  published assessment (existing behaviour, preserved), and for that attempt
  nobody assigned it, so NULL is the honest value rather than a placeholder.

Nullable and ``ON DELETE SET NULL`` by design
----------------------------------------------

- **Nullable** because a self-started attempt belongs to no application, and every
  attempt that exists today predates application-driven assignment. Requiring it
  would either invent applications or fail the migration.
- **No backfill.** ``(job_id, candidate_id)`` uniquely identifies an
  application, and an assessment carries a nullable ``job_id`` of its own, so the
  inference is a guess: a candidate's attempt at a job-scoped assessment is
  *probably* about that application, but the platform cannot prove the attempt was
  taken in response to that application. Existing rows stay NULL and remain fully
  reachable through the existing candidate-scoped ``/assessments/me`` endpoint.
  This is the same reasoning migration 0026 used for interviews.
- **``ON DELETE SET NULL``** so removing an application preserves the candidate's
  attempt and result history instead of cascading it away, matching the
  application's other optional links (``resume``, ``decided_by``) and
  ``interviews.application_id``.

Indexes
-------

``ix_candidate_assessments_application_id`` and
``ix_candidate_assessments_assigned_by`` are added because both are now
filter/join keys: the recruiter application page reads attempts by application,
and the audit trail reads the assigning actor. The pre-existing indexes on
``assessment_id``, ``candidate_id`` and ``status`` are untouched.

No status change is included. ``ApplicationStatus`` deliberately gains no
assessment stage: an assessment result is decision-support evidence and must not
appear in the application state machine, or "assessment assigned" would become a
pipeline stage and a passing score would look like a decision. Assessment state
lives on the attempt, where the attempt engine already owns it.
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this runs on SQLite as well as PostgreSQL. The development
    # and test database is SQLite, which cannot ALTER a constraint in place and
    # would raise "No support for ALTER of constraints in SQLite dialect"; batch
    # mode copies the table, adds the columns and their foreign keys, and moves it
    # back. On PostgreSQL it degrades to a plain ALTER.
    with op.batch_alter_table("candidate_assessments") as batch:
        batch.add_column(
            sa.Column("application_id", sa.Uuid(), nullable=True),
        )
        batch.add_column(
            sa.Column("assigned_by", sa.Uuid(), nullable=True),
        )
        batch.add_column(
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch.create_foreign_key(
            "fk_candidate_assessments_application_id",
            "job_applications",
            ["application_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_candidate_assessments_assigned_by",
            "users",
            ["assigned_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_candidate_assessments_application_id", ["application_id"]
        )
        batch.create_index("ix_candidate_assessments_assigned_by", ["assigned_by"])


def downgrade() -> None:
    with op.batch_alter_table("candidate_assessments") as batch:
        batch.drop_index("ix_candidate_assessments_assigned_by")
        batch.drop_index("ix_candidate_assessments_application_id")
        batch.drop_constraint(
            "fk_candidate_assessments_assigned_by", type_="foreignkey"
        )
        batch.drop_constraint(
            "fk_candidate_assessments_application_id", type_="foreignkey"
        )
        batch.drop_column("assigned_at")
        batch.drop_column("assigned_by")
        batch.drop_column("application_id")
