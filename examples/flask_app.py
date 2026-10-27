"""A shop on Flask taking crypto with SpotEx Pay.

    pip install flask git+https://github.com/SpotEx-trade/spotex-pay-python
    SPOTEX_KEY=sk_test_... SPOTEX_WEBHOOK_SECRET=whsec_... flask --app flask_app run

Use a test key (Merchant Center -> Developers) while you build: checkouts look
exactly like live ones and no money moves.
"""
import os

from flask import Flask, abort, redirect, request

from spotex_pay import SignatureVerificationError, SpotExPay, construct_event

spotex = SpotExPay(os.environ["SPOTEX_KEY"])
app = Flask(__name__)


@app.post("/orders/<order_id>/pay")
def pay(order_id):
    order = {"id": order_id, "total": "25.00", "name": "Gift box"}  # from your database
    session = spotex.checkout_sessions.create(
        amount_usd=order["total"],
        item=order["name"],
        order_id=order["id"],
        return_url=f"https://yourshop.com/orders/{order['id']}/thanks",
        idempotency_key=f"order-{order['id']}",  # same key, same session: retries are safe
    )
    return redirect(session["url"], code=303)


@app.post("/webhooks/spotex")
def webhook():
    try:
        event = construct_event(request.get_data(), request.headers.get("SpotEx-Signature"), os.environ["SPOTEX_WEBHOOK_SECRET"])
    except SignatureVerificationError:
        abort(400)
    if event["type"] == "checkout.paid" and event.get("livemode"):
        checkout = event["data"]["checkout"]
        mark_order_paid(checkout["order_id"], event["id"])  # once per event id: an event may arrive twice
    return "", 200


def mark_order_paid(order_id, event_id):
    print(f"order {order_id} paid (event {event_id})")
