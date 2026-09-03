from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.api.integrations import get_paypal_provider
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.payment_transaction import PaymentTransaction
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.schemas.payment import CreatePaymentRequest, PaymentOrderResponse, PaymentStatusResponse
from app.services.providers.base import PaymentProvider, PaymentProviderError

router = APIRouter(prefix="/payments", tags=["payments"])


def _connection(db: Session, merchant_id: str) -> ProviderConnection:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == merchant_id,
            ProviderConnection.provider == "paypal",
            ProviderConnection.status == "connected",
        )
    )
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect PayPal before creating a payment",
        )
    return connection


def _transaction(
    db: Session, merchant_id: str, order_id: str, *, lock: bool = False
) -> PaymentTransaction:
    query = select(PaymentTransaction).where(
        PaymentTransaction.merchant_id == merchant_id,
        PaymentTransaction.provider == "paypal",
        PaymentTransaction.provider_order_id == order_id,
    )
    if lock:
        query = query.with_for_update()
    transaction = db.scalar(query)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return transaction


def _status_response(transaction: PaymentTransaction) -> PaymentStatusResponse:
    return PaymentStatusResponse(
        order_id=transaction.provider_order_id,
        status=transaction.status,
        capture_id=transaction.capture_id,
        amount=transaction.amount,
        currency=transaction.currency,
    )


@router.post("/paypal/orders", response_model=PaymentOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_paypal_order(
    payload: CreatePaymentRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_paypal_provider),
) -> PaymentOrderResponse:
    connection = _connection(db, user.merchant_id)
    try:
        access_token = await provider.get_valid_access_token(connection, db)
        order = await provider.create_payment(
            access_token,
            f"{payload.amount:.2f}",
            payload.currency,
            str(uuid4()),
        )
    except PaymentProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal could not create the payment",
        ) from None

    transaction = PaymentTransaction(
        merchant_id=user.merchant_id,
        provider="paypal",
        provider_order_id=order.order_id,
        amount=f"{payload.amount:.2f}",
        currency=payload.currency,
        status=order.status,
        approval_url=order.approval_url,
    )
    db.add(transaction)
    db.commit()
    return PaymentOrderResponse(
        order_id=order.order_id,
        status=order.status,
        approval_url=order.approval_url,
        amount=transaction.amount,
        currency=transaction.currency,
    )


@router.post("/paypal/orders/{order_id}/capture", response_model=PaymentStatusResponse)
async def capture_paypal_order(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_paypal_provider),
) -> PaymentStatusResponse:
    transaction = _transaction(db, user.merchant_id, order_id)
    if transaction.status == "COMPLETED":
        return _status_response(transaction)
    if transaction.status in {"CANCELLED", "FAILED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment is no longer capturable")
    connection = _connection(db, user.merchant_id)
    try:
        access_token = await provider.get_valid_access_token(connection, db)
        transaction = _transaction(db, user.merchant_id, order_id, lock=True)
        if transaction.status == "COMPLETED":
            return _status_response(transaction)
        if transaction.status in {"CANCELLED", "FAILED"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment is no longer capturable")
        capture = await provider.capture_payment(access_token, order_id)
    except PaymentProviderError:
        # A timeout can happen after PayPal captured the order. Reconcile UNKNOWN
        # orders instead of permanently reporting a potentially paid order as failed.
        transaction.status = "UNKNOWN"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal could not complete the payment",
        ) from None
    transaction.status = capture.status
    transaction.capture_id = capture.capture_id
    db.commit()
    return _status_response(transaction)


@router.post("/paypal/orders/{order_id}/cancel", response_model=PaymentStatusResponse)
def cancel_paypal_order(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PaymentStatusResponse:
    transaction = _transaction(db, user.merchant_id, order_id, lock=True)
    if transaction.status not in {"COMPLETED", "CANCELLED", "FAILED"}:
        transaction.status = "CANCELLED"
        db.commit()
    return _status_response(transaction)


@router.get("/paypal/orders/{order_id}", response_model=PaymentStatusResponse)
async def paypal_order_status(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_paypal_provider),
) -> PaymentStatusResponse:
    transaction = _transaction(db, user.merchant_id, order_id)
    if transaction.status not in {"COMPLETED", "CANCELLED", "FAILED"}:
        connection = _connection(db, user.merchant_id)
        try:
            access_token = await provider.get_valid_access_token(connection, db)
            transaction = _transaction(db, user.merchant_id, order_id, lock=True)
            if transaction.status in {"COMPLETED", "CANCELLED", "FAILED"}:
                return _status_response(transaction)
            payment_status = await provider.get_payment_status(access_token, order_id)
        except PaymentProviderError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal status could not be loaded",
            ) from None
        transaction.status = payment_status.status
        transaction.capture_id = payment_status.capture_id
        db.commit()
    return _status_response(transaction)
