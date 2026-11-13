"""application screening - link screening_results to job_applications

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


# See 0022: batch mode must name the constraints it reflects into the rebuilt
# table, and the early migrations created unnamed inline foreign keys.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    # The column and its foreign key are added together in one batch step:
    # SQLite cannot ALTER in a constraint, so batch mode rewrites the table via
    # copy-and-move. It stays a plain ALTER on databases that support it.
    with op.batch_alter_table(
        "screening_results", naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column("application_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_screening_results_application_id",
            "job_applications",
            ["application_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_screening_results_application_id"),
        "screening_results",
        ["application_id"],
        unique=True,
    )
    # Backfill the explicit link from the existing (job_id, candidate_id)
    # natural key, which already identifies the application uniquely.
    op.execute(
        """
        UPDATE screening_results
        SET application_id = (
            SELECT ja.id
            FROM job_applications ja
            WHERE ja.job_id = screening_results.job_id
              AND ja.candidate_id = screening_results.candidate_id
        )
        WHERE application_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_screening_results_application_id"),
        table_name="screening_results",
    )
    with op.batch_alter_table(
        "screening_results", naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_column("application_id")
        batch_op.drop_constraint(
            "fk_screening_results_application_id", type_="foreignkey",
        )
