from datetime import UTC, datetime, timedelta
from hashlib import sha256
from logging import getLogger
from secrets import token_urlsafe
from collections.abc import Mapping

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.api.webhooks import delete_merchant_stripe_data
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.oauth_state import OAuthState
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.provider_connection import ProviderConnection
from app.models.user import User
from app.services.providers.base import PaymentProvider
from app.services.providers.stripe import StripeProvider

router = APIRouter(prefix="/stripe", tags=["stripe"])
payment_router = APIRouter(tags=["payments"])

logger = getLogger(__name__)


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
    """
    Dependency injection function that provides a PaymentProvider instance.

    Args:
        settings: Application settings containing Stripe configuration.

    Returns:
        A StripeProvider instance configured with the given settings.
    """
    return StripeProvider(settings)


def connection_response(connection: ProviderConnection | None) -> StripeConnectionResponse:
    """
    Convert a ProviderConnection model to a StripeConnectionResponse.

    Args:
        connection: The provider connection record, or None if not found.

    Returns:
        A StripeConnectionResponse with connection details or disconnected status.
    """
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
    """
    Compute a SHA-256 hash digest of the given state string.

    Args:
        value: The raw state string to hash.

    Returns:
        The hexadecimal digest of the state hash.
    """
    return sha256(value.encode("utf-8")).hexdigest()


def create_oauth_state(db: Session, user: User, settings: Settings) -> str:
    """
    Create a new OAuth state token and persist it to the database.

    Args:
        db: Database session for persisting the state.
        user: The user initiating the OAuth flow.
        settings: Application settings (currently unused).

    Returns:
        The raw state token to be included in the OAuth authorization URL.
    """
    raw_state = token_urlsafe(32)
    db.add(
        OAuthState(
            state_hash=state_digest(raw_state),
            user_id=user.id,
            merchant_id=user.merchant_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    db.commit()
    return raw_state


def consume_oauth_state(db: Session, raw_state: str, user: User) -> None:
    """
    Mark an OAuth state token as consumed if it is valid and unused.

    Args:
        db: Database session for updating the state.
        raw_state: The raw state token received from the OAuth callback.
        user: The user who initiated the OAuth flow.

    Raises:
        HTTPException: If the state is invalid, expired, already used, or not found.
    """
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
    """
    Create a redirect response to the frontend integrations page with a result parameter.

    Args:
        settings: Application settings containing the frontend URL.
        result: The OAuth result status to include in the query string.

    Returns:
        A RedirectResponse to the frontend settings/integrations page.
    """
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
    """
    Initiate Stripe OAuth connection flow by redirecting to the authorization URL.

    Args:
        user: The authenticated user initiating the connection.
        db: Database session for creating OAuth state.
        settings: Application settings.
        provider: Payment provider instance for generating the authorization URL.

    Returns:
        A redirect response to the Stripe authorization page.
    """
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
    """
    Handle Stripe OAuth callback, exchange authorization code for account details, and persist the connection.

    Args:
        request: The incoming request containing OAuth callback parameters.
        user: The authenticated user completing the OAuth flow.
        db: Database session for persisting the provider connection.
        settings: Application settings including Stripe mode and frontend URL.
        provider: Payment provider instance for exchanging the OAuth code.

    Returns:
        A redirect response to the frontend with the connection result.

    Raises:
        HTTPException: If state validation fails, token exchange fails, mode mismatches, or account conflicts exist.
    """
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
        logger.error("Stripe token exchange failed: %s", error)
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
    old_connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
            ProviderConnection.provider_account_id != account_id,
        )
    ).all()
    for old_connection in old_connections:
        db.execute(
            delete(PaymentEvent).where(
                PaymentEvent.provider_connection_id == old_connection.id,
            )
        )
        db.execute(
            delete(Payment).where(
                Payment.provider_connection_id == old_connection.id,
            )
        )
        db.delete(old_connection)
    if old_connections:
        db.flush()
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
    """
    Retrieve the current Stripe connection status for the authenticated merchant.

    Args:
        user: The authenticated user requesting connection status.
        db: Database session for querying the provider connection.

    Returns:
        The current or most recent Stripe connection status.
    """
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
    """
    Disconnect the merchant's Stripe account and remove all Voic-owned Stripe data.

    The merchant and user records are preserved so the merchant stays logged
    in; provider connections, payments, and payment events for provider
    ``stripe`` are deleted. Callers should warn that disconnecting
    permanently removes Stripe data from Voic.

    Args:
        user: The authenticated user requesting disconnection.
        db: Database session for deleting Stripe records.
        provider: Payment provider instance for calling the deauthorize endpoint.

    Raises:
        HTTPException: If no connected Stripe account is found or deauthorization fails.
    """
    connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.merchant_id == user.merchant_id,
            ProviderConnection.provider == "stripe",
        )
    ).all()
    active = [c for c in connections if c.status == "connected"]
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe connection not found")
    try:
        for connection in active:
            provider.deauthorize(connection.provider_account_id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAUTH_PROVIDER_ERROR") from error
    delete_merchant_stripe_data(db, user.merchant_id)
    db.commit()


def active_connection(db: Session, merchant_id: str) -> ProviderConnection:
    """
    Retrieve the active Stripe connection for a merchant or raise an error if not found.

    Args:
        db: Database session for querying the provider connection.
        merchant_id: The merchant's unique identifier.

    Returns:
        The active provider connection.

    Raises:
        HTTPException: If no connected Stripe account exists for the merchant.
    """
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
    """
    Extract a value from a provider response object or mapping.

    Args:
        value: A provider response object (mapping or object with attributes).
        name: The field name to extract.

    Returns:
        The extracted value, or None if not present.
    """
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def product_response(product: Mapping[str, object]) -> dict[str, object]:
    """
    Transform a Stripe product object into a simplified response dictionary.

    Args:
        product: The product object from the Stripe API.

    Returns:
        A dictionary containing product id, name, description, active status, and default_price id.
    """
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
    """
    List all active products from the connected Stripe account.

    Args:
        user: The authenticated user making the request.
        db: Database session for retrieving the active connection.
        provider: Payment provider instance for fetching products.

    Returns:
        A list of product dictionaries with id, name, description, active, and default_price fields.

    Raises:
        HTTPException: If the merchant has no active Stripe connection or the Stripe API call fails.
    """
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
    """
    Retrieve a single product by ID from the connected Stripe account.

    Args:
        product_id: The Stripe product ID to retrieve.
        user: The authenticated user making the request.
        db: Database session for retrieving the active connection.
        provider: Payment provider instance for fetching products.

    Returns:
        A product dictionary with id, name, description, active, and default_price fields.

    Raises:
        HTTPException: If the product is not found or the Stripe API call fails.
    """
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
    """
    List all active one-time prices from the connected Stripe account.

    Args:
        user: The authenticated user making the request.
        db: Database session for retrieving the active connection.
        provider: Payment provider instance for fetching prices.

    Returns:
        A list of price objects with id, product_id, unit_amount, currency, active, and type fields.

    Raises:
        HTTPException: If the merchant has no active Stripe connection or the Stripe API call fails.
    """
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
    created_at: datetime | None = None


def payment_response(payment: Payment, client_secret: str | None = None, url: str | None = None) -> PaymentResponse:
    """
    Transform a Payment model into a PaymentResponse with optional transient fields.

    Args:
        payment: The payment record from the database.
        client_secret: Optional client secret for confirming the PaymentIntent (transient, not persisted).
        url: Optional payment link URL (overrides the persisted URL if provided).

    Returns:
        A PaymentResponse with all payment details including transient fields.
    """
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
        created_at=payment.created_at,
    )


