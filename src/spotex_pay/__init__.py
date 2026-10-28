"""SpotEx Pay merchant API client.

    from spotex_pay import SpotExPay

    spotex = SpotExPay(os.environ["SPOTEX_KEY"])
    session = spotex.checkout_sessions.create(amount_usd="25.00", item="Gift box")

API reference: https://spotex.trade/docs/merchant
"""

from .client import DEFAULT_BASE_URL, SpotExPay
from .errors import SignatureVerificationError, SpotExPayError
from .webhook import construct_event, sign_payload, verify_signature

__version__ = "0.3.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "SpotExPay",
    "SpotExPayError",
    "SignatureVerificationError",
    "construct_event",
    "sign_payload",
    "verify_signature",
    "__version__",
]
