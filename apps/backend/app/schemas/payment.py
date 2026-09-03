from decimal import Decimal

from pydantic import BaseModel, Field


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Z]{3}$")


class PaymentOrderResponse(BaseModel):
    order_id: str
    status: str
    approval_url: str | None
    amount: str
    currency: str


class PaymentStatusResponse(BaseModel):
    order_id: str
    status: str
    capture_id: str | None
    amount: str
    currency: str
