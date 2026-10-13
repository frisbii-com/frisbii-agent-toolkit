---
name: frisbii-webhooks
description: Implement and debug Frisbii Billing and Frisbii Pay webhooks (formerly Reepay webhooks). Use when writing a webhook endpoint, verifying webhook signatures, choosing which events to handle (invoice, subscription, customer events), dealing with retries, duplicates or out-of-order events, or testing webhooks locally.
---

# Frisbii webhooks

Frisbii sends an HTTP POST with a small JSON body to each configured URL
whenever an event happens. Webhooks are how your system learns that a payment
settled, a renewal failed, or a subscription expired.

## Payload

```json
{
  "id": "8ab4b56439944e62ababca7954355578",
  "event_id": "680bd8055b5c444bb467dcb731c65bf9",
  "event_type": "invoice_settled",
  "timestamp": "2015-06-25T12:10:00.64Z",
  "signature": "7a591eddc400af4c8a64ff551ff90b37d79471bd2c9a5a2fcd4ed6944f39cb09",
  "customer": "cust-42",
  "subscription": "sub-42",
  "invoice": "order-1001",
  "transaction": "28b1af53d7ecd1c487292402a908e2b3",
  "payment_method": "ca_…"
}
```

`id`, `event_id`, `event_type`, `timestamp`, `signature` and `customer` are in
every webhook; `invoice`, `subscription`, `transaction`, `payment_method`,
`credit_note`, `dispute`, … only when relevant. New fields get added over time,
so ignore unknown ones. The payload carries **references, not state**: fetch the
object (`GET /v1/invoice/{invoice}`, `GET /v1/subscription/{subscription}`).

## Verify every request

```
signature = hex( HMAC_SHA256( key = webhook_secret, message = timestamp + id ) )
```

- `timestamp` and `id` are the exact strings from the payload, concatenated with
  no separator.
- The webhook secret is per account (test and live differ). Find it in the
  admin webhook settings or `GET /v1/account/webhook_settings`. Store it as a
  secret, never in code.
- The signature covers only `id` + `timestamp` (deliberately, so new fields can
  be added). It proves the webhook came from Frisbii; replay protection comes
  from storing processed ids (below), and state always comes from the API.
- Compare with a **constant-time** comparison.
- Reject (HTTP 401) on mismatch and log it.

Ready-made verifiers (copy into the project, no dependencies):

| Language | File |
|---|---|
| Python | [scripts/verify_webhook.py](scripts/verify_webhook.py) |
| Node.js / TypeScript | [scripts/verify_webhook.js](scripts/verify_webhook.js) |
| PHP | [scripts/verify_webhook.php](scripts/verify_webhook.php) |
| Java | [scripts/VerifyWebhook.java](scripts/VerifyWebhook.java) |
| C# | [scripts/VerifyWebhook.cs](scripts/VerifyWebhook.cs) |
| Go | [scripts/verify_webhook.go](scripts/verify_webhook.go) |

To exercise a local endpoint with a correctly signed fake event:

```bash
python3 scripts/send_test_webhook.py --url http://localhost:3000/webhooks/frisbii \
  --secret "$FRISBII_WEBHOOK_SECRET" --event invoice_settled --invoice order-1001
```

## Handler pattern

```text
POST /webhooks/frisbii
  1. parse JSON; verify signature        → 401 if invalid
  2. dedupe on payload.event_id          → 200 if already processed
  3. enqueue {id, event_type, refs}      → 200 immediately
worker:
  4. fetch current object state from the API
  5. apply business change idempotently (keyed on your own handles)
  6. mark payload.event_id processed
```

Rules (from the platform's delivery guarantees):
- **Respond 2xx within 10 seconds.** Connection and response timeouts are 10 s;
  anything else (including redirects) counts as a failure. Do the work
  asynchronously.
- **Retries:** after 2, 5, 10, 20 and 30 minutes, then hourly for three days
  (24 hours on test accounts). Alert emails can be enabled in the admin.
- **Dedupe.** The same event can arrive more than once. With several webhook
  URLs, each URL gets a different `id` but the same `event_id`. Dedupe business
  processing on `event_id`, and keep `id` for replay protection.
- **Ordering** is FIFO per customer and URL, but only while deliveries succeed.
  A failed webhook is retried without blocking later ones. Always act on fetched
  state, never on the sequence.
- **Concurrency:** at most five webhook requests in parallel per account.
- **Return non-2xx only when you want a retry.** Invalid signature → 401;
  irrelevant event → 200.
- **Reconcile.** Periodically compare with the API (e.g. `GET /v1/event` or list
  invoices by state) so a missed webhook cannot leave an order unpaid forever.
- **Firewalls:** webhooks come from `52.18.114.235` or `34.247.100.100`, to
  ports 80/443 only.

## Events to handle

See [references/events.md](references/events.md) for the catalogue. Minimum sets:

| Integration | Events |
|---|---|
| One-off payments | `invoice_authorized`, `invoice_settled`, `invoice_failed`, `invoice_cancelled`, `invoice_refund`, `invoice_refund_failed`, `invoice_dispute_*` |
| Subscriptions | the above plus `subscription_created`, `subscription_renewal`, `subscription_changed`, `subscription_cancelled`, `subscription_uncancelled`, `subscription_on_hold`, `subscription_on_hold_dunning`, `subscription_reactivated`, `subscription_expired`, `subscription_expired_dunning`, `invoice_dunning`, `invoice_dunning_notification`, `subscription_payment_method_changed` |
| Customer sync | `customer_created`, `customer_changed`, `customer_deleted`, `customer_payment_method_added/updated/deleted/failed` |

## Configuration

- Configure URLs (several allowed, for redundancy), the events that should
  produce webhooks (not every event does by default), optional HTTP Basic auth
  and alert emails in the admin, or via `GET/PUT /v1/account/webhook_settings`.
  A new secret can be generated via the API. Rotate it on suspicion of leakage.
- Basic auth is an additional layer, not a replacement for signature checks.
- Separate endpoints (and secrets) for test and live accounts.
