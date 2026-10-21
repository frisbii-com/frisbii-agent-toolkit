---
name: frisbii-best-practices
description: Opinionated guidance for building on Frisbii Billing and Frisbii Pay (the platform formerly known as Reepay). Use when starting a Frisbii integration, choosing between Frisbii products or APIs, writing code that calls api.frisbii.com, api.reepay.com or the Frisbii checkout API, handling payments, subscriptions, customers, invoices or webhooks with Frisbii, or reviewing a Frisbii integration. Routes to the more specific frisbii-* skills.
---

# Frisbii Billing & Pay: best practices

Frisbii Billing (recurring billing: plans, subscriptions, invoicing, dunning) and
Frisbii Pay (payments: checkout, card-on-file, settle, refund) run on **one
platform and one API**, the platform formerly known as Reepay. A single Frisbii
account gives you both. Most integrations use Pay's checkout to collect a payment
method and Billing's subscriptions to charge it on a schedule.

Authoritative references: API reference at <https://docs.frisbii.com/> (machine-readable index:
<https://docs.frisbii.com/llms.txt>; every page is available as `.md`), help
centre at <https://help.frisbii.com/docs>. When this skill and the API reference
disagree, the API reference wins. Say so to the user so the skill can be fixed.

## 1. Route to the right product first

| The developer wants to… | Use | Skill |
|---|---|---|
| Take a one-off payment (web shop, donation, top-up) | Pay: charge session + Checkout | `frisbii-checkout` |
| Save a card / wallet for later charges | Pay: recurring session | `frisbii-checkout` |
| Bill a customer on a schedule (SaaS, memberships, boxes) | Billing: plans + subscriptions | `frisbii-subscriptions` |
| React to payments, failures, cancellations | Webhooks | `frisbii-webhooks` |
| Move from Stripe | Billing + Pay | `frisbii-migrate-from-stripe` |
| Check an integration before production | All | `frisbii-go-live-review` |
| Bill on usage (metered) | Billing: usage-based billing products | `frisbii-subscriptions` |
| Let customers manage their own subscriptions | Billing: Customer Portal (plan feature) | `frisbii-subscriptions` |
| Already on Frisbii Transform (billwerk) | Different API: these skills do not apply | Talk to Frisbii Customer Success |

Out of scope for this skill set: **Frisbii Transform** (the former billwerk
platform, a different API at a different host), **Frisbii Media**, and the
**Frisbii App for Salesforce**. If the developer is using any of these, say so
and do not apply the guidance below to them.

## 2. Platform fundamentals (get these right in every integration)

**Hosts** (the `*.reepay.com` hosts of the same names still work for existing integrations):
- Core API: `https://api.frisbii.com/v1/`: customers, subscriptions, plans, charges, invoices, refunds.
- Checkout API: `https://checkout-api.frisbii.com/v1/`: creating checkout sessions only.
- Checkout JS: `https://checkout.frisbii.com/checkout.js`.
- Admin UI: `https://app.frisbii.com/`.

**Authentication.** HTTP Basic auth with a **private API key** (`priv_…`) as the
username and an empty password (`Authorization: Basic base64("priv_…:")`). The
private key is a server-side secret:
- never ship it to a browser, mobile app or public repo;
- load it from the environment / secret manager, never hard-code it;
- an account can have several active keys: use one per service/environment so
  they can be rotated independently.

**Test vs live.** Test mode is a separate **test account** with its own keys,
webhook secret and catalogue. `GET /v1/account` returns `state`: `test`,
`live` or `closed`. `POST /v1/customer` and `POST /v1/subscription` accept a
`test` flag that makes the API verify the account state matches what you
intended. Use it to stop test code from ever writing to a live account. Test
customers created more than three months ago are deleted automatically,
together with their subscriptions and invoices. "Going live" means
swapping key, webhook secret and any handles to the live account; keep every
environment-specific value in configuration, not code.

**Amounts are integers in minor units.** `10000` with `DKK` is 100.00 DKK.
Never use floats for money. Never send `amount * 100` computed from a float;
keep amounts as integers end to end. Currencies are ISO 4217 codes.

**Handles are your IDs.** Customers, subscriptions, charges/invoices, plans,
add-ons, discounts and coupons all take a `handle` you choose (max 255 chars,
128 for add-ons, `[a-zA-Z0-9_.-@]`). Use them:
- Derive handles from your own primary keys (`cust-<your id>`, `order-<order id>`).
  Then you never need to store a Frisbii-generated ID, and you can always look an
  object up by your own key.
- Handles are unique per account: retrying a create with the same handle cannot
  create a second object. Never use random handles for orders/charges. A charge
  handle must not look like a subscription invoice handle (`inv-<number>` by
  default).
- For charges, also send the idempotency `key` parameter. With the same `key`
  and `handle`, a retried `POST /v1/charge` returns the original result instead
  of failing with "already authorized/settled". The docs specifically call this
  out for instant-settle charges after a network error. The original result
  includes a decline: to try a declined charge again, keep the `handle` and send
  a new `key`.
- `generate_handle: true` exists for customers and subscriptions. Use it only when
  you genuinely have no stable key. A charge with an inline `customer` object but
  no customer `handle` creates a new customer on every call, so always send one.

