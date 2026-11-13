"""application lifecycle - decision fields + status history

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


# Batch mode has to name every constraint it reflects into the rebuilt table,
# and the tables created by the early migrations carry unnamed inline foreign
# keys. This convention gives those a deterministic name during the rebuild.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    # Batch mode throughout: ``decided_by`` carries a foreign key, and SQLite
    # cannot add a column with an inline constraint. Alembic's batch strategy
    # rewrites the table via copy-and-move, so this works on SQLite and is a
    # plain ALTER on databases that support it.
    with op.batch_alter_table(
        "job_applications", naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column("decision_reason", sa.String(255), nullable=True),
        )
        batch_op.add_column(
            sa.Column("decision_comment", sa.Text(), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "decided_by",
                sa.Uuid(),
                # Named explicitly: batch mode cannot derive a name for an
                # inline constraint it has to carry into the rebuilt table.
                sa.ForeignKey(
                    "users.id",
                    name="fk_job_applications_decided_by_users",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
        )
        batch_op.add_column(
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_status_history_application_id"),
        "application_status_history", ["application_id"], unique=False,
    )
    op.create_index(
        op.f("ix_application_status_history_organization_id"),
        "application_status_history", ["organization_id"], unique=False,
    )
    op.create_index(
        op.f("ix_application_status_history_changed_by"),
        "application_status_history", ["changed_by"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_application_status_history_changed_by"),
        table_name="application_status_history",
    )
    op.drop_index(
        op.f("ix_application_status_history_organization_id"),
        table_name="application_status_history",
    )
    op.drop_index(
        op.f("ix_application_status_history_application_id"),
        table_name="application_status_history",
    )
    op.drop_table("application_status_history")

    with op.batch_alter_table(
        "job_applications", naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_column("decided_at")
        batch_op.drop_column("decided_by")
        batch_op.drop_column("decision_comment")
        batch_op.drop_column("decision_reason")