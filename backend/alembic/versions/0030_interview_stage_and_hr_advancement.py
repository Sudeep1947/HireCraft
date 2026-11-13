"""interview stage, reschedule marker and HR advancement

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-17

Phase 11 made an interview schedulable from an application and Phase 14 gave it a
shared room, but the workflow had one interview and one question -- "where is this
candidate" -- and no way to say "whose interview is this". A recruiter interview
and an HR interview are two separate rounds that can each be scheduled, moved,
cancelled or completed independently; without a stage column the two collapse into
the single ``interviews.status``, and "recruiter interview completed, HR interview
not yet scheduled" cannot be represented. This migration adds that stage, the
marker that lets the room say an interview was rescheduled, and the two columns
that record a candidate having been advanced from the recruiter stage to HR.

Columns added
-------------

- ``interviews.stage`` is ``recruiter`` (the default) or ``hr``. It is not a
  status: ``status`` still means scheduled / in progress / completed / cancelled,
  and ``job_applications.status`` still means where the candidate is in the funnel.
  Stage is kept separable on purpose so advancing to HR is not a hiring decision
  and does not move the application status.

- ``interviews.rescheduled_at`` records when an interview was last moved to a new
  time. Nullable, written only by an explicit reschedule. It lets the room show
  "rescheduled, waiting for the new time" instead of a plain "upcoming", which the
  scheduled time alone cannot express, and it never completes the interview.

- ``job_applications.advanced_to_hr_at`` / ``advanced_to_hr_by`` record that a
  recruiter advanced the candidate to the HR interview stage and who did it.
  Nullable because most applications are never advanced that far, and because
  advancing is eligibility for a second round -- not a status change, not a hire
  and not an HR interview time, which the recruiter must still choose explicitly.

Additive and backfill-free on purpose
-------------------------------------

Every column is nullable or carries a server default, so existing rows keep their
current meaning without a data migration. ``stage`` defaults to ``recruiter``,
which is exactly what every interview that predates this column was: a
recruiter-driven round. ``rescheduled_at`` and the HR markers stay NULL, which is
the honest value -- no existing interview was rescheduled and no existing
application was advanced, so inferring either would assert something that never
happened.

Indexes
-------

None are added. ``stage`` is only ever read as a column of an already-loaded
interview row (an application's interviews, one interview), never as a filter or a
join key. The HR markers are read off the ``job_applications`` row already
selected by the indexed application or candidate id.

Datetime storage
----------------

All three timestamps are ``DateTime(timezone=True)``, matching ``scheduled_at``
and the rest of the interview timestamps. As migration 0028 records, SQLite -- the
development and test database -- returns naive values, so comparisons go through
the service's existing normalization rather than assuming awareness.
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this runs on SQLite as well as PostgreSQL. The development and
    # test database is SQLite, which cannot ADD a column carrying a constraint in
    # place; batch mode copies the table, adds the columns and moves it back. On
    # PostgreSQL it degrades to a plain ALTER TABLE ADD COLUMN.
    with op.batch_alter_table("interviews") as batch:
        batch.add_column(
            sa.Column(
                "stage",
                sa.String(length=20),
                nullable=False,
                server_default="recruiter",
            )
        )
        batch.add_column(
            sa.Column("rescheduled_at", sa.DateTime(timezone=True), nullable=True)
        )

    with op.batch_alter_table("job_applications") as batch:
        batch.add_column(
            sa.Column("advanced_to_hr_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "advanced_to_hr_by",
                sa.String(length=32),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("job_applications") as batch:
        batch.drop_column("advanced_to_hr_by")
        batch.drop_column("advanced_to_hr_at")

    with op.batch_alter_table("interviews") as batch:
        batch.drop_column("rescheduled_at")
        batch.drop_column("stage")
