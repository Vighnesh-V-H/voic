"""add stripe provider connections and oauth states

Revision ID: 0002_stripe_provider_connection
Revises: 0001_identity_and_merchants
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_stripe_provider_connection"
down_revision: Union[str, None] = "0001_identity_and_merchants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_account_id"),
    )
    op.create_index("ix_provider_connections_merchant_id", "provider_connections", ["merchant_id"])
    op.create_index("ix_provider_connections_status", "provider_connections", ["status"])
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_states_state_hash", "oauth_states", ["state_hash"])
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
    op.create_index("ix_oauth_states_merchant_id", "oauth_states", ["merchant_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_merchant_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state_hash", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_provider_connections_status", table_name="provider_connections")
    op.drop_index("ix_provider_connections_merchant_id", table_name="provider_connections")
    op.drop_table("provider_connections")
