"""add payments.provider_invoice_id

Revision ID: 0006_payment_invoice
Revises: 0005_payment_subscription
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_payment_invoice"
down_revision: Union[str, None] = "0005_payment_subscription"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("provider_invoice_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_payments_provider_invoice_id", "payments", ["provider", "provider_invoice_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_invoice_id", "payments", type_="unique")
    op.drop_column("payments", "provider_invoice_id")
