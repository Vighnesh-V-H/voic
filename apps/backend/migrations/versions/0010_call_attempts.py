"""persist outbound recovery call attempts

Revision ID: 0010_call_attempts
Revises: 0009_payment_event_backfill
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_call_attempts"
down_revision: Union[str, None] = "0009_payment_event_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_call_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "payment_id"),
        sa.UniqueConstraint("provider", "provider_call_id"),
    )
    op.create_index("ix_call_attempts_merchant_id", "call_attempts", ["merchant_id"])
    op.create_index("ix_call_attempts_payment_id", "call_attempts", ["payment_id"])
    op.create_index("ix_call_attempts_status", "call_attempts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_call_attempts_status", table_name="call_attempts")
    op.drop_index("ix_call_attempts_payment_id", table_name="call_attempts")
    op.drop_index("ix_call_attempts_merchant_id", table_name="call_attempts")
    op.drop_table("call_attempts")
