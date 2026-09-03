"""add payments

Revision ID: 0003_payments
Revises: 0002_stripe_provider_connection
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_payments"
down_revision: Union[str, None] = "0002_stripe_provider_connection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_connection_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_link_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_link_url", sa.String(length=2048), nullable=True),
        sa.Column("provider_price_id", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_connection_id"], ["provider_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_payment_id"),
        sa.UniqueConstraint("provider", "provider_payment_link_id"),
        sa.UniqueConstraint("merchant_id", "idempotency_key"),
    )
    op.create_index("ix_payments_merchant_id", "payments", ["merchant_id"])
    op.create_index("ix_payments_provider_connection_id", "payments", ["provider_connection_id"])
    op.create_index("ix_payments_status", "payments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_provider_connection_id", table_name="payments")
    op.drop_index("ix_payments_merchant_id", table_name="payments")
    op.drop_table("payments")
