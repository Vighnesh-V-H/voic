from collections.abc import Mapping

import httpx

from app.services.providers.base import OAuthToken, PaymentProvider, ProviderError


def _scopes(value: object) -> list[str]:
    if isinstance(value, str):
        return [scope for scope in value.split() if scope]
    if isinstance(value, list):
        return [scope for scope in value if isinstance(scope, str) and scope]
    return []


class RazorpayProvider(PaymentProvider):
    async def _token_request(self, payload: Mapping[str, str]) -> OAuthToken:
        try:
            async with httpx.AsyncClient(timeout=self.settings.oauth_http_timeout_seconds) as client:
                response = await client.post(self.settings.razorpay_token_url, json=payload)
        except httpx.HTTPError as error:
            raise ProviderError("Razorpay token exchange failed") from error

        if not response.is_success:
            raise ProviderError("Razorpay token exchange failed")

        try:
            body = response.json()
        except ValueError as error:
            raise ProviderError("Razorpay token exchange failed") from error
        if not isinstance(body, dict):
            raise ProviderError("Razorpay token exchange failed")

        access_token = body.get("access_token")
        refresh_token = body.get("refresh_token")
        expires_in = body.get("expires_in")
        if isinstance(expires_in, str) and expires_in.isdigit():
            expires_in = int(expires_in)
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise ProviderError("Razorpay token exchange failed")
        if not isinstance(expires_in, int) or expires_in <= 0:
            raise ProviderError("Razorpay token exchange failed")

        return OAuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            provider_account_id=body.get("razorpay_account_id"),
            scopes=_scopes(body.get("scopes", body.get("scope")))
            or [self.settings.razorpay_scope],
        )

    async def exchange_oauth_code(self, code: str) -> OAuthToken:
        return await self._token_request(
            {
                "client_id": self.settings.razorpay_client_id,
                "client_secret": self.settings.razorpay_client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.settings.razorpay_redirect_uri,
                "code": code,
                "mode": self.settings.razorpay_mode,
            }
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        return await self._token_request(
            {
                "client_id": self.settings.razorpay_client_id,
                "client_secret": self.settings.razorpay_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
