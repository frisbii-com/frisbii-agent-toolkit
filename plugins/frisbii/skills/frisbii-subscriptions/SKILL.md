---
name: frisbii-subscriptions
description: Build recurring billing on Frisbii Billing (formerly Reepay subscriptions). Use when designing plans and pricing, creating or changing subscriptions, add-ons, discounts and coupons, trials, proration and plan changes, billing schedules and anchors, usage-based (metered) billing or one-time additional costs, contract, notice and fixation periods, cancellation and pausing, the customer portal, or dunning and failed renewals.
---

# Frisbii Billing subscriptions

Read `frisbii-best-practices` first (auth, handles, amounts). Reference:
<https://docs.frisbii.com/reference/subscription>.

## Object model

```
Plan ──< Subscription >── Customer ──< Payment method (ca_…, sepa, paypal, …)
          │   ├─ add-ons (on_off or quantity)
          │   ├─ subscription discounts / coupon redemptions
          │   ├─ additional costs (one-time amounts on next invoice)
          │   └─ usage-based billing products (+ usage records)
          └─< Invoices (inv-<n>) ──< Transactions
```

## Recommended signup flows

**A. One step with Checkout (simplest).** `POST /v1/session/subscription` on the
Checkout API with `prepare_subscription` (plan, customer, add-ons, …). The
subscription is created when the customer completes payment. Open it with
`Reepay.EmbeddedSubscription` / `Reepay.ModalSubscription`.

**B. Two steps, server-controlled.**
1. Create/save the customer and collect a payment method with a recurring
   session (`frisbii-checkout`). Confirm the payment method server-side.
2. Create the subscription:

```json
POST https://api.frisbii.com/v1/subscription
{
  "handle": "sub-42",
  "customer": "cust-42",
  "plan": "plan-pro-monthly",
  "signup_method": "source",
  "source": "ca_…",
  "add_ons": [{ "add_on": "addon-seat", "quantity": 4, "handle": "sub-42-seat" }],
  "coupon_codes": ["WELCOME10"],
  "test": true
}
```

(`test: true` only in test environments: the API rejects the call if the
account is not a test account, and vice versa with `false`.)

`signup_method` is one of `source` (existing payment method or card token),
`email` (Frisbii emails the customer a link) or `link` (you get a link to send).
`POST /v1/subscription/prepare` creates a **pending** subscription that becomes
active only when the customer adds payment information.

Then gate access on webhooks: `invoice_settled` for the first invoice,
`subscription_on_hold` / `subscription_expired` to revoke.

## Designing plans (`POST /v1/plan`)

| Decision | Fields | Guidance |
|---|---|---|
| Price | `amount` (minor units), `currency`, `vat` or `tax_policy`, `amount_incl_vat` (default **true**) | Decide incl/excl VAT once for the whole catalogue and always send it explicitly |
| Interval & anchor | `schedule_type` (`manual`, `daily`, `weekly_fixedday`, `month_startdate`, `month_fixedday`, `month_lastday`), `interval_length`, `schedule_fixed_day`, `base_month` | Fixed day (e.g. 1st) simplifies finance; start-date anchoring is simpler for customers. Yearly = `month_*` with `interval_length: 12` |
| First partial period | `partial_period_handling` (`bill_full`, `bill_prorated`, `bill_zero_amount`, `no_bill`) | With fixed-day anchors, prorate |
| In advance / arrears | `prepaid` | Default in advance |
| Trial | `trial_interval_length` + `trial_interval_unit` (`days`/`months`), `trial_reminder_email_days` | Card-up-front trials convert better |
| Setup fee | `setup_fee`, `setup_fee_text`, `setup_fee_handling` | |
| Terms | `contract_period` + unit, `notice_periods` + unit, `fixation_periods`, `fixed_count`, `fixed_life_time_length`, `subscription_duration_type` | Model contract terms here, not in your code |
| Dunning | `dunning_plan` | Per plan; default plan otherwise |
| Renewal reminder | `renewal_reminder_email_days` | Needed for annual plans in many jurisdictions |

**Changing prices:** supersede the plan (`POST /v1/plan/{handle}` creates a
new version) or create a new plan. Existing subscriptions stay on their version
(`plan_version`) until changed deliberately.

