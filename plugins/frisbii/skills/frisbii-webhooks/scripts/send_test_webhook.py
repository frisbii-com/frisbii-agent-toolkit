"""Send a correctly signed fake Frisbii webhook to a local endpoint. No dependencies.

    python3 send_test_webhook.py --url http://localhost:3000/webhooks/frisbii \
        --secret "$FRISBII_WEBHOOK_SECRET" --event invoice_settled \
        --invoice order-1001 --customer cust-42 [--subscription sub-42] [--bad-signature]

Use only against your own development endpoints. The event is synthetic: the
referenced objects do not exist in Frisbii unless you created them in the test account.

Behaves like the platform: a 10 second timeout, redirects are not followed, and
anything but 2xx is a failed delivery (exit code 1).
"""

import argparse
import datetime
import hashlib
import hmac
import json
import socket
import sys
import urllib.error
import urllib.request
import uuid

TIMEOUT_SECONDS = 10


def format_timestamp(dt: datetime.datetime) -> str:
    """ISO 8601 UTC as Frisbii sends it: milliseconds without trailing zeros, e.g. .64Z, or none."""
    millis = f"{dt.microsecond // 1000:03d}".rstrip("0")
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + (f".{millis}" if millis else "") + "Z"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--secret", required=True)
    p.add_argument("--event", default="invoice_settled")
    p.add_argument("--invoice")
    p.add_argument("--customer")
    p.add_argument("--subscription")
    p.add_argument("--bad-signature", action="store_true", help="send an invalid signature (expect 401)")
    a = p.parse_args()

    webhook_id = uuid.uuid4().hex
    timestamp = format_timestamp(datetime.datetime.now(datetime.timezone.utc))
    signature = hmac.new(a.secret.encode(), (timestamp + webhook_id).encode(), hashlib.sha256).hexdigest()
    if a.bad_signature:
        signature = "0" * 64

    payload = {
        "id": webhook_id,
        "event_id": uuid.uuid4().hex,
        "event_type": a.event,
        "timestamp": timestamp,
        "signature": signature,
    }
    for key in ("invoice", "customer", "subscription"):
        if getattr(a, key):
            payload[key] = getattr(a, key)

    req = urllib.request.Request(
        a.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
            print(resp.status, resp.read(500).decode(errors="replace"))
            ok = 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print(e.code, e.read(500).decode(errors="replace"))
        if 300 <= e.code < 400:
            print(f"Redirect to {e.headers.get('Location')}: Frisbii does not follow it, use the final URL")
        ok = False
    except (urllib.error.URLError, socket.timeout) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, socket.timeout):
            print(f"No response within {TIMEOUT_SECONDS} s: Frisbii would retry this delivery")
        else:
            print(f"Could not deliver: {reason}")
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
