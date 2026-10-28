"""SpotEx Pay with FastAPI.

    pip install fastapi uvicorn git+https://github.com/SpotEx-trade/spotex-pay-python
    SPOTEX_KEY=sk_test_... SPOTEX_WEBHOOK_SECRET=whsec_... uvicorn fastapi_app:app
"""
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from spotex_pay import SignatureVerificationError, SpotExPay, construct_event

spotex = SpotExPay(os.environ["SPOTEX_KEY"])
app = FastAPI()


@app.post("/orders/{order_id}/pay")
def pay(order_id: str):
    session = spotex.checkout_sessions.create(
        price="25.00",
        currency="USD",
        item="Gift box",
        order_id=order_id,
        return_url=f"https://yourshop.com/orders/{order_id}/thanks",
        idempotency_key=f"order-{order_id}",
    )
    return RedirectResponse(session["url"], status_code=303)


@app.post("/webhooks/spotex")
async def webhook(request: Request):
    raw = await request.body()  # the exact bytes: parse only after the signature checks out
    try:
        event = construct_event(raw, request.headers.get("spotex-signature"), os.environ["SPOTEX_WEBHOOK_SECRET"])
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="bad signature")
    if event["type"] == "checkout.paid" and event.get("livemode"):
        print("fulfil order", event["data"]["checkout"]["order_id"])
    return {"ok": True}
