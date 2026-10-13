"""Send a correctly signed fake Frisbii webhook to a local endpoint. No dependencies.

    python3 send_test_webhook.py --url http://localhost:3000/webhooks/frisbii \
        --secret "$FRISBII_WEBHOOK_SECRET" --event invoice_settled \
        --invoice order-1001 --customer cust-42 [--subscription sub-42] [--bad-signature]

Use only against your own development endpoints. The event is synthetic: the
referenced objects do not exist in Frisbii unless you created them in the test account.
"""

import argparse
import datetime
import hashlib
import hmac
import json
import urllib.error
import urllib.request
import uuid


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
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(resp.status, resp.read(500).decode(errors="replace"))
    except urllib.error.HTTPError as e:
        print(e.code, e.read(500).decode(errors="replace"))


if __name__ == "__main__":
    main()
