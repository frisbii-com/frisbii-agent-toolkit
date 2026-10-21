# Common Frisbii integration mistakes

Ranked by how often they come up in Frisbii support: **often**, **regularly**
or **sometimes**. Items marked `VERIFY` are still being confirmed against
docs.frisbii.com.

## 1. Deciding "paid" from the wrong signal (often)

**Mistake.** Fulfilling or activating on something that is not the invoice's
server-side state: the `accept_url` redirect, a webhook payload on its own,
`subscription_created`, an open browser tab, a single failed transaction, or the
HTTP status of a charge call (a declined charge answers HTTP 200 with
`state: failed`). The mirror image is just as common: treating the `cancel_url`,
a closed window or one `invoice_failed` as a final failure.

**Symptoms.** Goods or add-ons provisioned without payment; duplicate orders
because a static cancel page made the shopper buy again while the first
payment was already authorised; plugins cancelling invoices the shopper had
paid; duplicate subscriptions when a webhook was used as a synchronous signal
during signup.

**Fix.** Treat redirects and webhooks as *triggers*. On each one, fetch the
invoice/charge (`GET /v1/charge/{handle}` or `GET /v1/invoice/{id}`) and act on
its state: fulfil on `authorized`/`settled` as your flow requires. After a
`POST /v1/charge` or settle, read `state` and `error_state` in the response body.
`failed` is
not final while the customer can still retry or dunning is running; only
`cancelled` is. Make the cancel page check the order state before offering a
retry. Make every handler idempotent.

## 2. Embedding checkout where it cannot work (often)

**Mistake.** Dropping the embedded or modal checkout into an environment
without the setup it needs.

**Symptoms.** Apple Pay fails in embedded/modal checkout ("cannot run in
iframe", payment not completed); checkout jumps straight to the cancel URL;
the session hangs after 3-D Secure or MitID; app switch to MobilePay, Vipps or
iDEAL never returns; a blank page inside Facebook/Instagram or other in-app
webviews; the embedded card form cut off after a few lines.

**Fix.**
- Apple Pay in embedded/modal checkout: register and verify the domain on the
  Apple Pay agreement in the Frisbii admin, host Apple's domain-verification
  file at `https://<domain>/.well-known/apple-developer-merchantid-domain-association`,
  and pass the domain as `domainName` in the `EmbeddedCheckout`/`ModalCheckout`
  options.
- With the embedded and modal checkout, react to the checkout events (Accept,
  Error, Cancel, Close) instead of relying on redirects, but still set
  `accept_url` and `cancel_url`: on mobile, app-switch methods such as
  MobilePay return through them.
- In native apps, follow the docs' "Checkout Native App Integration": load
  checkout in a WebView (WKWebView / Android WebView), receive the checkout
  events through the Native Bridge, and set `session_data.alternative_return_url`
  to your app's URL scheme so wallet and bank apps can return to the app. Never
  send it as an empty string. For hybrid apps (React Native, Flutter, Ionic)
  see "Checkout Hybrid App Integration".
- Do not offer a payment method list that the device cannot show (for example
  Apple Pay only, to Android users).
- Give the embedded checkout's container a definite `height`: the iframe is sized
  `height: 100%`, so with only `min-height` it collapses to 150px.

## 3. Not subscribing to, or misreading, the right webhook events (often)

**Mistake.** Assuming every event is delivered by default, or guessing which
event marks a state.

**Symptoms.** "Missing webhooks" because only `invoice_authorized` is enabled,
no webhook is configured, or the configuration is disabled; failed renewals
never noticed; waiting for `customer_payment_method_deleted` when the
customer revoked the agreement in their wallet app (that is
`customer_payment_method_failed`).

**Fix.** On a new account webhooks are disabled, and only `invoice_authorized`
and `customer_payment_method_added` are selected. Enable webhooks and select
every event your flow needs (see `frisbii-webhooks`). Failed
renewal: `invoice_dunning` (entered dunning), then `invoice_settled`
(recovered) or `invoice_dunning_cancelled`/`subscription_on_hold`. A payment
method that can no longer be used: `customer_payment_method_failed`. Keep a
reconciliation job that lists recent invoices so a missed event never leaves
state wrong for long.

## 4. API key, auth and environment mix-ups (regularly)

**Mistake.** The wrong key, wrong auth scheme or wrong account.

**Symptoms.** `Authorization: Bearer priv_…` rejected; "unknown or expired api
key"; "invoice not found" or "payment method not found" because the test key
was used against live data or the key belongs to another account; a staging
app wired to the live key; several environments sharing one test account and
receiving each other's webhooks.

**Fix.** HTTP Basic auth with the private key as username and an empty
password (`base64("priv_…:")`). Keys, webhook URLs and secrets per environment
in configuration; one Frisbii test account per environment that receives
webhooks. Never share one private key across unrelated systems, and never
paste a live key into email or tickets; rotate it if that happens.

## 5. Session and charge parameters that do not fit the payment method (regularly)

**Mistake.** Sending parameters that only apply to some methods or flows.

**Symptoms.** `card_on_file` used with a wallet (Apple Pay) method or without
the customer on the session (error 19, "Card not found"), or with a
network-token (EMV token) card in a session that also saves a payment method
(error 604); bad requests on `vipps_recurring`; recurring sessions attempted
with a one-off method such as `vipps_epayment`; "why is it not settled?" on a
charge session created without `settle`; unwanted methods shown because
`payment_methods` was not restricted, or expected methods missing because an
id was misspelled or not enabled on the account (such ids are dropped
silently); wrong checkout language from `locale: en_US` for German customers.

**Fix.** Use `card_on_file` only with an active saved card (`ca_…`) of the
session's customer. When the customer is present and pays with a saved card,
that is a customer-initiated payment: use a charge session with `card_on_file`
so SCA can run. For merchant-initiated charges (customer not present), use
`POST /v1/charge` with `source` set to the saved method's id (`ca_…` card,
`ar_…` Apple Pay, `gr_…` Google Pay, …). Check each method supports recurring
before offering it in a recurring session. Set `settle` explicitly. Restrict
`payment_methods` per market, check the session shows the methods you expect,
and send the customer's real `locale`.

