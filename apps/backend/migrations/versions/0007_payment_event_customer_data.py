"""store normalized Stripe customer data on payment events

Revision ID: 0007_payment_event_customer_data
Revises: 0006_payment_invoice
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_payment_event_customer_data"
down_revision: Union[str, None] = "0006_payment_invoice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_events", sa.Column("customer_email", sa.String(length=320), nullable=True))
    op.add_column("payment_events", sa.Column("customer_phone", sa.String(length=64), nullable=True))
    op.add_column("payment_events", sa.Column("payment_status", sa.String(length=20), nullable=True))
    op.create_index("ix_payment_events_payment_status", "payment_events", ["payment_status"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_payment_status", table_name="payment_events")
    op.drop_column("payment_events", "payment_status")
    op.drop_column("payment_events", "customer_phone")
    op.drop_column("payment_events", "customer_email")
