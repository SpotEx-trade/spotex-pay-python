"""Try the whole flow in test mode, from the command line:

    SPOTEX_KEY=sk_test_... python test_mode.py
"""
import os

from spotex_pay import SpotExPay

spotex = SpotExPay(os.environ["SPOTEX_KEY"])
if not spotex.test_mode:
    raise SystemExit("Use a test key (sk_test_...) for this script.")

coin = next((c for c in spotex.coins.list()["data"] if c["onchain"]), None)
if coin is None:
    raise SystemExit("You accept no coin that can be sent from a wallet.")

checkout = spotex.checkouts.create(amount_usd="10.00", coin=coin["coin"], item="Test order", order_id="test-1")
print(f"Made {checkout['id']}: send {checkout['amount']} {checkout['coin']} to {checkout['address']} (a stand-in)")

half = spotex.checkouts.simulate(checkout["id"], "partial")
print("After half:", half["status"], "remaining", half["remaining"])

paid = spotex.checkouts.simulate(checkout["id"], "paid")
print("After the rest:", paid["status"], "- your webhook got checkout.partial and checkout.paid, livemode false")
