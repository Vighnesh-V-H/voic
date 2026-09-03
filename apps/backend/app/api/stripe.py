from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from collections.abc import Mapping

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.oauth_state import OAuthState
from app.models.payment import Payment
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.services.providers.base import PaymentProvider
from app.services.providers.stripe import StripeProvider

router = APIRouter(prefix="/stripe", tags=["stripe"])
payment_router = APIRouter(tags=["payments"])


class StripeConnectionResponse(BaseModel):
    provider: str
    connected: bool
    provider_account_id: str | None = None
    scope: str | None = None
    mode: str | None = None
    status: str


class StripePriceResponse(BaseModel):
    id: str
    product_id: str | None
    unit_amount: int | None
    currency: str | None
    active: bool | None
    type: str | None


def get_payment_provider(settings: Settings = Depends(get_settings)) -> PaymentProvider:
    return StripeProvider(settings)


def connection_response(connection: ProviderConnection | None) -> StripeConnectionResponse:
    if connection is None:
        return StripeConnectionResponse(provider="stripe", connected=False, status="disconnected")
    return StripeConnectionResponse(
        provider=connection.provider,
        connected=connection.status == "connected",
        provider_account_id=connection.provider_account_id,
        scope=connection.scope,
        mode=connection.mode,
        status=connection.status,
    )


def state_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def create_oauth_state(db: Session, user: User, settings: Settings) -> str:
    raw_state = token_urlsafe(32)
    db.add(
        OAuthState(
            state_hash=state_digest(raw_state),
            user_id=user.id,
            merchant_id=user.merchant_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    return raw_state


def consume_oauth_state(db: Session, raw_state: str, user: User) -> None:
    now = datetime.now(UTC)
    consumed = db.execute(
        update(OAuthState)
        .where(
            OAuthState.state_hash == state_digest(raw_state),
            OAuthState.user_id == user.id,
            OAuthState.merchant_id == user.merchant_id,
            OAuthState.used_at.is_(None),
            OAuthState.expires_at > now,
        )
        .values(used_at=now)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAUTH_STATE_MISMATCH")
    db.commit()


def redirect_to_frontend(settings: Settings, result: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.frontend_url}/settings/integrations?stripe={result}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/connect")
def connect(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> RedirectResponse:
    state = create_oauth_state(db, user, settings)
    return RedirectResponse(provider.authorization_url(state), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback")
def callback(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> RedirectResponse:
    error = request.query_params.get("error")
    raw_state = request.query_params.get("state")
    if not raw_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAUTH_STATE_MISMATCH")
    consume_oauth_state(db, raw_state, user)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAUTH_ACCESS_DENIED")

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAUTH_TOKEN_EXCHANGE_FAILED")
    try:
        result = provider.exchange_oauth_code(code)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="OAUTH_TOKEN_EXCHANGE_FAILED"
        ) from error

    account_id = result.get("stripe_user_id")
    if not isinstance(account_id, str) or not account_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAUTH_PROVIDER_ERROR")
    livemode = result.get("livemode") is True or result.get("livemode") == "true"
    if ("live" if livemode else "test") != settings.stripe_mode:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="STRIPE_MODE_MISMATCH")
    scope = result.get("scope")
    other_connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.provider == "stripe",
            ProviderConnection.provider_account_id == account_id,
            ProviderConnection.merchant_id != user.merchant_id,
        )
    )
    if other_connection is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="STRIPE_ACCOUNT_ALREADY_CONNECTED")
    current_connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.status == "connected",
            ProviderConnection.provider_account_id != account_id,
        )
    )
    if current_connection is not None:
        current_connection.status = "disconnected"
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.provider_account_id == account_id,
        )
    )
    if connection is None:
        connection = ProviderConnection(
            merchant_id=user.merchant_id,
            provider="stripe",
            provider_account_id=account_id,
            mode="live" if livemode else "test",
            scope=scope if isinstance(scope, str) else settings.stripe_oauth_scope,
            status="connected",
        )
        db.add(connection)
    else:
        connection.mode = "live" if livemode else "test"
        connection.scope = scope if isinstance(scope, str) else settings.stripe_oauth_scope
        connection.status = "connected"
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="STRIPE_ACCOUNT_ALREADY_CONNECTED") from error
    return redirect_to_frontend(settings, "connected")


