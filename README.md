# SpotEx Pay for Python

[![tests](https://github.com/SpotEx-trade/spotex-pay-python/actions/workflows/tests.yml/badge.svg)](https://github.com/SpotEx-trade/spotex-pay-python/actions/workflows/tests.yml)

Accept crypto on your website with [SpotEx Pay](https://spotex.trade/merchants): a hosted checkout or your own, signed webhooks, payouts, and a test mode to build against. Standard library only; Python 3.8+.

- **0.5% per payment**, no setup or monthly fee
- Buyers pay from any wallet or their SpotEx balance
- Amounts are decimal strings: add them with `decimal.Decimal`, never `float`

API reference: **https://spotex.trade/docs/merchant**

## Install

```sh
pip install git+https://github.com/SpotEx-trade/spotex-pay-python
```

## Get a key

Apply as a merchant at [spotex.trade/merchant](https://spotex.trade/merchant). Once approved, make keys under **Merchant Center → Developers**:

- `sk_test_…`: **test mode**. Checkouts and sessions work exactly as live and webhooks are sent, but no money moves. Start here.
- `sk_live_…`: real payments. Payout permissions are separate, and need an IP allowlist.

Keep keys on your server, in an environment variable, never in code you share.

## Take a payment on SpotEx's page

```python
import os
from spotex_pay import SpotExPay

spotex = SpotExPay(os.environ["SPOTEX_KEY"])

session = spotex.checkout_sessions.create(
    price="25.00",
    currency="EUR",  # or USD, GBP, JPY... any of https://spotex.trade/docs/merchant#currencies
    item="Gift box",
    order_id="1043",
    return_url="https://yourshop.com/thanks",  # must be on your merchant website
    idempotency_key="order-1043",              # same key, same session: retries are safe
)
# redirect the buyer to session["url"]
```

Your price becomes dollars at the exchange rate when the buyer opens the checkout. `amount_usd="25.00"` in place of `price` and `currency` still works, for a price in dollars.

## Or in your own design

```python
checkout = spotex.checkouts.create(price="25.00", currency="EUR", coin="DOGE", item="Gift box", order_id="1043")
# show checkout["address"] and checkout["amount"], then wait for the webhook
# or poll spotex.checkouts.retrieve(checkout["id"])
```

`spotex.coins.list()` says which coins you accept and which can be sent from any wallet (`"onchain": True`).

## Webhooks

Check the signature against the **raw** body before trusting anything in it:

```python
from spotex_pay import SignatureVerificationError, construct_event

try:
    event = construct_event(raw_body, headers["SpotEx-Signature"], os.environ["SPOTEX_WEBHOOK_SECRET"])
except SignatureVerificationError:
    return 400

if event["type"] == "checkout.paid" and event.get("livemode"):
    mark_order_paid(event["data"]["checkout"]["order_id"])  # once per event["id"]
```

Events older than five minutes are refused. Events: `checkout.paid`, `checkout.partial`, `checkout.extra`, `checkout.refunded`, `payout.withdrawal.*`, `payout.transfer.*`, `test`.

## Test mode

```python
checkout = spotex.checkouts.create(amount_usd="10.00", coin="DOGE", item="Test")
spotex.checkouts.simulate(checkout["id"], "partial")  # or "paid", "expired"
```

Or open its `hosted_url` and press a button. Test objects and their webhooks carry `livemode: false`.

## Payouts

From your merchant wallet, with a live key that has the permission. Always pass your own idempotency key, and retry with the same one:

```python
spotex.payouts.transfers.create(to="alice", coin="USDT", amount="15.00", note="Refund 1043", idempotency_key="refund-1043")
spotex.payouts.withdrawals.create(coin="DOGE", amount="500", address="D...", idempotency_key="payout-77")
spotex.balance.retrieve()
```

## Errors

Anything other than 2xx raises `SpotExPayError` with `status`, `code` and `message`. A network failure or timeout is `code == "network_error"`: retry with the same idempotency key.

## Examples

- [`examples/flask_app.py`](examples/flask_app.py): a Flask shop with a checkout session and a webhook
- [`examples/fastapi_app.py`](examples/fastapi_app.py): the same with FastAPI
- [`examples/test_mode.py`](examples/test_mode.py): the whole flow in test mode, from the command line

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests
```

## License

MIT
