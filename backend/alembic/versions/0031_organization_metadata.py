"""Add industry, website, and location to organizations

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-27

Adds optional industry, website, and location metadata columns to organizations.
Supports batch alteration for SQLite compatibility as well as PostgreSQL.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    columns = {c["name"] for c in inspect(bind).get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("organizations") as batch:
        if not _column_exists(bind, "organizations", "industry"):
            batch.add_column(
                sa.Column("industry", sa.String(length=255), nullable=True)
            )
        if not _column_exists(bind, "organizations", "website"):
            batch.add_column(
                sa.Column("website", sa.String(length=500), nullable=True)
            )
        if not _column_exists(bind, "organizations", "location"):
            batch.add_column(
                sa.Column("location", sa.String(length=255), nullable=True)
            )


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("location")
        batch.drop_column("website")
        batch.drop_column("industry")
