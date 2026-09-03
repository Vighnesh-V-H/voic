"""add OAuth state and provider connections

Revision ID: 0002_razorpay_oauth
Revises: 0001_identity_and_merchants
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_razorpay_oauth"
down_revision: Union[str, None] = "0001_identity_and_merchants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_states_state_hash", "oauth_states", ["state_hash"], unique=True)
    op.create_index("ix_oauth_states_merchant_id", "oauth_states", ["merchant_id"], unique=False)
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_account_id", sa.String(length=120), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "provider", name="uq_provider_connection_merchant"),
    )
    op.create_index(
        "ix_provider_connections_merchant_id", "provider_connections", ["merchant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_provider_connections_merchant_id", table_name="provider_connections")
    op.drop_table("provider_connections")
    op.drop_index("ix_oauth_states_merchant_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state_hash", table_name="oauth_states")
    op.drop_table("oauth_states")
