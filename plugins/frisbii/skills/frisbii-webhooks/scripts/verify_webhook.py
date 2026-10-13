"""Verify a Frisbii (Reepay) webhook signature. No dependencies.

signature = hex(HMAC_SHA256(key=webhook_secret, msg=timestamp + id))

Usage in a handler:

    payload = json.loads(request_body)
    if not verify_frisbii_webhook(payload, os.environ["FRISBII_WEBHOOK_SECRET"]):
        return 401

CLI self-test:  python3 verify_webhook.py <secret> <payload.json>
"""

import hashlib
import hmac
import json
import sys


def compute_signature(secret: str, timestamp: str, webhook_id: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        (timestamp + webhook_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_frisbii_webhook(payload: dict, secret: str) -> bool:
    timestamp = payload.get("timestamp")
    webhook_id = payload.get("id")
    signature = payload.get("signature")
    if not (isinstance(timestamp, str) and isinstance(webhook_id, str) and isinstance(signature, str)):
        return False
    expected = compute_signature(secret, timestamp, webhook_id)
    return hmac.compare_digest(expected, signature.lower())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: verify_webhook.py <secret> <payload.json>")
    with open(sys.argv[2], encoding="utf-8") as f:
        ok = verify_frisbii_webhook(json.load(f), sys.argv[1])
    print("valid" if ok else "INVALID")
    sys.exit(0 if ok else 1)
