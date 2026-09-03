from collections.abc import Mapping
from urllib.parse import urlparse

import httpx

from app.services.providers.base import OAuthToken, PaymentCapture, PaymentOrder, PaymentProvider, PaymentProviderError


def _expires_in(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def _scopes(value: object) -> list[str]:
    if isinstance(value, str):
        return [scope for scope in value.split() if scope]
    return []


class PayPalProvider(PaymentProvider):
    async def obtain_access_token(self) -> OAuthToken:
        try:
            async with httpx.AsyncClient(timeout=self.settings.paypal_http_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.paypal_api_base_url}/v1/oauth2/token",
                    auth=(self.settings.paypal_client_id, self.settings.paypal_client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as error:
            raise PaymentProviderError("PayPal authentication failed") from error

        if not response.is_success:
            raise PaymentProviderError("PayPal authentication failed")
        try:
            body = response.json()
        except ValueError as error:
            raise PaymentProviderError("PayPal authentication failed") from error
        if not isinstance(body, dict):
            raise PaymentProviderError("PayPal authentication failed")

        access_token = body.get("access_token")
        expires_in = _expires_in(body.get("expires_in"))
        if not isinstance(access_token, str) or expires_in is None:
            raise PaymentProviderError("PayPal authentication failed")
        return OAuthToken(
            access_token=access_token,
            expires_in=expires_in,
            provider_account_id=body.get("app_id") if isinstance(body.get("app_id"), str) else None,
            scopes=_scopes(body.get("scope")),
        )

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        json: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        request_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        try:
            async with httpx.AsyncClient(timeout=self.settings.paypal_http_timeout_seconds) as client:
                response = await client.request(
                    method,
                    f"{self.settings.paypal_api_base_url}{path}",
                    json=json,
                    headers=request_headers,
                )
        except httpx.HTTPError as error:
            raise PaymentProviderError("PayPal payment request failed") from error
        if not response.is_success:
            raise PaymentProviderError("PayPal payment request failed")
        try:
            body = response.json()
        except ValueError as error:
            raise PaymentProviderError("PayPal payment request failed") from error
        if not isinstance(body, dict):
            raise PaymentProviderError("PayPal payment request failed")
        return body

    async def create_payment(
        self, access_token: str, amount: str, currency: str, request_id: str
    ) -> PaymentOrder:
        body = await self._request(
            "POST",
            "/v2/checkout/orders",
            access_token,
            json={
                "intent": "CAPTURE",
                "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}],
                "application_context": {
                    "return_url": self.settings.paypal_frontend_return_url,
                    "cancel_url": self.settings.paypal_frontend_cancel_url,
                    "user_action": "PAY_NOW",
                },
            },
            headers={"PayPal-Request-Id": request_id, "Prefer": "return=representation"},
        )
        order_id = body.get("id")
        if not isinstance(order_id, str):
            raise PaymentProviderError("PayPal did not return an order identifier")
        links = body.get("links")
        approval_url = None
        if isinstance(links, list):
            for link in links:
                if (
                    isinstance(link, dict)
                    and link.get("rel") in {"approve", "payer-action"}
                    and isinstance(link.get("href"), str)
                ):
                    parsed_url = urlparse(link["href"])
                    if parsed_url.scheme == "https" and parsed_url.hostname in {
                        "sandbox.paypal.com",
                        "www.sandbox.paypal.com",
                    }:
                        approval_url = link["href"]
                        break
        return PaymentOrder(order_id=order_id, status=str(body.get("status", "CREATED")), approval_url=approval_url)

    async def capture_payment(self, access_token: str, order_id: str) -> PaymentCapture:
        body = await self._request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            access_token,
            headers={"PayPal-Request-Id": f"capture-{order_id}", "Prefer": "return=representation"},
        )
        return self._capture_from_body(body)

    async def get_payment_status(self, access_token: str, order_id: str) -> PaymentCapture:
        body = await self._request("GET", f"/v2/checkout/orders/{order_id}", access_token)
        return self._capture_from_body(body)

    @staticmethod
    def _capture_from_body(body: dict[str, object]) -> PaymentCapture:
        capture_id = None
        purchase_units = body.get("purchase_units")
        if isinstance(purchase_units, list) and purchase_units:
            first_unit = purchase_units[0]
            if isinstance(first_unit, dict):
                payments = first_unit.get("payments")
                if isinstance(payments, dict):
                    captures = payments.get("captures")
                    if isinstance(captures, list) and captures and isinstance(captures[0], dict):
                        value = captures[0].get("id")
                        capture_id = value if isinstance(value, str) else None
        return PaymentCapture(status=str(body.get("status", "UNKNOWN")), capture_id=capture_id)
