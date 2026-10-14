# Stripe → Frisbii field mapping

> Frisbii field names verified against <https://docs.frisbii.com/> (October 2026).

## Customer

| Stripe | Frisbii | Notes |
|---|---|---|
| `id` (`cus_…`) | `handle` | Prefer your own user id; keep Stripe id in your DB during transition |
| `email` | `email` | |
| `name` | `first_name` / `last_name` or `company` | Split or use company for B2B |
| `phone` | `phone` | |
| `address.line1/line2` | `address` / `address2` | |
| `address.city/postal_code/country` | `city` / `postal_code` / `country` | ISO country code |
| `tax_ids[0].value` | `vat` | |
| `metadata` | `metadata` | Keep small |

## Price → Plan

| Stripe | Frisbii plan | Notes |
|---|---|---|
| `id` (`price_…`) | `handle` | e.g. `plan-pro-monthly-eur` |
| `product.name` | `name` | |
| `unit_amount` | `amount` | Same minor units |
| `currency` | `currency` | Upper-case on Frisbii |
| `recurring.interval` + `interval_count` | `interval_length` + `schedule_type` | month → `month_startdate` (or `month_fixedday`); year → `interval_length: 12`; day → `daily`; week → `weekly_fixedday` + `schedule_fixed_day` |
| `tax_behavior` | `amount_incl_vat` (default true!) + `vat` or `tax_policy` | Decide once for the catalogue |
| `recurring.trial_period_days` / subscription `trial_end` | `trial_interval_length` + `trial_interval_unit` (`days`/`months`), or `trial_period` (ISO 8601) on the subscription | |

## Subscription

| Stripe | Frisbii | Notes |
|---|---|---|
| `id` (`sub_…`) | `handle` | `sub-<your id>` |
| `customer` | `customer` | handle |
| `items[0].price` | `plan` | via price → plan mapping |
| other `items[]` | `add_ons[]` | add-on handle + quantity |
| `quantity` | `quantity` | |
| `default_payment_method` | `source` (`ca_…`) | from card-import mapping |
| `current_period_end` | `start_date` (at migration) | Aligns first Frisbii invoice with next Stripe renewal |
| `trial_end` | trial / `start_date` | If in trial: `start_date` = trial end |
| `discount.coupon` | `subscription_discounts` / `coupon_codes` | |
| `cancel_at_period_end` | `/cancel` after create | Recreate the pending cancellation |
| `billing_cycle_anchor` | plan `schedule_type` + `schedule_fixed_day` | |
| `collection_method: send_invoice` | Offline payment method (`POST /v1/payment_method/offline`, e.g. `offline_bank_transfer`) as `source` | Requires an offline agreement on the account |

## Coupon / promotion code

| Stripe | Frisbii |
|---|---|
| Coupon `percent_off` / `amount_off` | Discount `percentage` / `amount` |
| `duration: once / repeating / forever` | `fixed_count: 1` / `fixed_period` + `fixed_period_unit` / omit both |
| Promotion code `code` | Coupon `code` → discount |
| `max_redemptions`, `redeem_by` | Coupon redemption limits / validity (see Create coupon) |
| `applies_to` | Discount `apply_to` (required: `all`, `plan`, `add_on`, …) |
