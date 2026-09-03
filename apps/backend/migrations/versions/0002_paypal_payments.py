"""add provider connections and PayPal payment transactions

Revision ID: 0002_paypal_payments
Revises: 0001_identity_and_merchants
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_paypal_payments"
down_revision: Union[str, None] = "0001_identity_and_merchants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_account_id", sa.String(length=120), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
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
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_order_id", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approval_url", sa.String(length=2048), nullable=True),
        sa.Column("capture_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_order_id", name="uq_payment_transaction_provider_order"),
    )
    op.create_index(
        "ix_payment_transactions_merchant_id", "payment_transactions", ["merchant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_merchant_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_provider_connections_merchant_id", table_name="provider_connections")
    op.drop_table("provider_connections")
