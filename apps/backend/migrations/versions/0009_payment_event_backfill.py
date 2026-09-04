"""backfill payment event price attribution from linked payments

Revision ID: 0009_payment_event_backfill
Revises: 0008_payment_event_price
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0009_payment_event_backfill"
down_revision: Union[str, None] = "0008_payment_event_price"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE payment_events AS e
        SET provider_price_id = p.provider_price_id
        FROM payments AS p
        WHERE e.provider_price_id IS NULL
          AND e.provider_payment_id IS NOT NULL
          AND p.provider_payment_id = e.provider_payment_id
          AND p.provider_price_id IS NOT NULL
          AND p.merchant_id = e.merchant_id
        """
    )


def downgrade() -> None:
    # Irreversible data backfill: new rows are stamped at ingest time.
    pass
