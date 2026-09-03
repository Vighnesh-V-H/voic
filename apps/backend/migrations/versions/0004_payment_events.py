"""add payment events

Revision ID: 0004_payment_events
Revises: 0003_payments
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_payment_events"
down_revision: Union[str, None] = "0003_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_connection_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("customer_reference", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_connection_id"], ["provider_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id"),
    )
    op.create_index("ix_payment_events_merchant_id", "payment_events", ["merchant_id"])
    op.create_index("ix_payment_events_provider_connection_id", "payment_events", ["provider_connection_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_provider_connection_id", table_name="payment_events")
    op.drop_index("ix_payment_events_merchant_id", table_name="payment_events")
    op.drop_table("payment_events")
