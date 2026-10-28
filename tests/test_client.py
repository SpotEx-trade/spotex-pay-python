import hashlib
import hmac
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from spotex_pay import (
    SignatureVerificationError,
    SpotExPay,
    SpotExPayError,
    construct_event,
    sign_payload,
    verify_signature,
)


class MockApi:
    """A stand-in for the API that records what it was sent and answers as told."""

    def __init__(self, status=200, payload=None):
        self.seen = []
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode() if length else ""
                mock.seen.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": json.loads(body) if body else None})
                data = json.dumps(payload if payload is not None else {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = _answer
            do_POST = _answer

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/api/merchant/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ClientTest(unittest.TestCase):
    def test_refuses_anything_but_a_secret_key(self):
        with self.assertRaises(ValueError):
            SpotExPay("pk_nope")
        self.assertTrue(SpotExPay("sk_test_abc").test_mode)
        self.assertFalse(SpotExPay("sk_live_abc").test_mode)

    def test_creates_a_checkout_session(self):
        api = MockApi(201, {"id": "cs1", "object": "checkout_session", "url": "https://spotex.trade/m/cs1"})
        try:
            spotex = SpotExPay("sk_test_abc", base_url=api.base_url)
            session = spotex.checkout_sessions.create(amount_usd="25.00", item="Gift box", order_id="1043", idempotency_key="order-1043")
            self.assertEqual(session["url"], "https://spotex.trade/m/cs1")
            r = api.seen[0]
            self.assertEqual((r["method"], r["path"]), ("POST", "/api/merchant/v1/checkout-sessions"))
            self.assertEqual(r["headers"]["Authorization"], "Bearer sk_test_abc")
            self.assertEqual(r["headers"]["Idempotency-Key"], "order-1043")
            self.assertEqual(r["body"], {"amount_usd": "25.00", "item": "Gift box", "order_id": "1043"})
        finally:
            api.close()

    def test_price_in_another_currency(self):
        api = MockApi(201, {"id": "cs2", "object": "checkout_session", "price": "25.00", "currency": "EUR", "amount_usd": None})
        try:
            spotex = SpotExPay("sk_test_abc", base_url=api.base_url)
            session = spotex.checkout_sessions.create(price="25.00", currency="EUR", item="Gift box")
            self.assertEqual(session["currency"], "EUR")
            self.assertEqual(api.seen[0]["body"], {"price": "25.00", "currency": "EUR", "item": "Gift box"})
            # Positional, as in 0.1: amount first, then item.
            spotex.checkouts.create("10.00", "DOGE", "X")
            self.assertEqual(api.seen[1]["body"], {"amount_usd": "10.00", "coin": "DOGE", "item": "X"})
        finally:
            api.close()

    def test_idempotency_key_made_for_posts_only(self):
        api = MockApi(200, {"data": []})
        try:
            spotex = SpotExPay("sk_live_abc", base_url=api.base_url)
            spotex.checkouts.create(amount_usd="10", coin="DOGE", item="X")
            spotex.checkouts.list(status="paid", limit=5)
            self.assertRegex(api.seen[0]["headers"]["Idempotency-Key"], r"^py-[0-9a-f-]{36}$")
            self.assertNotIn("Idempotency-Key", api.seen[1]["headers"])
            self.assertEqual(api.seen[1]["path"], "/api/merchant/v1/checkouts?status=paid&limit=5")
        finally:
            api.close()

    def test_every_endpoint(self):
        api = MockApi(200, {})
        try:
            s = SpotExPay("sk_live_abc", base_url=api.base_url)
            s.checkout_sessions.retrieve("cs/1")
            s.checkouts.retrieve("c1")
            s.checkouts.simulate("c1", "partial")
            s.coins.list()
            s.balance.retrieve()
            s.payouts.transfers.create(to="alice", coin="USDT", amount="5")
            s.payouts.transfers.retrieve("t1")
            s.payouts.withdrawals.create(coin="DOGE", amount="100", address="D8aM")
            s.payouts.withdrawals.retrieve("w1")
            self.assertEqual(
                [f"{r['method']} {r['path'].replace('/api/merchant/v1', '')}" for r in api.seen],
                [
                    "GET /checkout-sessions/cs%2F1",
                    "GET /checkouts/c1",
                    "POST /checkouts/c1/simulate",
                    "GET /coins",
                    "GET /balance",
                    "POST /payouts/transfers",
                    "GET /payouts/transfers/t1",
                    "POST /payouts/withdrawals",
                    "GET /payouts/withdrawals/w1",
                ],
            )
            self.assertEqual(api.seen[2]["body"], {"outcome": "partial"})
        finally:
            api.close()

    def test_api_error(self):
        api = MockApi(403, {"error": {"code": "test_mode", "message": "This can't be done with a test key."}})
        try:
            with self.assertRaises(SpotExPayError) as caught:
                SpotExPay("sk_test_abc", base_url=api.base_url).balance.retrieve()
            self.assertEqual((caught.exception.status, caught.exception.code), (403, "test_mode"))
        finally:
            api.close()

    def test_network_error(self):
        with self.assertRaises(SpotExPayError) as caught:
            SpotExPay("sk_live_abc", base_url="http://127.0.0.1:1/api", timeout=2).coins.list()
        self.assertEqual(caught.exception.code, "network_error")


# The vector every SpotEx Pay SDK is tested against, signed by the server's own code.
SECRET = "whsec_test_123"
BODY = '{"id":"evt_1","type":"checkout.paid","created":1793071234,"livemode":true,"data":{"checkout":{"id":"cm1","order_id":"1043","status":"paid"}}}'
HEADER = "t=1793071234,v1=18217f112e2f8d2f3115929e1be70e8f16f429eb28d429c6221caa60f1476863"


class WebhookTest(unittest.TestCase):
    def test_shared_vector(self):
        event = construct_event(BODY, HEADER, SECRET, tolerance_seconds=0)
        self.assertEqual(event["data"]["checkout"]["order_id"], "1043")
        self.assertEqual(sign_payload(BODY, SECRET, 1793071234), HEADER)

    def test_refusals(self):
        with self.assertRaises(SignatureVerificationError):
            construct_event(BODY.replace("1043", "9999"), HEADER, SECRET, tolerance_seconds=0)
        with self.assertRaises(SignatureVerificationError):
            construct_event(BODY, HEADER, "whsec_other", tolerance_seconds=0)
        with self.assertRaisesRegex(SignatureVerificationError, "too old"):
            construct_event(BODY, HEADER, SECRET)
        with self.assertRaisesRegex(SignatureVerificationError, "form"):
            construct_event(BODY, "nonsense", SECRET, tolerance_seconds=0)
        with self.assertRaises(SignatureVerificationError):
            construct_event(BODY, "t=1793071234,v1=ü", SECRET, tolerance_seconds=0)
        fresh = sign_payload(BODY.encode(), SECRET, int(time.time()))
        self.assertTrue(verify_signature(BODY.encode(), fresh, SECRET))

    def test_no_secret(self):
        # Signed with an empty key, as an attacker could when the secret is empty.
        digest = hmac.new(b"", b"1793071234." + BODY.encode(), hashlib.sha256).hexdigest()
        forged = "t=1793071234,v1=" + digest
        with self.assertRaisesRegex(TypeError, "no webhook signing secret"):
            construct_event(BODY, forged, "", tolerance_seconds=0)
        with self.assertRaises(TypeError):
            verify_signature(BODY, forged, "", tolerance_seconds=0)
        with self.assertRaises(TypeError):
            verify_signature(BODY, forged, os.environ.get("SPOTEX_NO_SUCH_VARIABLE"), tolerance_seconds=0)
        with self.assertRaises(TypeError):
            sign_payload(BODY, "")


if __name__ == "__main__":
    unittest.main()
