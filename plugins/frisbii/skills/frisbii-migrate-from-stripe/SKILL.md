---
name: frisbii-migrate-from-stripe
description: Migrate an integration and its billing data from Stripe to Frisbii Billing and Frisbii Pay. Use when a codebase uses Stripe (stripe SDK, PaymentIntents, Checkout Sessions, Subscriptions, Prices, webhooks) and needs to move to Frisbii, when mapping Stripe objects or events to Frisbii equivalents, planning a card data migration, or running Stripe and Frisbii in parallel.
---

# Migrating from Stripe to Frisbii

A Stripe migration has three independent workstreams. Plan them separately:

1. **Code**: replace Stripe API calls, Checkout and webhooks with Frisbii ones.
2. **Catalogue and subscriptions**: recreate products/prices as plans and move
   active subscriptions without double-billing or skipping a period.
3. **Payment methods**: cards move via a PCI-compliant **card data export from
   Stripe to Frisbii**. This is not something code or an agent can do. SEPA
   mandates and PayPal agreements can be imported through the API (below).

## 1. Object mapping

Full table: [references/object-mapping.md](references/object-mapping.md).

| Stripe | Frisbii | Key differences |
|---|---|---|
| Customer `cus_…` | Customer (your `handle`) | Choose handles from your own IDs; store Stripe ID in metadata during transition |
| PaymentMethod `pm_…` / Card | Payment method `ca_…` | Created via Checkout or card import, never via raw PAN |
| PaymentIntent | Charge (an invoice) | `handle` = your order ID; `settle: false/true` ≈ `capture_method` |
| SetupIntent | Recurring checkout session | Saves a method, no amount |
| Checkout Session (payment) | Charge session | `order.handle`, `accept_url`/`cancel_url` |
| Checkout Session (subscription) | Recurring session + `POST /v1/subscription` | Two steps on Frisbii |
| Product + recurring Price | Plan | One plan per price (amount + interval + currency) |
| Product + one-time Price | Order line on a charge | No catalogue object needed |
| Subscription | Subscription | `start_date`, `plan`, `source` |
| Subscription item (extra) | Add-on | Quantity add-ons for seats |
| Metered price / usage record | Usage-based billing product + usage records | Report usage to Frisbii instead of Stripe |
| Coupon | Discount | Amount or percentage, duration |
| Promotion code | Coupon | The redeemable code |
| Invoice | Invoice | Do not migrate history; keep Stripe export as archive |
| Refund | Refund | `POST /v1/refund` with invoice handle |
| Idempotency-Key header | Deterministic `handle` (+ `key` on charges) | |
| Test mode keys | Separate test **account** | `GET /v1/account` → `state`; `test` flag on subscription create |

Amounts are minor-unit integers on both platforms, so no conversion is needed.

## 2. Code migration

Work through the codebase in this order, one flow at a time, keeping Stripe
working until cut-over:

1. Introduce a payment-provider abstraction if there is none (one module owns
   all Stripe calls). Then implement the Frisbii side behind it.
2. **Checkout:** replace `stripe.checkout.sessions.create` / Payment Element with
   a Frisbii charge or recurring session (`frisbii-checkout`).
3. **Subscriptions:** replace `stripe.subscriptions.create/update/cancel`
   (`frisbii-subscriptions`). Map `proration_behavior`:
   `create_prorations` → `timing: immediate` + prorated billing;
   `none` → `timing: renewal`.
   Map `cancel_at_period_end: true` → `POST /cancel`; immediate cancel →
   `POST /expire`.
4. **Webhooks:** new endpoint with Frisbii signature verification
   (`frisbii-webhooks`). Event mapping: [references/event-mapping.md](references/event-mapping.md).
   Frisbii payloads contain references only; fetch the object.
5. **Customer portal:** Stripe Billing Portal → **Frisbii Customer Portal**
   (plan feature) with SSO from your app: `POST
   https://customer-portal-api.reepay.com/v1/session` `{ "email" }` → redirect
   to `redirect_url`. Otherwise build actions on the API (subscription session
   for payment-method changes, cancel, change plan).
6. Remove Stripe-specific assumptions: `metadata` limits, `expand[]`, `cus_`
   prefixes in your DB, Stripe Tax.

Search the codebase for: `stripe`, `Stripe(`, `pk_live`, `sk_live`,
`stripe-signature`, `payment_intent`, `checkout.session`, `price_`, `sub_`.

## 3. Data migration and parallel run

1. **Recreate the catalogue** as plans/add-ons/discounts in the Frisbii *test*
   account first; keep a mapping file `stripe price id → plan handle`.
2. **Request the card export** from Stripe to Frisbii (Stripe's PAN export to
   another PCI DSS Level 1 processor). Frisbii's team imports the cards and
   returns a mapping `stripe pm_/card id → ca_…`. Start this early; it takes
   weeks, not days. **Hand this off to Frisbii. Do not attempt it in code.**
3. **New signups go to Frisbii** from day one of the parallel run; existing
   customers stay on Stripe until migrated.
4. **Move each subscription at its period boundary:**
   - create the Frisbii subscription with `start_date` = Stripe
     `current_period_end` (so the first Frisbii invoice replaces the next Stripe
     invoice), `source` = imported `ca_…`, no trial, no setup fee;
   - set the Stripe subscription to `cancel_at_period_end`;
   - use deterministic handles (`sub-<your id>`) so re-runs cannot duplicate.
5. **Reconcile** before each batch and after each billing day: counts per
   plan, MRR, next billing date per customer.
6. **Non-card methods:**
   - SEPA Direct Debit on Stripe: `POST /v1/payment_method/import_stripe_sepa`
     with `stripe_customer_id`, `stripe_payment_method_id` and an active,
     reusable `stripe_mandate_id`. The mandate continues; no customer action.
   - PayPal: `POST /v1/payment_method/import_paypal` (`token_type` `VAULT` or
     `BILLING_AGREEMENT`) when the agreement belongs to the merchant's own
     PayPal account; confirm with Frisbii.
   - Klarna: `POST /v1/payment_method/import_klarna` (confirm eligibility).
   - Apple Pay / Google Pay and anything else: re-collect via a subscription
     checkout session link before the Stripe period ends.

Dry-run every write against the Frisbii test account; never run a migration
script against live first.
