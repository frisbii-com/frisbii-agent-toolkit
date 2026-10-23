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

`id`, `event_id`, `event_type`, `timestamp` and `signature` are in every
webhook. `customer` is in every customer, invoice and subscription event, but not
in account-level events such as `settlement_data_updated`, so do not require it.
`invoice`, `subscription`, `transaction`, `payment_method`, `credit_note`,
`dispute`, … appear only when relevant. New fields get added over time, so
ignore unknown ones. The payload carries **references, not state**: fetch the
object (`GET /v1/invoice/{invoice}`, `GET /v1/subscription/{subscription}`).

## Verify every request

```
signature = hex( HMAC_SHA256( key = webhook_secret, message = timestamp + id ) )
```

- `timestamp` and `id` are the exact strings from the payload, concatenated with
  no separator. The timestamp is ISO 8601 in UTC with zero to three fraction
  digits (`2015-06-25T12:10:00.64Z`, `…:00Z`). Read it as a string: a JSON
  library that turns it into a date and back (Newtonsoft `JObject` does by
  default, a Jackson mapping to `OffsetDateTime` does) changes the text and
  breaks the check.
- The webhook secret is per account (test and live differ). Find it in the
  admin webhook settings or `GET /v1/account/webhook_settings`. Store it as a
  secret, never in code.
- The signature covers only `id` + `timestamp` (deliberately, so new fields can
  be added). It proves the webhook came from Frisbii; replay protection comes
  from storing processed `id`s (below), and state always comes from the API.
- The signature is computed once, when the webhook is created, and retries and
  manual resends send it unchanged. After rotating the secret, accept the old
  and the new secret until older webhooks have finished retrying (up to three
  days). For the same reason, do not reject webhooks for an old `timestamp`.
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
  2. seen payload.id or payload.event_id → 200 (retry or duplicate)
  3. enqueue {id, event_type, refs}      → 200 immediately
worker:
  4. fetch current object state from the API
  5. apply business change idempotently (keyed on your own handles)
  6. mark payload.id and payload.event_id processed
```

Storing `id` as well as `event_id` matters: `event_id` is not covered by the
signature, so a captured webhook replayed with a changed `event_id` would
otherwise pass both the signature check and the dedupe.

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
- **Concurrency:** expect several webhook requests in parallel, also for the same
  customer while earlier deliveries are being retried. Make processing safe under
  concurrency rather than relying on a fixed limit.
- **Return non-2xx only when you want a retry.** Invalid signature → 401;
  irrelevant event → 200.
- **Reconcile.** Periodically compare with the API (e.g. `GET /v1/event` or list
  invoices by state) so a missed webhook cannot leave an order unpaid forever.
  `GET /v1/list/webhook` (filter on `state`) shows deliveries that failed, and
  `POST /v1/webhook/resend` sends them again once your endpoint is fixed.
- **Firewalls:** webhooks come from `52.18.114.235` or `34.247.100.100`, to
  ports 80/443 only.

## Events to handle

See [references/events.md](references/events.md) for the catalogue. Minimum sets:

| Integration | Events |
|---|---|
| One-off payments | `invoice_authorized`, `invoice_settled`, `invoice_failed`, `invoice_cancelled`, `invoice_refund`, `invoice_refund_failed`, `invoice_dispute_opened`, `invoice_dispute_waiting_for_response`, `invoice_dispute_under_review`, `invoice_dispute_resolved` |
| Subscriptions | the above plus `subscription_created`, `subscription_payment_method_added`, `subscription_payment_method_changed`, `subscription_renewal`, `subscription_changed`, `subscription_cancelled`, `subscription_uncancelled`, `subscription_on_hold`, `subscription_on_hold_dunning`, `subscription_reactivated`, `subscription_expired`, `subscription_expired_dunning`, `invoice_dunning`, `invoice_dunning_notification`, `invoice_dunning_cancelled`, `customer_payment_method_failed` |
| Customer sync | `customer_created`, `customer_changed`, `customer_deleted`, `customer_payment_method_added`, `customer_payment_method_updated`, `customer_payment_method_deleted`, `customer_payment_method_failed` |

Spell event names out in full when you configure them; the settings API does
not accept wildcards.

## Configuration

- Configure URLs (several allowed, for redundancy), the events that should
  produce webhooks, optional HTTP Basic auth and alert emails in the admin, or
  via `GET/PUT /v1/account/webhook_settings`.
- On a new account webhooks are **disabled**, and only `invoice_authorized` and
  `customer_payment_method_added` are selected. Enable them and select every
  event your flow needs.
- `PUT /v1/account/webhook_settings` replaces the URLs, Basic auth credentials
  and alert settings with what you send: `GET` first and send everything back.
  Leaving out `username`/`password` removes Basic auth. `event_types` is kept
  when you leave it out.
- `POST /v1/account/webhook_settings/secret` generates a new secret. Rotate it on
  suspicion of leakage, and accept both secrets during the switch (see above).
- Basic auth is an additional layer, not a replacement for signature checks.
- Separate endpoints (and secrets) for test and live accounts.
