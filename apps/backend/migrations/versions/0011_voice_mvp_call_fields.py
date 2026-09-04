"""voice-mvp call context fields on call_attempts

Revision ID: 0011_voice_mvp_call_fields
Revises: 0010_call_attempts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_voice_mvp_call_fields"
down_revision: Union[str, None] = "0010_call_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("call_attempts", sa.Column("elevenlabs_conversation_id", sa.String(length=255), nullable=True))
    op.add_column("call_attempts", sa.Column("customer_phone", sa.String(length=32), nullable=True))
    op.add_column("call_attempts", sa.Column("outcome", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("call_attempts", "outcome")
    op.drop_column("call_attempts", "customer_phone")
    op.drop_column("call_attempts", "elevenlabs_conversation_id")
