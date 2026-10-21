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
and line that proves it. The numbers in brackets point to the matching entry in
`frisbii-best-practices/references/common-mistakes.md`, which explains the
symptom and fix.

### Keys and environments
- [ ] Private key only on the server, loaded from env/secret manager; not in repo, frontend bundle, mobile app or logs.
- [ ] Live key, live webhook secret and live plan handles come from production config; nothing from the test account is hard-coded.
- [ ] Separate keys per environment; documented rotation procedure.
- [ ] Test code paths pass `test: true` (or check `GET /v1/account` → `state`) so they cannot write to the live account.
- [ ] Requests use HTTP Basic auth with the private key as username and an empty password, not `Bearer`. [4]
- [ ] Each environment that receives webhooks has its own Frisbii test account; no private key is shared across unrelated systems. [4]

### Payments
- [ ] Payment success is confirmed server-side (webhook or `GET /v1/charge/{handle}`), **never** from the `accept_url` redirect, a webhook payload alone or `subscription_created`. [1]
- [ ] Code calling `POST /v1/charge` or settle reads `state` / `error_state` from the response: a declined payment answers HTTP 200 with `state: failed`, so a 2xx status alone is not success. [1]
- [ ] A cancel redirect, a closed window or one `invoice_failed` is not treated as final: the cancel page checks the order state before offering a retry, and only `cancelled` ends an order. [1]
- [ ] Charge/order handles are deterministic (derived from order IDs) and `POST /v1/charge` sends an idempotency `key`. A retry or double click cannot double-charge. A deliberate new attempt after a decline uses a new `key` (the same `key` replays the decline).
- [ ] Handles are unique across environments and order-number resets (for example prefixed per shop or environment); `generate_handle` is not mixed with self-chosen handles; a retry re-sends the same amount and lines, and a changed basket gets a new handle; email addresses are not used as handles. [7]
- [ ] Amounts are integers in minor units; no float arithmetic on money.
- [ ] Authorise-vs-settle policy matches the business (physical goods settle on shipment; authorisations are settled or cancelled before they expire).
- [ ] Refund and cancel flows exist and are permission-checked.
- [ ] No raw card data passes through the merchant's servers (Checkout only), and no code calls Checkout's internal tokenisation endpoints or hand-builds platform URLs. [13]
- [ ] Asynchronous methods (MobilePay, Vipps, Anyday, SEPA, PayPal) are handled as asynchronous: state comes from webhooks, no new attempt starts while one is pending, and partial capture or refund is only used where the method allows it. [8]
- [ ] Back-office code (shop plugins, cron jobs, admin scripts) fetches the current state before cancelling, settling or deleting, and auto-cancel allows time for asynchronous authorisations to complete. [10]

### Checkout
- [ ] Every session sets `settle` explicitly, restricts `payment_methods` per market (ids spelled as in the docs; unknown ones are dropped silently) and sends the customer's real `locale`. [5]
- [ ] `card_on_file` is used only with saved cards (`ca_…`), in a charge session when the customer is present; merchant-initiated charges on saved methods use `POST /v1/charge` with `source`. Recurring sessions only offer methods that support recurring. [5]
- [ ] The embedded checkout container has a definite height (not only `min-height`), so the iframe is not cut off at 150px. [2]
- [ ] Apple Pay in embedded/modal checkout: the domain is registered on the Apple Pay agreement in the Frisbii admin, Apple's domain-verification file is hosted on it, and it is passed as `domainName`. [2]
- [ ] Embedded and modal checkout react to the checkout events (Accept, Error, Cancel, Close) and still set `accept_url`/`cancel_url` for app-switch returns on mobile; Window checkout relies on the URLs only. [2]
- [ ] Native apps load checkout in a WebView with the Native Bridge, as in the docs' "Checkout Native App Integration", and set `session_data.alternative_return_url` to the app's URL scheme (never an empty string). [2]
- [ ] Tested on real devices for every payment method offered, including app switch to and from MobilePay/Vipps and 3-D Secure/MitID. [2]

