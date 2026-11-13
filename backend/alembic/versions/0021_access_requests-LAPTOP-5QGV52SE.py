"""0021 - Employee access requests.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("requested_role", sa.String(50), nullable=True),
        sa.Column("verification_token_hash", sa.String(255), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending_email_verification"),
        sa.Column("approved_role", sa.String(50), nullable=True),
        sa.Column("reviewed_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("activation_token_hash", sa.String(255), nullable=True),
        sa.Column("activation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_requests_email", "access_requests", ["email"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])
    op.create_index("ix_access_requests_organization_id", "access_requests", ["organization_id"])
    op.create_index("ix_access_requests_verification_token_hash", "access_requests", ["verification_token_hash"], unique=True)
    op.create_index("ix_access_requests_activation_token_hash", "access_requests", ["activation_token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_access_requests_activation_token_hash")
    op.drop_index("ix_access_requests_verification_token_hash")
    op.drop_index("ix_access_requests_organization_id")
    op.drop_index("ix_access_requests_status")
    op.drop_index("ix_access_requests_email")
    op.drop_table("access_requests")
