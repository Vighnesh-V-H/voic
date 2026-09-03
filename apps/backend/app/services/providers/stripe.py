import hashlib
import hmac
import json
import time
from base64 import b64encode
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from app.core.config import Settings


class StripeProviderError(Exception):
    pass


def verify_webhook_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """
    Verify the signature of a Stripe webhook payload using HMAC SHA-256.

    Args:
        payload: The raw request body bytes.
        signature_header: The Stripe-Signature header value.
        secret: The webhook signing secret.

    Returns:
        True if the signature is valid and within the 5-minute tolerance window, False otherwise.
    """
    values: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        key, separator, value = item.partition("=")
        if separator:
            values.setdefault(key, []).append(value)
    timestamps = values.get("t", [])
    signatures = values.get("v1", [])
    if len(timestamps) != 1 or not signatures or not secret:
        return False
    try:
        timestamp = int(timestamps[0])
    except ValueError:
        return False
    if abs(time.time() - timestamp) > 300:
        return False
    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


class StripeProvider:
    authorization_endpoint = "https://connect.stripe.com/oauth/authorize"
    token_endpoint = "https://connect.stripe.com/oauth/token"
    deauthorize_endpoint = "https://connect.stripe.com/oauth/deauthorize"

    def __init__(self, settings: Settings):
        self.settings = settings

    def authorization_url(self, state: str) -> str:
        """
        Generate the Stripe OAuth authorization URL with the given state.

        Args:
            state: The OAuth state token for CSRF protection.

        Returns:
            The full authorization URL for redirecting the user to Stripe.
        """
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.stripe_client_id,
                "scope": self.settings.stripe_oauth_scope,
                "redirect_uri": self.settings.stripe_oauth_redirect_uri,
                "state": state,
            }
        )
        return f"{self.authorization_endpoint}?{query}"

    def exchange_oauth_code(self, code: str) -> Mapping[str, object]:
        """
        Exchange an OAuth authorization code for access credentials.

        Args:
            code: The authorization code received from the OAuth callback.

        Returns:
            A mapping containing stripe_user_id, scope, livemode, and access tokens.

        Raises:
            StripeProviderError: If the token exchange request fails.
        """
        response = self._post_form(
            self.token_endpoint,
            {"client_secret": self.settings.stripe_platform_secret_key, "code": code, "grant_type": "authorization_code"},
        )
        return response

    def deauthorize(self, account_id: str) -> None:
        """
        Deauthorize a connected Stripe account.

        Args:
            account_id: The Stripe account ID to deauthorize.

        Raises:
            StripeProviderError: If the deauthorization request fails.
        """
        self._post_form(
            self.deauthorize_endpoint,
            {"client_id": self.settings.stripe_client_id, "stripe_user_id": account_id},
        )

    def list_products(self, account_id: str):
        """
        List all active products from a connected Stripe account.

        Args:
            account_id: The Stripe account ID to query.

        Returns:
            A list of normalized product objects with expanded default_price.
        """
        import stripe

        products = stripe.Product.list(**self._account_options(account_id), active=True, expand=["data.default_price"])
        return [self._normalize(product) for product in products.data]

    def list_prices(self, account_id: str):
        """
        List all active one-time prices from a connected Stripe account.

        Args:
            account_id: The Stripe account ID to query.

        Returns:
            A list of normalized price objects.
        """
        import stripe

        prices = stripe.Price.list(**self._account_options(account_id), active=True, type="one_time", limit=100)
        return [self._normalize(price) for price in prices.data]

    def get_price(self, account_id: str, price_id: str):
        """
        Retrieve a single price by ID from a connected Stripe account.

        Args:
            account_id: The Stripe account ID to query.
            price_id: The Stripe price ID to retrieve.

        Returns:
            A normalized price object with expanded product details.
        """
        import stripe

        return self._normalize(stripe.Price.retrieve(price_id, **self._account_options(account_id), expand=["product"]))

    def create_payment_intent(self, account_id: str, amount: int, currency: str, metadata, idempotency_key: str):
        """
        Create a PaymentIntent on a connected Stripe account.

        Args:
            account_id: The Stripe account ID to create the PaymentIntent on.
            amount: The amount in the smallest currency unit (e.g., cents).
            currency: The three-letter ISO currency code.
            metadata: Metadata to attach to the PaymentIntent.
            idempotency_key: Idempotency key for safe retries.

        Returns:
            A normalized PaymentIntent object with id and client_secret.
        """
        import stripe

        return self._normalize(stripe.PaymentIntent.create(
            **self._account_options(account_id),
            amount=amount,
            currency=currency,
            automatic_payment_methods={"enabled": True},
            metadata=dict(metadata),
            idempotency_key=idempotency_key,
        ))

    def create_payment_link(self, account_id: str, price_id: str, quantity: int, metadata, idempotency_key: str):
        """
        Create a Payment Link on a connected Stripe account.

        Args:
            account_id: The Stripe account ID to create the Payment Link on.
            price_id: The Stripe price ID to use for the line item.
            quantity: The quantity of the price.
            metadata: Metadata to attach to the Payment Link and underlying PaymentIntent.
            idempotency_key: Idempotency key for safe retries.

        Returns:
            A normalized Payment Link object with id and url.
        """
        import stripe

        return self._normalize(stripe.PaymentLink.create(
            **self._account_options(account_id),
            line_items=[{"price": price_id, "quantity": quantity}],
            metadata=dict(metadata),
            payment_intent_data={"metadata": dict(metadata)},
            idempotency_key=idempotency_key,
        ))

    def _account_options(self, account_id: str) -> dict[str, str]:
        """
        Build the Stripe API call options for a connected account.

        Args:
            account_id: The Stripe account ID to include in the request headers.

        Returns:
            A dictionary with api_key and stripe_account for use with Stripe SDK calls.
        """
        return {"api_key": self.settings.stripe_platform_secret_key, "stripe_account": account_id}

    @staticmethod
    def _normalize(value):
        """
        Convert a Stripe SDK object to a dictionary for JSON serialization.

        Args:
            value: A Stripe API response object.

        Returns:
            A dictionary representation of the object if it has to_dict_recursive, otherwise the value as-is.
        """
        if hasattr(value, "to_dict_recursive"):
            return value.to_dict_recursive()
        return value

    def _post_form(self, url: str, fields: Mapping[str, str]) -> Mapping[str, object]:
        """
        Make a form-encoded POST request to Stripe with Basic authentication.

        Args:
            url: The Stripe endpoint URL.
            fields: The form fields to encode and send in the request body.

        Returns:
            The parsed JSON response from Stripe.

        Raises:
            StripeProviderError: If the request fails or Stripe returns an error status.
        """
        credentials = b64encode(f"{self.settings.stripe_platform_secret_key}:".encode()).decode()
        request = UrlRequest(
            url,
            data=urlencode(fields).encode(),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read())
        except HTTPError as error:
            body = error.read().decode(errors="replace")
            raise StripeProviderError(f"Stripe responded {error.code}: {body}") from error
        except URLError as error:
            raise StripeProviderError(f"Stripe request failed: {error.reason}") from error