## 6. Subscription changes that do something other than expected (regularly)

**Mistake.** Assuming change calls merge, or pinning prices on subscriptions.

**Symptoms.**
- A second change-subscription call (for example add-ons only) replaced an
  earlier pending change, leaving subscriptions on the wrong plan. An
  immediate change likewise replaces a pending renewal change.
- A script removing and re-adding add-ons cancelled pending supersede
  changes, so subscriptions kept the old price. Any change call takes the
  subscription out of a scheduled plan update.
- Hard-coded `amount` overrides on subscriptions meant later plan price or VAT
  changes never applied; the reverse also happens: a change call without
  `amount` removed a custom price that was meant to stay.
- Contract terms (notice periods, fixation and contract dates) lost after a
  change call that did not repeat them.
- `billing` options on a plan change still producing an invoice when the
  billing cycle differs; compensation refunds failing for methods that do not
  allow partial refunds.
- Extra seats sold as one-off charges, so they never recur at renewal.
- Signups with an add-on failing with `400` code 154 "Currency mismatch": the
  add-on was created without `currency`, so it took the account default rather
  than the plans' currency.

**Fix.** Treat every change call as a full replacement: send the complete
desired change, including `amount` when the price is pinned and the contract
fields you want to keep. After an immediate change, send any renewal change
again. Do not set a subscription `amount` unless you mean to pin the price; the
`amount` (with `amount_incl_vat`) on the subscription is the custom price, no
other flag is needed. Change prices with a new plan or plan version and
supersede deliberately. Model recurring quantities as add-on quantity, not
one-off charges, and create add-ons with the plans' `currency`.

## 7. Handle collisions (regularly)

**Mistake.** Handles that are deterministic but not unique, or reused with
different data.

**Symptoms.** "Customer cannot be changed on invoice" (error 99) because shop
order numbers restarted or were reused across environments; "duplicate
customer" when `generate_handle: true` is mixed with self-chosen handles in
the same pattern; a retry that re-sent an existing handle with different order
lines silently replaced the lines of the unpaid charge, or failed with
"invoice already authorized" (error 105) / "already settled" (error 79) once it
was paid; parallel calls racing to create the same customer.

