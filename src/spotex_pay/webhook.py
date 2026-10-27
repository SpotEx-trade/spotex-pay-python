import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional, Union

from .errors import SignatureVerificationError


def construct_event(
    raw_body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    tolerance_seconds: int = 300,
) -> Dict[str, Any]:
    """Check a webhook's SpotEx-Signature header against the raw request body
    (the exact bytes received, before any JSON parsing) and return the event.

    Raises SignatureVerificationError if it does not match, or if it is older
    than ``tolerance_seconds`` (a replay). Pass 0 to skip the age check.
    """
    if not signature_header:
        raise SignatureVerificationError("No SpotEx-Signature header.")
    parts: Dict[str, str] = {}
    for piece in signature_header.split(","):
        key, sep, value = piece.partition("=")
        if sep and key.strip():
            parts[key.strip()] = value.strip()
    try:
        t = int(parts.get("t", ""))
    except ValueError:
        t = None
    if t is None or not parts.get("v1"):
        raise SignatureVerificationError("The SpotEx-Signature header is not in the form t=...,v1=....")
    if tolerance_seconds > 0 and abs(time.time() - t) > tolerance_seconds:
        raise SignatureVerificationError("The webhook is too old: refuse it as a possible replay.")
    body = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), str(t).encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    # compare_digest takes ASCII strings only: anything else is no signature of ours.
    if not parts["v1"].isascii() or not hmac.compare_digest(expected, parts["v1"]):
        raise SignatureVerificationError("The signature does not match: check the signing secret, and pass the raw body.")
    return json.loads(body.decode("utf-8"))


def verify_signature(
    raw_body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """True when the signature checks out; construct_event says why when it does not."""
    try:
        construct_event(raw_body, signature_header, secret, tolerance_seconds)
        return True
    except (SignatureVerificationError, ValueError):
        return False


def sign_payload(body: Union[bytes, str], secret: str, unix: Optional[int] = None) -> str:
    """Sign a body as SpotEx does: for your own tests of a webhook handler."""
    t = int(time.time()) if unix is None else unix
    data = body if isinstance(body, bytes) else body.encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), str(t).encode("ascii") + b"." + data, hashlib.sha256).hexdigest()
    return f"t={t},v1={digest}"
