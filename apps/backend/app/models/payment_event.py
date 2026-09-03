from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.provider_connection import ProviderConnection


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    provider_connection_id: Mapped[str] = mapped_column(
        ForeignKey("provider_connections.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    provider_event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100))
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    customer_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
