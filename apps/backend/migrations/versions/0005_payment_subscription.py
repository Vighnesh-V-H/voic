"""add payments.provider_subscription_id

Revision ID: 0005_payment_subscription
Revises: 0004_payment_events
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_payment_subscription"
down_revision: Union[str, None] = "0004_payment_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("provider_subscription_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_payments_provider_subscription_id", "payments", ["provider", "provider_subscription_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_subscription_id", "payments", type_="unique")
    op.drop_column("payments", "provider_subscription_id")
