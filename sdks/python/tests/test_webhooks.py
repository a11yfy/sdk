"""Webhook-verify tesztek — a contract (§5.3) sémája ellen.

Az aláírt payload: "{ts}:{rawBody}" (KETTŐSPONT), HMAC-SHA256 hex,
header: ts=<unix>;h1=<hex>, 300 s replay-ablak.
"""

import hashlib
import hmac
import json
import time

import pytest

from a11yfy import Webhook, WebhookVerificationError

SECRET = "whsec_test_secret"


def sign(payload: bytes, ts: int, secret: str = SECRET) -> str:
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def make_payload(**overrides) -> bytes:
    data = {
        "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "done",
        "credits_used": 12,
        "output_url": "https://example.com/out.pdf",
        "completed_at": "2026-07-10T10:31:00.000Z",
    }
    data.update(overrides)
    return json.dumps(data).encode()


def test_valid_signature_roundtrip():
    payload = make_payload()
    ts = int(time.time())
    event = Webhook.construct_event(payload, sign(payload, ts), SECRET)
    assert event.is_success
    assert event.job_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert event.credits_used == 12
    assert event.output_url == "https://example.com/out.pdf"


def test_str_payload_accepted():
    payload = make_payload()
    ts = int(time.time())
    event = Webhook.construct_event(payload.decode(), sign(payload, ts), SECRET)
    assert event.status == "done"


def test_tampered_payload_rejected():
    payload = make_payload()
    ts = int(time.time())
    header = sign(payload, ts)
    tampered = make_payload(credits_used=0)
    with pytest.raises(WebhookVerificationError, match="Signature mismatch"):
        Webhook.construct_event(tampered, header, SECRET)


def test_wrong_secret_rejected():
    payload = make_payload()
    ts = int(time.time())
    with pytest.raises(WebhookVerificationError, match="Signature mismatch"):
        Webhook.construct_event(payload, sign(payload, ts), "wrong_secret")


def test_expired_timestamp_rejected():
    payload = make_payload()
    ts = int(time.time()) - 301
    with pytest.raises(WebhookVerificationError, match="tolerance"):
        Webhook.construct_event(payload, sign(payload, ts), SECRET)


def test_malformed_header_rejected():
    payload = make_payload()
    with pytest.raises(WebhookVerificationError, match="ts and h1"):
        Webhook.construct_event(payload, "nonsense", SECRET)


def test_failed_event():
    payload = make_payload(status="failed", error="diagnostic_failed", output_url=None)
    ts = int(time.time())
    event = Webhook.construct_event(payload, sign(payload, ts), SECRET)
    assert not event.is_success
    assert event.error == "diagnostic_failed"
