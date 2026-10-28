import json
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from .errors import SpotExPayError

DEFAULT_BASE_URL = "https://spotex.trade/api/merchant/v1"
_VERSION = "0.2.0"


class SpotExPay:
    """The SpotEx Pay merchant API. Resources come back as plain dicts, with
    amounts as decimal strings (use decimal.Decimal, never float, to add them).

        spotex = SpotExPay("sk_test_...")
        session = spotex.checkout_sessions.create(price="25.00", currency="EUR", item="Gift box",
                                                  idempotency_key="order-1043")
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        if not isinstance(api_key, str) or not (api_key.startswith("sk_live_") or api_key.startswith("sk_test_")):
            raise ValueError("SpotExPay: pass your secret key, sk_live_... or sk_test_....")
        self._key = api_key
        self.test_mode = api_key.startswith("sk_test_")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.checkout_sessions = _CheckoutSessions(self)
        self.checkouts = _Checkouts(self)
        self.invoices = _Invoices(self)
        self.coins = _Coins(self)
        self.balance = _Balance(self)
        self.payouts = _Payouts(self)

    # ------------------------------------------------------------------ http

    def _get(self, path: str, query: Optional[Dict[str, Any]] = None) -> Any:
        params = {k: v for k, v in (query or {}).items() if v is not None}
        if params:
            path = f"{path}?{urllib.parse.urlencode(params)}"
        return self._request("GET", path)

    def _post(self, path: str, body: Dict[str, Any], idempotency_key: Optional[str] = None) -> Any:
        body = {k: v for k, v in body.items() if v is not None}
        return self._request("POST", path, body, idempotency_key or f"py-{uuid.uuid4()}")

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, idempotency_key: Optional[str] = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
            "User-Agent": f"spotex-pay-python/{_VERSION}",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return _json(response.read(), response.status)
        except urllib.error.HTTPError as error:
            payload = None
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                pass
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            raise SpotExPayError(error.code, err.get("code", "http_error"), err.get("message", f"HTTP {error.code}")) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as error:
            reason = getattr(error, "reason", error)
            raise SpotExPayError(0, "network_error", f"Could not reach SpotEx Pay: {reason}. Retry with the same idempotency key.") from None


def _json(raw: bytes, status: int) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SpotExPayError(status, "invalid_response", "SpotEx Pay answered with something that is not JSON.") from None


def _q(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


class _CheckoutSessions:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def create(self, amount_usd: Optional[str] = None, item: Optional[str] = None, order_id: Optional[str] = None,
               return_url: Optional[str] = None, expires_in_minutes: Optional[int] = None, idempotency_key: Optional[str] = None,
               *, price: Optional[str] = None, currency: Optional[str] = None) -> Dict[str, Any]:
        """One order paid on SpotEx's own page: send the buyer to the session's ``url``.

        Price it with ``price`` and ``currency`` ("EUR", "JPY"...), or ``amount_usd`` for dollars.
        """
        body = {"price": price, "currency": currency, "amount_usd": amount_usd, "item": item, "order_id": order_id,
                "return_url": return_url, "expires_in_minutes": expires_in_minutes}
        return self._c._post("/checkout-sessions", body, idempotency_key)

    def retrieve(self, session_id: str) -> Dict[str, Any]:
        return self._c._get(f"/checkout-sessions/{_q(session_id)}")


class _Checkouts:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def create(self, amount_usd: Optional[str] = None, coin: Optional[str] = None, item: Optional[str] = None,
               order_id: Optional[str] = None, idempotency_key: Optional[str] = None,
               *, price: Optional[str] = None, currency: Optional[str] = None) -> Dict[str, Any]:
        """An on-chain checkout with its own address and exact amount, to show in your own design.

        Price it with ``price`` and ``currency``, or ``amount_usd`` for dollars.
        """
        body = {"price": price, "currency": currency, "amount_usd": amount_usd, "coin": coin, "item": item, "order_id": order_id}
        return self._c._post("/checkouts", body, idempotency_key)

    def retrieve(self, checkout_id: str) -> Dict[str, Any]:
        return self._c._get(f"/checkouts/{_q(checkout_id)}")

    def list(self, status: Optional[str] = None, limit: Optional[int] = None, before: Optional[str] = None) -> Dict[str, Any]:
        return self._c._get("/checkouts", {"status": status, "limit": limit, "before": before})

    def simulate(self, checkout_id: str, outcome: str) -> Dict[str, Any]:
        """Test mode only: "paid", "partial" or "expired"."""
        return self._c._post(f"/checkouts/{_q(checkout_id)}/simulate", {"outcome": outcome})


class _Invoices:
    """Live keys only."""

    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def create(self, currency: str, items: List[Dict[str, Any]], title: Optional[str] = None, customer_name: Optional[str] = None,
               customer_email: Optional[str] = None, memo: Optional[str] = None, due_date: Optional[str] = None,
               idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """An invoice with a page of its own: send your customer its ``url``.

        ``items`` is 1 to 50 of ``{"description", "quantity" (default "1"), "unit_price"}``;
        ``due_date`` is YYYY-MM-DD.
        """
        body = {"currency": currency, "items": items, "title": title, "customer_name": customer_name,
                "customer_email": customer_email, "memo": memo, "due_date": due_date}
        return self._c._post("/invoices", body, idempotency_key)

    def retrieve(self, invoice_id: str) -> Dict[str, Any]:
        return self._c._get(f"/invoices/{_q(invoice_id)}")

    def list(self, limit: Optional[int] = None, before: Optional[str] = None) -> Dict[str, Any]:
        return self._c._get("/invoices", {"limit": limit, "before": before})

    def void(self, invoice_id: str) -> Dict[str, Any]:
        """Cancel an unpaid invoice: its page stops taking payments."""
        return self._c._post(f"/invoices/{_q(invoice_id)}/void", {})


class _Coins:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def list(self) -> Dict[str, Any]:
        return self._c._get("/coins")


class _Balance:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def retrieve(self) -> Dict[str, Any]:
        """Live keys only."""
        return self._c._get("/balance")


class _Transfers:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def create(self, to: str, coin: str, amount: str, note: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Pay a SpotEx user (username or email) from the merchant wallet. Pass your own idempotency_key."""
        return self._c._post("/payouts/transfers", {"to": to, "coin": coin, "amount": amount, "note": note}, idempotency_key)

    def retrieve(self, transfer_id: str) -> Dict[str, Any]:
        return self._c._get(f"/payouts/transfers/{_q(transfer_id)}")


class _Withdrawals:
    def __init__(self, client: SpotExPay) -> None:
        self._c = client

    def create(self, coin: str, amount: str, address: str, memo: Optional[str] = None, network: Optional[str] = None,
               idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Send from the merchant wallet on-chain. Pass your own idempotency_key."""
        body = {"coin": coin, "amount": amount, "address": address, "memo": memo, "network": network}
        return self._c._post("/payouts/withdrawals", body, idempotency_key)

    def retrieve(self, withdrawal_id: str) -> Dict[str, Any]:
        return self._c._get(f"/payouts/withdrawals/{_q(withdrawal_id)}")


class _Payouts:
    """Live keys with the transfer or withdraw permission only."""

    def __init__(self, client: SpotExPay) -> None:
        self.transfers = _Transfers(client)
        self.withdrawals = _Withdrawals(client)