## Changing a subscription

`PUT /v1/subscription/{handle}` with `timing` (required):

- `timing: "renewal"`: apply at next period. Use for downgrades.
- `timing: "immediate"`: apply now. Use for upgrades; choose `billing` for the
  remaining period: `prorated`, `full`, `zero_amount` or `none`, and optionally
  `compensation_method` (`prorated_credit`, `prorated_refund`, `full_credit`, …).
- Other fields: `plan`, `quantity`, `amount` (custom price), `add_ons`,
  `remove_add_ons` (by subscription add-on handle), `cancel_change` (drop a
  pending renewal change), `force_new_period`.

Use **Preview change subscription** to show the customer the price before
confirming.

## Usage and one-time charges

| Need | Use |
|---|---|
| Seats / licences | Quantity add-on (`type: quantity`) |
| Metered usage (API calls, kWh, GB) | **Usage-based billing product** (`POST /v1/metered_billing_product`), attach to subscription, report usage records (`…/metered_usage_record`) |
| One-time extra on next invoice | `POST /v1/additional_cost` `{ handle, subscription, amount, ordertext, quantity }` |
| Collect now | `POST /v1/charge` with the subscription's payment method, or "Create invoice on demand for subscription" |

## Discounts and coupons

`POST /v1/discount`: `handle`, `name`, `percentage` **or** `amount`, `apply_to`
(required: `all`, `plan`, `add_on`, `additional_cost`, `setup_fee`, …), and
duration via `fixed_count` (number of invoices) or `fixed_period` +
`fixed_period_unit`. Omit both for forever. Coupons (`POST /v1/coupon`) are
redeemable codes for a discount. Attach with `coupon_codes` or
`subscription_discounts` on create.

## Lifecycle

| Action | Call | Effect |
|---|---|---|
| Cancel at period end | `POST /v1/subscription/{h}/cancel` | `is_cancelled: true`; expires at period end (respecting notice periods); reversible with `/uncancel` |
| End now | `POST /v1/subscription/{h}/expire` | `state: expired` |
| Pause | `POST /v1/subscription/{h}/on_hold` | No invoicing while on hold |
| Resume | `POST /v1/subscription/{h}/reactivate` | Back to `active` |
| Change payment method | subscription session with `subscription`, or `POST /v1/subscription/{h}/pm` `{ source }` | Next invoice uses new method |

States: `pending`, `active`, `on_hold`, `expired`. Useful fields:
`next_period_start`, `current_period_start`, `is_cancelled`, `renewing`,
`pending_change`, `subscription_add_ons`. Gate access on state + latest invoice
outcome, not on "created" webhooks.

## Customer self-service

The **Frisbii Customer Portal** (plan feature) lets customers see
subscriptions and invoices and update payment methods. From your logged-in
area, create an SSO link: `POST https://customer-portal-api.reepay.com/v1/session`
`{ "email": "…" }` with the private key, then redirect to `redirect_url`.
Build custom UI on the API only for actions the portal does not cover.

## Failed renewals and dunning

- Configure **dunning plans** (retry schedule, reminder emails, final action).
  Soft declines (e.g. insufficient funds) are retried; irrecoverable ones need a
  new payment method.
- Handle: `invoice_failed`, `invoice_dunning`, `invoice_dunning_notification`,
  `invoice_settled` (recovered), `invoice_dunning_cancelled`,
  `subscription_on_hold_dunning`, `subscription_expired_dunning`.
- Decide access policy during dunning explicitly.
- Send customers to a payment-method update (portal or subscription session),
  or let them pay the failed invoice via a charge session with `invoice`.
- Test with CVV `100`–`302` on the test account (first/second/random payment failures).

## Common subscription pitfalls

1. A cron job that creates renewal charges instead of using subscriptions.
2. Granting access on `subscription_created` before the first invoice settles.
3. Editing live plan prices instead of superseding.
4. Forgetting `remove_add_ons` when downgrading.
5. Not handling `subscription_expired` / `_dunning` (customer keeps access).
6. Relying on the `amount_incl_vat` default (true) by accident.
