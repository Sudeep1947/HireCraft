"""interview room + attendance for Phase 14

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-01

Phase 11 made an interview schedulable from an application and Phase 8 gave the
application a final decision, but nothing ever connected the two ends: a recruiter
scheduled an interview, the candidate was shown a read-only card with nothing to
attend, and the interview could only leave ``scheduled`` if a recruiter recorded
it completed by hand. ``InterviewStatus.IN_PROGRESS`` existed and was handled by
the Phase 11 service, yet no production code path ever wrote it -- only mock
practice sessions did. This migration adds the attendance record that was
missing; it changes no existing column, status or decision.

Columns added
-------------

- ``interviews.room_id`` is the shared room. It is a column on the interview
  rather than a new table because there is exactly one room per interview and
  both participants are already that row's ``candidate_id`` / ``recruiter_id``;
  a separate table would have to guarantee 1:1 with the interview, which nothing
  else in the schema guarantees.

- ``interviews.timezone`` records the interviewer's wall-clock zone so the join
  window can be explained in the clock the recruiter scheduled it in. An IANA
  name rather than a fixed offset, since the offset that applies is a fact about
  the scheduled time and not about whenever the row is later read.

- ``interviews.candidate_joined_at`` / ``.recruiter_joined_at`` are the presence
  record. These are first-entry timestamps and are never cleared, so "the
  candidate joined at 14:03" stays true for the life of the interview and a page
  refresh cannot erase it.

Nullable and defaulted deliberately
------------------------------------

- **``room_id`` is nullable with no backfill.** It is assigned lazily, the first
  time a room is read or joined. Every interview that already exists therefore
  gets a room on demand, including interviews scheduled before this migration,
  and a migration cannot invent a room id for rows it cannot reason about. Unique
  where present; the many NULLs of not-yet-assigned rooms are fine in both
  PostgreSQL and SQLite.

- **``timezone`` is NOT NULL with a server default of ``'UTC'``.`` Existing rows
  genuinely have no recorded zone -- ``scheduled_at`` is stored verbatim from the
  request body and was never normalized -- so claiming UTC for them would assert
  something unrecorded. The default keeps the column honest for new rows while
  the room service falls back to UTC whenever it needs to *interpret* a stored
  time, which is where an unknown zone actually matters.

Datetime storage
----------------

The three new timestamps are ``DateTime(timezone=True)``, matching
``scheduled_at``, ``started_at`` and ``completed_at``. Note that SQLite -- the
development and test database -- does not persist the offset and returns naive
values, so the room service normalizes to UTC before any comparison rather than
assuming awareness. Getting this wrong would raise ``TypeError`` comparing a
naive value from the database with an aware ``datetime.now(timezone.utc)``, and
only under the test database, which is exactly the failure this note exists to
prevent.

Indexes
-------

``ix_interviews_room_id`` comes from the unique constraint on ``room_id``. No
index is added for the two presence columns: they are read only as part of a
single already-loaded interview row, so an index would be write cost for a query
that is never issued on its own.
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this runs on SQLite as well as PostgreSQL, which cannot ADD a
    # column carrying a unique constraint in place. On PostgreSQL it degrades to a
    # plain ALTER TABLE ADD COLUMN.
    with op.batch_alter_table("interviews") as batch:
        batch.add_column(sa.Column("room_id", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column(
                "timezone",
                sa.String(length=64),
                nullable=False,
                server_default="UTC",
            )
        )
        batch.add_column(
            sa.Column(
                "candidate_joined_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch.add_column(
            sa.Column(
                "recruiter_joined_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        # Named so downgrade can drop it explicitly; a bare unique=True would
        # produce an anonymous constraint that batch mode cannot remove.
        batch.create_unique_constraint("uq_interviews_room_id", ["room_id"])


def downgrade() -> None:
    with op.batch_alter_table("interviews") as batch:
        batch.drop_constraint("uq_interviews_room_id", type_="unique")
        batch.drop_column("recruiter_joined_at")
        batch.drop_column("candidate_joined_at")
        batch.drop_column("timezone")
        batch.drop_column("room_id")