**Webhooks are the source of truth for asynchronous state.** The redirect to
`accept_url` is a UX signal, not a payment confirmation: users close tabs,
redirects get replayed, query strings get forged. Always confirm state either
from a verified webhook or by fetching the object server-side. See
`frisbii-webhooks`.

**Never touch raw card data.** Collect payment methods with Frisbii Checkout
(hosted window, modal or embedded). The integration stays out of PCI DSS scope
beyond SAQ A. Do not build your own card form posting PANs to your server.

**A declined payment is not an HTTP error.** `POST /v1/charge` and
`POST /v1/charge/{handle}/settle` answer **HTTP 200** when the request was
processed, also when the payment failed. Read `state` (`authorized`, `settled`,
`failed`, or `pending` for asynchronous methods) and, on failure, `error_state`
(`soft_declined`, `hard_declined` or `processing_error`) and `error`. Code that
only checks the HTTP status treats a declined charge as paid.

**Errors.** Non-2xx responses return a JSON error object with `http_status`,
`http_reason`, `error`, optional `message`, `code`, `path`, `timestamp`,
`request_id` and, where a payment operation failed, `transaction_error` (e.g.
`insufficient_funds`, `credit_card_expired`). Log `request_id`: Frisbii support
needs it. The same value is sent as the `request-id` response header on both the
Core and the Checkout API. Branch on `http_status`, `code` and `transaction_error`,
never on the message text. Validation errors (422) carry a `message` but no
`code`. Error codes: <https://api.frisbii.com/v1/error_codes>.
- 400 with `code` 1 "Malformed authorization header" usually means `Bearer`
  instead of Basic auth; 401 (`code` 6) an unknown key; 403 (`code` 7) no
  credentials, or a key without permission for the operation.
- 4xx: a bug or a business outcome. Do not retry blindly.
- 429: rate limit (`code` 122) or concurrent-request limit (`code` 123). Back
  off and retry; reduce parallelism.
- 5xx / network errors: retry with back-off. This is safe because creates use
  deterministic handles (and `key` for charges).

**Lists and pagination.** `GET /v1/list/{resource}` (e.g. `/v1/list/invoice`)
with `range`, `from`/`to` or `interval`, `size` (10–100) and
`next_page_token`. Lists are for specific queries and occasional bulk pulls.
Do not poll them to detect changes; use webhooks.

## 3. Opinionated defaults

1. **Checkout:** use Frisbii Checkout sessions (charge session / recurring
   session). Prefer the **embedded** or **modal** checkout for web apps and the
   **hosted window** (redirect) for the simplest possible integration or when the
   site cannot load third-party JS.
2. **Authorise vs settle:** for physical goods, authorise at checkout
   (`settle: false`) and **settle on shipment**. For digital goods and services
   delivered immediately, settle at checkout (`settle: true`).
3. **Subscriptions:** save the payment method with a recurring session, then
   create the subscription server-side with that payment method as the source.
   Let Billing generate invoices and charge renewals. Do not run your own cron
   that creates charges for recurring billing.
4. **Pricing changes:** create a new plan (or plan version) rather than editing
   live prices in place; move subscriptions deliberately.
5. **Webhooks:** verify every signature, acknowledge fast (2xx), process
   asynchronously and idempotently, then fetch the object for full state.
6. **Configuration over code:** plan handles, webhook secrets, keys and URLs
   live in configuration per environment.

## 4. Mistakes we see most often

See [references/common-mistakes.md](references/common-mistakes.md) for the full
list with fixes, ranked by how often they reach support. The top five:

1. Deciding "paid" from a redirect, a webhook payload or `subscription_created`
   instead of fetching the invoice; or treating a cancel redirect or one
   `invoice_failed` as final.
2. Embedding checkout where it cannot work: Apple Pay without domain setup,
   in-app webviews, broken app-switch returns.
3. Not enabling, or misreading, the webhook events the flow depends on.
4. API key, auth scheme or environment mix-ups (Bearer instead of Basic, test
   key against live, environments sharing one account).
5. Session or charge parameters that do not fit the payment method
   (`card_on_file` with wallets, recurring sessions on one-off methods).

Always required even though tickets rarely show it: verify webhook signatures
with a constant-time compare, and keep the private key server-side.

## 5. The Frisbii MCP server (optional)

The `frisbii` plugin connects the Frisbii Billing & Pay MCP server
(`https://mcp.frisbii.com/mcp`). On first use the developer signs in through
the browser (OAuth); the tools then act on the account they signed in to.

- **Sign in with the test account** while building. Before any tool call that
  creates, changes or refunds something, check which account the session is on
  and confirm with the developer if it is live.
- Use the MCP tools to inspect real state while coding: look up a charge, a
  subscription or a plan; check that plan handles the code relies on exist;
  replay what a webhook referred to. Use them to set up test data.
- Do not use MCP calls as a substitute for the integration itself. The
  developer's code must call the API directly with its own key.
- Everything in this skill works without the MCP server. Without it, explain
  the `curl` call instead.

## 6. How to work

- Before writing code, identify which Frisbii objects the flow touches and which
  webhook events confirm each step.
- When unsure about a field name or enum value, check the API reference rather
  than guessing. Field names differ from Stripe's (see
  `frisbii-migrate-from-stripe`).
- When the developer is about to go to production, run `frisbii-go-live-review`.
- More API detail: [references/api-basics.md](references/api-basics.md).