def price_details(provider: PaymentProvider, account_id: str, price_id: str) -> tuple[int, str]:
    """
    Fetch and validate a Stripe price for payment creation.

    Args:
        provider: Payment provider instance for fetching the price.
        account_id: The connected Stripe account ID.
        price_id: The Stripe price ID to retrieve.

    Returns:
        A tuple of (unit_amount, currency) for the price.

    Raises:
        HTTPException: If the price is not found, not one-time, or missing required fields.
    """
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
    """
    Create a new PaymentIntent for the given price and quantity.

    Args:
        payload: The payment request containing price_id and quantity.
        idempotency_key: Optional idempotency key for safe retries.
        user: The authenticated user creating the payment.
        db: Database session for persisting the payment record.
        provider: Payment provider instance for creating the PaymentIntent.

    Returns:
        A PaymentResponse with the payment details including the client_secret for Stripe.js.

    Raises:
        HTTPException: If quantity is invalid, connection is missing, or Stripe API call fails.
    """
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
    """
    Retrieve a single payment by ID for the authenticated merchant.

    Args:
        payment_id: The payment ID to retrieve.
        user: The authenticated user making the request.
        db: Database session for querying the payment record.

    Returns:
        A PaymentResponse with the payment details (without the client_secret).

    Raises:
        HTTPException: If the payment is not found or does not belong to the merchant.
    """
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
    """
    Create a new Stripe Payment Link for the given price and quantity.

    Args:
        payload: The payment request containing price_id and quantity.
        idempotency_key: Optional idempotency key for safe retries.
        user: The authenticated user creating the payment link.
        db: Database session for persisting the payment record.
        provider: Payment provider instance for creating the Payment Link.

    Returns:
        A PaymentResponse with the payment details including the hosted checkout URL.

    Raises:
        HTTPException: If quantity is invalid, connection is missing, or Stripe API call fails.
    """
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
    """
    Retrieve a single payment link by ID for the authenticated merchant.

    Args:
        payment_id: The payment ID to retrieve.
        user: The authenticated user making the request.
        db: Database session for querying the payment record.

    Returns:
        A PaymentResponse with the payment link details including the checkout URL.

    Raises:
        HTTPException: If the payment link is not found or does not belong to the merchant.
    """
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
    """
    List recent payments for the authenticated merchant.

    Args:
        user: The authenticated user making the request.
        db: Database session for querying payment records.

    Returns:
        A list of up to 50 most recent PaymentResponse objects, ordered by creation time descending.
    """
    payments = db.scalars(
        select(Payment)
        .where(Payment.merchant_id == user.merchant_id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    ).all()
    return [payment_response(payment) for payment in payments]