### Webhooks
- [ ] Signature verified on every request with a constant-time compare (`frisbii-webhooks`).
- [ ] Handler responds 2xx within 10 seconds (Frisbii's timeout) and processes asynchronously.
- [ ] Processing is idempotent (dedupe on `id` and `event_id`; business changes keyed on handles). Unknown payload fields are ignored: no strict schema validation that rejects new fields, and `customer` is not required on every event. [9]
- [ ] The signature check uses the raw `timestamp` string (not a re-formatted date), and a secret rotation plan accepts the old and new secret while older webhooks are retried.
- [ ] Logic does not depend on event order; it fetches current state.
- [ ] Live webhook URL is configured on the **live** account and webhooks are enabled there (they start disabled), reachable over HTTPS on port 443 without a redirect (allow `52.18.114.235`, `34.247.100.100` through firewalls), required events selected, alert email set. The URL is at most 255 characters.
- [ ] Every event the flow depends on is enabled, including `invoice_dunning` for failed renewals and `customer_payment_method_failed` for methods that can no longer be used. [3]
- [ ] A reconciliation job or runbook covers missed webhooks.

### Subscriptions (if used)
- [ ] Access is granted on settled invoices / active state, not on `subscription_created`. [1]
- [ ] Change-subscription calls send the complete desired change (including a pinned `amount` and the contract fields to keep), so a second call does not silently replace the first or drop a custom price. [6]
- [ ] No subscription `amount` overrides unless the price is meant to be pinned; recurring quantities (seats) are add-on quantities, not one-off charges. [6]
- [ ] Immediate changes set `compensation_method` explicitly (the default refunds unused time to the payment method). [6]
- [ ] Renewals are billed by Billing subscriptions, not a custom job charging saved sources. [12]
- [ ] Plans and add-ons are created with an explicit, matching `currency` (an add-on without one takes the account default and signups fail with "Currency mismatch"). [6]
- [ ] Failed payments, dunning, on-hold and expiry are handled; customers can update their payment method.
- [ ] Plan handles exist on the live account with the same configuration as test.
- [ ] Upgrade/downgrade timing and proration are deliberate.
- [ ] Cancellation (period end vs immediate) matches terms and conditions.

### Errors and operations
- [ ] Non-2xx responses are logged with `request_id` (body) or the `request-id` header, `code` and `transaction_error`; 5xx/network errors retried with back-off (same `handle` + `key` for charges); 429 (codes 122/123) backs off; other 4xx not retried blindly.
- [ ] Timeouts set on all HTTP calls to Frisbii.
- [ ] Monitoring/alerts on payment failure rate and webhook failures.
- [ ] Test data, test card numbers and debug endpoints removed from production paths.

### Test evidence (in the test account)
- [ ] Success, decline (CVV `888` + amount `2001`/`3002`), SCA required (`1337`), customer cancel.
- [ ] Browser closed after payment (webhook-only confirmation path works).
- [ ] Duplicate submit / retry does not double-charge.
- [ ] Shopper cancels, then pays again; shopper pays in an app and returns late: no duplicate order and no premature cancel.
- [ ] Webhook with invalid signature is rejected.
- [ ] Subscription renewal, failed renewal and recovery (CVV `100`–`302`), if applicable.

## Step 3: report

Produce a short report:

1. **Verdict**: ready / ready with fixes / not ready.
2. **Blocking issues**: anything in Keys, Payments or Webhooks that fails.
3. **Recommended fixes**: non-blocking.
4. **Evidence table**: checklist item → pass/fail/n/a → file:line.

Blocking means: a leaked or hard-coded key, payment confirmed from the redirect
or another client-side signal (or from the HTTP status of a charge call alone),
unverified webhooks, non-idempotent charge
creation or colliding handles, float money arithmetic, raw card data on the
merchant's servers, or back-office code that cancels or settles without
checking state.
