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
        response = self._post_form(
            self.token_endpoint,
            {"client_secret": self.settings.stripe_platform_secret_key, "code": code, "grant_type": "authorization_code"},
        )
        return response

    def deauthorize(self, account_id: str) -> None:
        self._post_form(
            self.deauthorize_endpoint,
            {"client_id": self.settings.stripe_client_id, "stripe_user_id": account_id},
        )

    def list_products(self, account_id: str):
        import stripe

        products = stripe.Product.list(**self._account_options(account_id), active=True, expand=["data.default_price"])
        return [self._normalize(product) for product in products.data]

    def list_prices(self, account_id: str):
        import stripe

        prices = stripe.Price.list(**self._account_options(account_id), active=True, type="one_time", limit=100)
        return [self._normalize(price) for price in prices.data]

    def get_price(self, account_id: str, price_id: str):
        import stripe

        return self._normalize(stripe.Price.retrieve(price_id, **self._account_options(account_id), expand=["product"]))

    def create_payment_intent(self, account_id: str, amount: int, currency: str, metadata, idempotency_key: str):
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
        import stripe

        return self._normalize(stripe.PaymentLink.create(
            **self._account_options(account_id),
            line_items=[{"price": price_id, "quantity": quantity}],
            metadata=dict(metadata),
            payment_intent_data={"metadata": dict(metadata)},
            idempotency_key=idempotency_key,
        ))

    def _account_options(self, account_id: str) -> dict[str, str]:
        return {"api_key": self.settings.stripe_platform_secret_key, "stripe_account": account_id}

    @staticmethod
    def _normalize(value):
        if hasattr(value, "to_dict_recursive"):
            return value.to_dict_recursive()
        return value

    def _post_form(self, url: str, fields: Mapping[str, str]) -> Mapping[str, object]:
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
