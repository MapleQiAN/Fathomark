"""HMAC-signed webhook notifications with replay protection.

Signing scheme (design doc §15): the sender computes
``HMAC-SHA256(secret, f"{timestamp}.".encode() + body)`` and transmits the hex
digest in ``X-Fathomark-Signature`` together with ``X-Fathomark-Timestamp``.
Receivers recompute the signature over the raw body and reject when the
timestamp is older/newer than the tolerance window (default 300s), which
prevents replay of captured deliveries.
"""

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger("fathomark_api.webhooks")

SIGNATURE_HEADER = "X-Fathomark-Signature"
TIMESTAMP_HEADER = "X-Fathomark-Timestamp"
DEFAULT_TOLERANCE = 300


def sign(secret: bytes, timestamp: int, body: bytes) -> str:
    """HMAC-SHA256 hex digest over ``f"{timestamp}.".encode() + body``."""
    return hmac.new(
        secret, f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()


def verify(
    secret: bytes,
    signature: str,
    timestamp: int,
    body: bytes,
    *,
    now: int | None = None,
    tolerance: int = DEFAULT_TOLERANCE,
) -> bool:
    """Constant-time signature check with replay-window enforcement."""
    if now is None:
        now = int(time.time())
    if abs(now - timestamp) > tolerance:
        return False
    expected = sign(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)


class WebhookEvent(BaseModel):
    event: Literal["needs_review", "approved", "failed"]
    run_id: str
    occurred_at: int
    payload: dict


def canonical_body(event: WebhookEvent) -> bytes:
    """Deterministic JSON encoding shared by signer and receiver."""
    return json.dumps(
        event.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


Sender = Callable[[str, dict, bytes], None]


def httpx_sender(url: str, headers: dict, body: bytes) -> None:
    """Default sender: synchronous POST via httpx."""
    import httpx

    httpx.post(url, headers=headers, content=body, timeout=10.0)


class WebhookDispatcher:
    def __init__(self, url: str, secret: str, sender: Sender = httpx_sender):
        self.url = url
        self.secret = secret.encode()
        self.sender = sender

    def dispatch(self, event: WebhookEvent) -> None:
        body = canonical_body(event)
        timestamp = int(time.time())
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(self.secret, timestamp, body),
            TIMESTAMP_HEADER: str(timestamp),
        }
        self.sender(self.url, headers, body)


def notify(dispatcher: WebhookDispatcher | None, event: WebhookEvent) -> None:
    """Fire a webhook; delivery failures must never break the mutation."""
    if dispatcher is None:
        return
    try:
        dispatcher.dispatch(event)
    except Exception:
        logger.exception(
            "webhook delivery failed for event %s run %s", event.event, event.run_id
        )
