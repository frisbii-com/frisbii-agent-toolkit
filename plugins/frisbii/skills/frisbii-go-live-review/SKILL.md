---
name: frisbii-go-live-review
description: Review a Frisbii Billing / Frisbii Pay integration before it goes to production. Use when the user asks whether their Frisbii (Reepay) integration is ready to go live, asks for a pre-launch or security review of payment code, or is switching from the Frisbii test account to the live account.
---

# Frisbii go-live review

Run this review against the customer's codebase and report findings. Do not
change code unless the user asks; report first.

## Step 1: automated scan

```bash
python3 scripts/scan.py <path-to-repo> [--json]
```

(`scripts/` is relative to this skill's directory.) The scanner is heuristic.
It flags candidates; you confirm each one by reading the code. It never prints
secret values, only file and line.

## Step 2: manual checklist

Work through every item. For each, record **pass / fail / n/a** with the file
and line that proves it.

### Keys and environments
- [ ] Private key only on the server, loaded from env/secret manager; not in repo, frontend bundle, mobile app or logs.
- [ ] Live key, live webhook secret and live plan handles come from production config; nothing from the test account is hard-coded.
- [ ] Separate keys per environment; documented rotation procedure.
- [ ] Test code paths pass `test: true` (or check `GET /v1/account` → `state`) so they cannot write to the live account.

### Payments
- [ ] Payment success is confirmed server-side (webhook or `GET /v1/charge/{handle}`), **never** from the `accept_url` redirect alone.
- [ ] Charge/order handles are deterministic (derived from order IDs) and `POST /v1/charge` sends an idempotency `key`. A retry or double click cannot double-charge.
- [ ] Amounts are integers in minor units; no float arithmetic on money.
- [ ] Authorise-vs-settle policy matches the business (physical goods settle on shipment; authorisations are settled or cancelled before they expire).
- [ ] Refund and cancel flows exist and are permission-checked.
- [ ] No raw card data passes through the merchant's servers (Checkout only).

### Webhooks
- [ ] Signature verified on every request with a constant-time compare (`frisbii-webhooks`).
- [ ] Handler responds 2xx within 10 seconds (Frisbii's timeout) and processes asynchronously.
- [ ] Processing is idempotent (dedupe on `event_id`; business changes keyed on handles). Unknown payload fields are ignored.
- [ ] Logic does not depend on event order; it fetches current state.
- [ ] Live webhook URL is configured on the **live** account, reachable over HTTPS on port 443 (allow `52.18.114.235`, `34.247.100.100` through firewalls), required events selected, alert email set.
- [ ] A reconciliation job or runbook covers missed webhooks.

### Subscriptions (if used)
- [ ] Access is granted on settled invoices / active state, not on `subscription_created`.
- [ ] Failed payments, dunning, on-hold and expiry are handled; customers can update their payment method.
- [ ] Plan handles exist on the live account with the same configuration as test.
- [ ] Upgrade/downgrade timing and proration are deliberate.
- [ ] Cancellation (period end vs immediate) matches terms and conditions.

### Errors and operations
- [ ] Non-2xx responses are logged with `request-id`, `code` and `transaction_error`; 5xx/network errors retried with back-off (same `handle` + `key` for charges); 429 (codes 122/123) backs off; other 4xx not retried blindly.
- [ ] Timeouts set on all HTTP calls to Frisbii.
- [ ] Monitoring/alerts on payment failure rate and webhook failures.
- [ ] Test data, test card numbers and debug endpoints removed from production paths.

### Test evidence (in the test account)
- [ ] Success, decline (CVV `888` + amount `2001`/`3002`), SCA required (`1337`), customer cancel.
- [ ] Browser closed after payment (webhook-only confirmation path works).
- [ ] Duplicate submit / retry does not double-charge.
- [ ] Webhook with invalid signature is rejected.
- [ ] Subscription renewal, failed renewal and recovery (CVV `100`–`302`), if applicable.

## Step 3: report

Produce a short report:

1. **Verdict**: ready / ready with fixes / not ready.
2. **Blocking issues**: anything in Keys, Payments or Webhooks that fails.
3. **Recommended fixes**: non-blocking.
4. **Evidence table**: checklist item → pass/fail/n/a → file:line.

Blocking means: a leaked or hard-coded key, payment confirmed from the redirect,
unverified webhooks, non-idempotent charge creation, or float money arithmetic.
