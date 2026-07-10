# Hand-written overlay — NOT generated. Protected by .fernignore.
#
# Webhook signature verification (Stripe constructEvent pattern), matched to
# the a11yfy contract (API-CONTRACT.md §5.3):
#   header:  X-A11yfy-Signature: ts=<unix_seconds>;h1=<hex_hmac>
#   signed:  "{ts}:{raw_request_body}"        <-- COLON separator!
#   algo:    HMAC-SHA256, hex, constant-time compare, 300s replay window

from __future__ import annotations

import hashlib
import hmac
import json
import time
import typing

__all__ = ["Webhook", "WebhookEvent", "WebhookVerificationError"]

#: Replay-protection window in seconds (contract §5.3).
DEFAULT_TOLERANCE = 300


class WebhookVerificationError(Exception):
    """The webhook signature could not be verified."""


class WebhookEvent:
    """Verified webhook payload (terminal job notification).

    Attributes mirror the contract payload (§5.2): job_id, status
    ('done' | 'failed' | 'partial'), credits_used, output_url (on success),
    error (on failure), completed_at.
    """

    def __init__(self, data: typing.Dict[str, typing.Any]) -> None:
        self._data = data
        self.job_id: str = data.get("job_id", "")
        self.status: str = data.get("status", "")
        self.credits_used: typing.Optional[int] = data.get("credits_used")
        self.output_url: typing.Optional[str] = data.get("output_url")
        self.error: typing.Optional[str] = data.get("error")
        self.completed_at: typing.Optional[str] = data.get("completed_at")

    @property
    def is_success(self) -> bool:
        return self.status == "done"

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        return dict(self._data)

    def __repr__(self) -> str:  # pragma: no cover
        return f"WebhookEvent(job_id={self.job_id!r}, status={self.status!r})"


def _parse_header(header: str) -> typing.Tuple[int, str]:
    ts: typing.Optional[str] = None
    h1: typing.Optional[str] = None
    for part in header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == "ts":
            ts = value
        elif key == "h1":
            h1 = value
    if ts is None or h1 is None or not ts.isdigit() or not h1:
        raise WebhookVerificationError(
            "Unable to extract ts and h1 from the X-A11yfy-Signature header."
        )
    return int(ts), h1


class Webhook:
    """Verify and parse a11yfy webhook deliveries.

    Usage (e.g. in a Flask/FastAPI handler):
        event = Webhook.construct_event(
            payload=request.body,                              # RAW bytes!
            signature_header=request.headers["X-A11yfy-Signature"],
            secret=os.environ["A11YFY_WEBHOOK_SECRET"],
        )
        if event.is_success:
            download(event.output_url)
    """

    @staticmethod
    def construct_event(
        payload: typing.Union[bytes, str],
        signature_header: str,
        secret: str,
        tolerance: int = DEFAULT_TOLERANCE,
    ) -> WebhookEvent:
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        ts, h1 = _parse_header(signature_header)

        if tolerance and abs(time.time() - ts) > tolerance:
            raise WebhookVerificationError(
                f"Timestamp outside the {tolerance}s tolerance zone."
            )

        signed_payload = str(ts).encode("ascii") + b":" + raw
        expected = hmac.new(
            secret.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, h1):
            raise WebhookVerificationError(
                "Signature mismatch — payload was not signed with this secret."
            )

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebhookVerificationError("Payload is not valid JSON.") from exc
        return WebhookEvent(data)