@router.get("/connection", response_model=StripeConnectionResponse)
def get_connection(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StripeConnectionResponse:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.status == "connected",
        )
    )
    if connection is None:
        connection = db.scalar(
            select(ProviderConnection)
            .where(
                ProviderConnection.merchant_id == user.merchant_id,
                ProviderConnection.provider == "stripe",
            )
            .order_by(ProviderConnection.updated_at.desc())
        )
    return connection_response(connection)


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> None:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
        )
    )
    if connection is None or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe connection not found")
    try:
        provider.deauthorize(connection.provider_account_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAUTH_PROVIDER_ERROR") from error
    connection.status = "disconnected"
    db.commit()


def active_connection(db: Session, merchant_id: str) -> ProviderConnection:
    connection = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.status == "connected",
        )
    )
    if connection is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stripe connection required")
    return connection


def provider_value(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def product_response(product: Mapping[str, object]) -> dict[str, object]:
    default_price = provider_value(product, "default_price")
    if isinstance(default_price, Mapping):
        default_price = default_price.get("id")
    elif default_price is not None:
        default_price = getattr(default_price, "id", default_price)
    return {
        "id": provider_value(product, "id"),
        "name": provider_value(product, "name"),
        "description": provider_value(product, "description"),
        "active": provider_value(product, "active"),
        "default_price": default_price,
    }


@router.get("/products")
def list_products(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> list[dict[str, object]]:
    connection = active_connection(db, user.merchant_id)
    try:
        products = provider.list_products(connection.provider_account_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR") from error
    return [product_response(product) for product in products]


@router.get("/products/{product_id}")
def get_product(
    product_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> dict[str, object]:
    connection = active_connection(db, user.merchant_id)
    try:
        products = provider.list_products(connection.provider_account_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR") from error
    product = next((item for item in products if provider_value(item, "id") == product_id), None)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe product not found")
    return product_response(product)


@router.get("/prices", response_model=list[StripePriceResponse])
def list_prices(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> list[StripePriceResponse]:
    connection = active_connection(db, user.merchant_id)
    try:
        prices = provider.list_prices(connection.provider_account_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR") from error
    result = []
    for price in prices:
        price_id = provider_value(price, "id")
        if not isinstance(price_id, str):
            continue
        product = provider_value(price, "product")
        product_id = provider_value(product, "id") if isinstance(product, Mapping) else product
        result.append(
            StripePriceResponse(
                id=price_id,
                product_id=product_id if isinstance(product_id, str) else None,
                unit_amount=provider_value(price, "unit_amount")
                if isinstance(provider_value(price, "unit_amount"), int)
                else None,
                currency=provider_value(price, "currency")
                if isinstance(provider_value(price, "currency"), str)
                else None,
                active=provider_value(price, "active") if isinstance(provider_value(price, "active"), bool) else None,
                type=provider_value(price, "type") if isinstance(provider_value(price, "type"), str) else None,
            )
        )
    return result


class PaymentRequest(BaseModel):
    price_id: str
    quantity: int = 1


class PaymentResponse(BaseModel):
    id: str
    provider_payment_id: str | None = None
    provider_payment_link_id: str | None = None
    provider_price_id: str
    amount: int
    currency: str
    status: str
    client_secret: str | None = None
    url: str | None = None


def payment_response(payment: Payment, client_secret: str | None = None, url: str | None = None) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        provider_payment_id=payment.provider_payment_id,
        provider_payment_link_id=payment.provider_payment_link_id,
        provider_price_id=payment.provider_price_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        client_secret=client_secret,
        url=url if url is not None else payment.provider_payment_link_url,
    )


def price_details(provider: PaymentProvider, account_id: str, price_id: str) -> tuple[int, str]:
    try:
        price = provider.get_price(account_id, price_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe price not found") from error
    price_type = provider_value(price, "type")
    amount = provider_value(price, "unit_amount")
    currency = provider_value(price, "currency")
    if price_type != "one_time" or not isinstance(amount, int) or not isinstance(currency, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Price is not eligible for a payment")
    return amount, currency


@payment_router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> PaymentResponse:
    if payload.quantity < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantity must be positive")
    if idempotency_key is not None:
        existing = db.scalar(
            select(Payment).where(
                Payment.merchant_id == user.merchant_id,
                Payment.idempotency_key == idempotency_key,
                Payment.provider_payment_link_id.is_(None),
            )
        )
        if existing is not None:
            return payment_response(existing)
    connection = active_connection(db, user.merchant_id)
    amount, currency = price_details(provider, connection.provider_account_id, payload.price_id)
    payment = Payment(
        merchant_id=user.merchant_id,
        provider_connection_id=connection.id,
        provider="stripe",
        provider_account_id=connection.provider_account_id,
        idempotency_key=idempotency_key,
        provider_price_id=payload.price_id,
        amount=amount * payload.quantity,
        currency=currency,
        status="PENDING",
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if idempotency_key is not None:
            existing = db.scalar(
                select(Payment).where(
                    Payment.merchant_id == user.merchant_id,
                    Payment.idempotency_key == idempotency_key,
                    Payment.provider_payment_link_id.is_(None),
                )
            )
            if existing is not None:
                return payment_response(existing)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PAYMENT_ALREADY_EXISTS") from error
    metadata = {"voic_payment_id": payment.id}
    try:
        provider_payment = provider.create_payment_intent(
            connection.provider_account_id,
            payment.amount,
            payment.currency,
            metadata,
            payment.idempotency_key or payment.id,
        )
    except Exception as error:
        payment.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR") from error
    provider_payment_id = provider_value(provider_payment, "id")
    client_secret = provider_value(provider_payment, "client_secret")
    if not isinstance(provider_payment_id, str):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR")
    payment.provider_payment_id = provider_payment_id
    db.commit()
    return payment_response(payment, client_secret if isinstance(client_secret, str) else None)


@payment_router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    payment = db.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.merchant_id == user.merchant_id)
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment_response(payment)


@payment_router.post("/payment-links", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment_link(
    payload: PaymentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> PaymentResponse:
    if payload.quantity < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantity must be positive")
    connection = active_connection(db, user.merchant_id)
    if idempotency_key is not None:
        existing = db.scalar(
            select(Payment).where(
                Payment.merchant_id == user.merchant_id,
                Payment.idempotency_key == idempotency_key,
                Payment.provider_payment_link_id.is_not(None),
            )
        )
        if existing is not None:
            return payment_response(existing)
    amount, currency = price_details(provider, connection.provider_account_id, payload.price_id)
    payment = Payment(
        merchant_id=user.merchant_id,
        provider_connection_id=connection.id,
        provider="stripe",
        provider_account_id=connection.provider_account_id,
        idempotency_key=idempotency_key,
        provider_price_id=payload.price_id,
        amount=amount * payload.quantity,
        currency=currency,
        status="PENDING",
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if idempotency_key is not None:
            existing = db.scalar(
                select(Payment).where(
                    Payment.merchant_id == user.merchant_id,
                    Payment.idempotency_key == idempotency_key,
                    Payment.provider_payment_link_id.is_not(None),
                )
            )
            if existing is not None:
                return payment_response(existing)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PAYMENT_ALREADY_EXISTS") from error
    metadata = {"voic_payment_id": payment.id}
    try:
        provider_link = provider.create_payment_link(
            connection.provider_account_id,
            payload.price_id,
            payload.quantity,
            metadata,
            payment.idempotency_key or payment.id,
        )
    except Exception as error:
        payment.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR") from error
    provider_link_id = provider_value(provider_link, "id")
    url = provider_value(provider_link, "url")
    if not isinstance(provider_link_id, str) or not isinstance(url, str):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STRIPE_PROVIDER_ERROR")
    payment.provider_payment_link_id = provider_link_id
    payment.provider_payment_link_url = url
    db.commit()
    return payment_response(payment, url=url)


@payment_router.get("/payment-links/{payment_id}", response_model=PaymentResponse)
def get_payment_link(
    payment_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    payment = db.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.merchant_id == user.merchant_id)
    )
    if payment is None or payment.provider_payment_link_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment Link not found")
    return payment_response(payment)


@payment_router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PaymentResponse]:
    payments = db.scalars(
        select(Payment)
        .where(Payment.merchant_id == user.merchant_id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    ).all()
    return [payment_response(payment) for payment in payments]
