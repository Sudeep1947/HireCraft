"""scheduled date/time + stored link for assigned assessments

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-03

Phase 12 made an assessment assignable from an application, but "assign" was the
only verb the data model had. ``ApplicationAssessmentAssignRequest`` carried
nothing but an ``assessment_id`` and ``candidate_assessments`` had no column for a
chosen date and time, so the only timestamp an assignment carried was
``assigned_at`` -- the instant the recruiter clicked the button. The candidate API
published that value as ``scheduled_at``, which meant the candidate's assessment
page could only ever say "Scheduled <the moment you were assigned>". A recruiter
could not schedule anything, and a reschedule had nowhere to be written: posting
the same assignment again was answered with ``already_assigned`` and changed
nothing. Two smaller gaps came from the same root: the take-link was rebuilt as an
f-string in two separate readers instead of being recorded, and
``notifications`` had no column to hold a destination, so the candidate's
notification page had to guess a route from the notification type and every
assessment notification landed on the list rather than the assessment.

This migration adds the storage for all three. It changes no existing column, no
status, no attempt lifecycle and no existing behaviour; it adds the columns the
already-written assign path was missing.

Columns added
-------------

- ``candidate_assessments.scheduled_for`` is the date and time the recruiter
  chose. It is deliberately distinct from ``assigned_at``, which stays exactly
  what it was -- the moment of assignment, an audit fact -- because "when was this
  asked for" and "when is this due" are different facts and overloading one
  column to mean both is what made the feature impossible to express.

- ``candidate_assessments.assessment_link`` records the link issued with this
  assignment, so the candidate page, the notification and the database cannot
  disagree about where the assessment lives. It is written from the same single
  helper the readers use, so it is a record of what was issued rather than a
  second, independently maintained copy of the route.

- ``notifications.action_link`` is the destination for one notification. It is
  the general fix for a problem that was previously worked around by switching on
  ``notification_type`` in the frontend, which could only ever route a candidate
  as far as a list page.

Nullable, with no backfill, on purpose
--------------------------------------

- **``scheduled_for`` is nullable and not backfilled.** Every existing assignment
  genuinely has no scheduled time -- it was never chosen. Inferring one from
  ``assigned_at`` would assert that the recruiter picked that moment, which is
  false. NULL is the honest value, and every reader falls back to
  ``assigned_at`` so an old row renders exactly as it did before this migration
  rather than disappearing.

- **``assessment_link`` is nullable and not backfilled** for the same reason: no
  link was ever stored, so there is nothing truthful to backfill from. Readers
  derive the link for these rows from the assessment id they already hold, which
  reproduces the pre-migration behaviour exactly.

- **``action_link`` is nullable and not backfilled.** Notifications that predate
  this column have no recorded destination, and the frontend already routes them
  by type. Making it nullable keeps every existing notification rendering exactly
  as before instead of losing its View action.

Indexes
-------

None are added. ``scheduled_for`` is only ever read as part of an already-loaded
attempt row (the candidate's own list, one application's attempts), never as a
filter or a join key, so an index would be pure write cost. ``assessment_link`` is
written once and read as a column of a row already selected by ``candidate_id``,
which is indexed. ``action_link`` is likewise read only alongside rows fetched by
the indexed ``user_id``.

Datetime storage
----------------

``scheduled_for`` is ``DateTime(timezone=True)``, matching ``assigned_at``,
``expires_at`` and ``Interview.scheduled_at``. As migration 0028 records,
SQLite -- the development and test database -- returns naive values, so every
comparison against it goes through the service's existing ``_aware`` helper rather
than assuming awareness.
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this runs on SQLite as well as PostgreSQL. The development and
    # test database is SQLite, which cannot ADD a column carrying a constraint in
    # place; batch mode copies the table, adds the columns and moves it back. On
    # PostgreSQL it degrades to a plain ALTER TABLE ADD COLUMN.
    with op.batch_alter_table("candidate_assessments") as batch:
        batch.add_column(
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("assessment_link", sa.String(length=500), nullable=True)
        )

    with op.batch_alter_table("notifications") as batch:
        batch.add_column(
            sa.Column("action_link", sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("action_link")

    with op.batch_alter_table("candidate_assessments") as batch:
        batch.drop_column("assessment_link")
        batch.drop_column("scheduled_for")