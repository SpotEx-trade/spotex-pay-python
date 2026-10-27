class SpotExPayError(Exception):
    """An API answer other than 2xx: ``code`` to branch on, ``message`` to log.

    A network failure or timeout has ``status`` 0 and ``code`` "network_error":
    retry with the same idempotency key.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"SpotExPayError(status={self.status!r}, code={self.code!r}, message={self.message!r})"


class SignatureVerificationError(Exception):
    """A webhook whose signature, or age, does not check out. Answer it with 400."""