**Fix.** Handle = your own order or customer ID, unique across environments
and resets (prefix with the environment or shop). Either always generate
handles or never; do not mix. A retry must send the same handle *and* the same
amount and lines; if the basket changed, use a new handle. Serialise customer
creation. Do not use an email address as a handle (it ends up in URLs).

## 8. Treating asynchronous payment methods as synchronous (regularly)

**Mistake.** Expecting MobilePay/Vipps, Anyday, SEPA or PayPal to authorise,
settle or refund within the API call.

**Symptoms.** Client timeouts on settle; new dunning attempts started while a
transaction is still pending; partial capture rejected for methods that only
allow full capture; settling more than was authorised after the basket
changed; expecting `invoice_refund_failed` for card refunds.

**Fix.** After the call, wait for the webhook (`invoice_settled`,
`invoice_refund`, …) and fetch state. Never start a new attempt while one is
pending. Outstanding authorisation = `authorized_amount − settled_amount`.
Check per-method capture and refund rules before relying on partial settle or
refund.

## 9. Brittle webhook endpoints (sometimes)

**Mistake.** Endpoints that reject valid deliveries or answer too slowly.

**Symptoms.** Webhooks start failing after a Frisbii release because the
consumer rejected new JSON fields; endpoints returning 400/404; "read timed
out" alert emails; webhook URLs longer than 255 characters.

**Fix.** Ignore unknown fields (the API is extended without notice). Return
2xx within 10 seconds and do the work asynchronously. Answer directly: a
redirect (for example http → https, or a missing trailing slash) counts as a
failed delivery. Expect retries and make processing idempotent. Keep webhook
URLs within 255 characters.

## 10. Back-office code acting without checking state (sometimes)

**Mistake.** Plugins, cron jobs or admin scripts that cancel, delete or settle
on a timer or a guess.

**Symptoms.** Invoices cancelled seconds after authorisation by the merchant's
own key; shop auto-cancel firing while a Vipps or Anyday authorisation was
still completing; a newly added payment method deleted by a cleanup job; a
manual settle on a hard-declined SEPA mandate; a re-settle charging twice.

**Fix.** Fetch current state before any cancel, delete or settle, and make
the action conditional on it. Give asynchronous methods time to complete
before auto-cancelling.

## 11. Amounts not in minor units (sometimes)

**Mistake.** Sending major units or zero amounts.

**Symptoms.** `37.50` or `125` meant as DKK instead of øre; zero-amount order
lines (e.g. gift wrapping) causing errors; authorised amount not matching the order total; "no payment
methods found" for zero-decimal currencies such as ISK and HUF.

**Fix.** Integers in minor units end to end, computed once from the order
total. Check how zero-decimal currencies are expressed before enabling them.

## 12. Running your own renewal billing (sometimes)

**Mistake.** A scheduled job charging saved `ca_…` sources instead of using
Billing subscriptions.

**Symptoms.** Questions about duplicate protection when the job runs twice;
monthly retries on a dead card; renewals and dunning that do not match what
the platform would do.

**Fix.** Use Billing subscriptions and let the platform invoice, retry and
dun. If a custom job is unavoidable, use a deterministic handle per period
(e.g. `sub-123-2026-10`) and stop on `customer_payment_method_failed`.

## 13. Handling raw card data or internal endpoints (sometimes)

**Mistake.** Posting card numbers directly to tokenisation endpoints used
internally by checkout, or hand-building URLs the platform generates.

**Symptoms.** Integrations that break when SCA is enforced; PCI scope
the merchant did not intend.

**Fix.** Collect cards only through Frisbii Checkout. Use only documented API
endpoints and URLs returned by the API. Card migrations go through Frisbii
(see `frisbii-migrate-from-stripe`).

## Baseline: still required, even though tickets rarely show it

These rarely appear in tickets because the failure is silent until it is
exploited. Treat them as non-negotiable.

- **Verify every webhook signature** with HMAC-SHA256 and a constant-time
  compare (`frisbii-webhooks`).
- **Keep the private key server-side.** Never in frontend code, mobile apps
  or repositories.
- **Do not assume webhook order.** Fetch current state on each event instead
  of deriving it from the sequence.
