from collections.abc import Mapping, Sequence
from typing import Protocol


class PaymentProvider(Protocol):
    def authorization_url(self, state: str) -> str: ...

    def exchange_oauth_code(self, code: str) -> Mapping[str, object]: ...

    def deauthorize(self, account_id: str) -> None: ...

    def list_products(self, account_id: str) -> Sequence[Mapping[str, object]]: ...

    def list_prices(self, account_id: str) -> Sequence[Mapping[str, object]]: ...

    def get_price(self, account_id: str, price_id: str) -> Mapping[str, object]: ...

    def get_payment_method(self, account_id: str, payment_method_id: str) -> Mapping[str, object]: ...

    def get_customer(self, account_id: str, customer_id: str) -> Mapping[str, object]: ...

    def create_payment_intent(
        self,
        account_id: str,
        amount: int,
        currency: str,
        metadata: Mapping[str, str],
        idempotency_key: str,
    ) -> Mapping[str, object]: ...

    def create_payment_link(
        self,
        account_id: str,
        price_id: str,
        quantity: int,
        metadata: Mapping[str, str],
        idempotency_key: str,
    ) -> Mapping[str, object]: ...
