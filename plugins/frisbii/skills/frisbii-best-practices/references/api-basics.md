# Frisbii Billing & Pay API basics

Source of truth: <https://docs.frisbii.com/> (index for agents:
<https://docs.frisbii.com/llms.txt>; append `.md` to any docs/reference URL to
get Markdown). Verified against the docs in October 2026.

## Request shape

```bash
curl -u "$FRISBII_PRIVATE_KEY:" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  https://api.frisbii.com/v1/customer/cust-42
```

- HTTPS only. Basic auth: private key as username, empty password (note the trailing `:`).
- JSON bodies and responses. Unknown response fields must be ignored. New ones are added over time.
- Dates: `yyyy-MM-dd`, `yyyyMMdd`, `yyyy-MM-ddTHH:mm`, `yyyy-MM-ddTHH:mm:ss`;
  responses use ISO-8601 with offset. List-query dates are in the account time zone.

## Hosts

| Purpose | Host |
|---|---|
| Core API | `https://api.frisbii.com/v1` (legacy: `https://api.reepay.com/v1`) |
| Checkout API (sessions) | `https://checkout-api.frisbii.com/v1` (legacy: `checkout-api.reepay.com`) |
| Checkout JS | `https://checkout.frisbii.com/checkout.js` |
| Customer Portal API (SSO) | `https://customer-portal-api.frisbii.com/v1/session` (legacy: `customer-portal-api.reepay.com`) |
| Admin | `https://app.frisbii.com` |

## Core objects

| Object | Handle / id | Endpoints |
|---|---|---|
| Account | n/a | `GET /v1/account` → `handle`, `name`, `state` (`test`/`live`/`closed`) |
| Customer | `cust-42` | `POST /v1/customer`, `GET/PUT /v1/customer/{handle}`, `GET /v1/list/customer` |
| Payment method | `ca_…` (card), `ar_…` (Apple Pay), `gr_…` (Google Pay), other ids per type | `GET /v1/payment_method/{id}`; imports: `POST /v1/payment_method/import_sepa`, `/import_paypal`, `/import_klarna`, …; offline: `POST /v1/payment_method/offline` |
| Charge (one-off invoice) | `order-1001` | `POST /v1/charge`, `GET /v1/charge/{handle}`, `POST /v1/charge/{handle}/settle`, `/cancel` |
| Refund | n/a | `POST /v1/refund` (`invoice`, `amount`) |
| Plan | `plan-pro-monthly` | `POST /v1/plan`, `GET /v1/plan/{handle}/current` (the current version), `GET /v1/plan/{handle}` (a **list** of every version, newest first), supersede (new version): `POST /v1/plan/{handle}` |
| Subscription | `sub-42` | `POST /v1/subscription`, `GET/PUT /v1/subscription/{handle}`, `/cancel`, `/uncancel`, `/expire`, `/on_hold`, `/reactivate`, `POST /v1/subscription/{handle}/pm` |
| Add-on | `addon-seat` | `POST /v1/add_on` (`type`: `on_off` / `quantity`; send `currency`, which otherwise defaults to the account currency, not the plans') |
| Additional cost | `ac-…` | `POST /v1/additional_cost` (`subscription`, `amount`, `ordertext`, `handle`) |
| Usage-based billing product | handle | `POST /v1/metered_billing_product`; attach: `POST /v1/subscription/{handle}/metered_billing_product`; report: `POST /v1/subscription/{handle}/metered_billing_product/{product}/metered_usage_record` |
| Discount | `disc-10pct` | `POST /v1/discount` (`apply_to` required) |
| Coupon | code | `POST /v1/coupon` |
| Dunning plan | handle | `POST /v1/dunning_plan` |
| Invoice | `inv-<n>` for subscription invoices, your handle for charges | `GET /v1/invoice/{id}`, `GET /v1/list/invoice` |
| Checkout session | `cs_…` | `POST {checkout-api}/v1/session/charge`, `/session/recurring`, `/session/subscription` |

## Charge lifecycle

`created → authorized → settled`, or `→ failed`, or `authorized → cancelled`.
Asynchronous methods can return `pending` first; the outcome then arrives by
webhook. Refunds act on settled invoices and can be partial. Authorisations expire
after a window that depends on payment method, scheme and acquirer, so settle
physical-goods orders promptly.

Create charge and settle answer HTTP 200 also when the payment is declined:
check `state`, `error_state` (`soft_declined`, `hard_declined`,
`processing_error`) and `error` in the response, not only the HTTP status.

## Idempotency

1. **Handles**: one authorisation/settle per charge handle; one object per
   customer/subscription/plan handle.
2. **`key`**: optional idempotency key in the body of `POST /v1/charge`, settle
   and refund. Same `key` + `handle` → same result, so network-error retries are
   safe. The stored result includes a decline; retry a declined charge with the
   same handle and a **new** `key`.
3. **Changed basket**: re-sending a charge handle with different order lines
   replaces the lines of a charge that is not yet paid (`created` or `failed`).
   On an authorised or settled charge the call fails (`code` 105 or 79). Use a new
   handle when the basket changes.

## Errors

```json
{
  "code": 13,
  "error": "Subscription expired",
  "http_reason": "Bad Request",
  "http_status": 400,
  "path": "/v1/subscription/WHBBv/expire",
  "timestamp": "2015-06-12T06:38:33.876+0000",
  "request_id": "de03e86d0a6d44359b249340f967ddc9"
}
```

The id is `request_id` in the body of both the Core and the Checkout API, and
also sent as the `request-id` response header. Failed payment operations can add
`transaction_error` (e.g. `credit_card_expired`).

| Status | Meaning | Action |
|---|---|---|
| 400 / 404 / 422 | Illegal operation / not found / bad parameters (422 has a `message` but no `code`) | Fix the request; do not retry unchanged |
| 400, `code` 1 | Malformed `Authorization` header, e.g. `Bearer` instead of Basic | Use Basic auth |
| 401, `code` 6 | Unknown API key | Check the key and the account |
| 403, `code` 7 | No credentials, or the key lacks permission for the operation | Send the key; check its permissions |
| 429 | `code` 122 rate limit, `code` 123 concurrency limit | Back off, reduce parallelism |
| 5xx / no response | Platform or acquirer issue | Retry with back-off (with `key` for charges) |

Example: attaching an add-on in another currency than the subscription returns
`400`, `code` 154, `"Currency mismatch"`, `message`
`"addon currency is not matching subscription currency"`.

Error code list: <https://api.frisbii.com/v1/error_codes>.

## Lists

`GET /v1/list/{resource}?range=created&from=…&to=…&size=100&next_page_token=…`
Page size 10–100 (default 20); keep all parameters identical when paging. For
targeted queries and occasional bulk pulls, not for change detection.

## Test account

- Separate account, keys, webhook secret, catalogue. `GET /v1/account` → `state: test`.
- Test cards (any future expiry): Visa `4111 1111 1111 1111`, Mastercard
  `5500 0000 0000 0004`, Dankort `5019 1000 0000 0006`, Visa-DK `4571 9940 0006 2336`
  (full list in the reference "Testing" page).
- CVV codes drive scenarios: `001`–`006` fail saving a card; `100`–`302`
  fail first/second/random subscription payments (recoverable vs irrecoverable);
  CVV `888` + specific amounts trigger charge errors (e.g. amount `2001`
  insufficient funds, `1337` SCA required); `401`–`405` refund errors.
- Webhooks on test accounts are retried for 24 hours only; test customers older
  than three months are deleted.
