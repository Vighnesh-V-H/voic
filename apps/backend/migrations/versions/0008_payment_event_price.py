"""attribute payment events to a Voic price for product mapping

Revision ID: 0008_payment_event_price
Revises: 0007_payment_event_customer_data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_payment_event_price"
down_revision: Union[str, None] = "0007_payment_event_customer_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_events", sa.Column("provider_price_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_events", "provider_price_id")
