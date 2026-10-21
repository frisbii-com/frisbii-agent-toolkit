---
name: frisbii-checkout
description: Build payment collection with Frisbii Checkout (Frisbii Pay, formerly Reepay Checkout). Use when implementing a payment page, one-off charges, saving a card or wallet for later, subscription signup checkout, hosted vs embedded vs modal checkout, choosing payment methods by market (cards, MobilePay, Vipps, Swish, SEPA, Apple Pay, Google Pay, Klarna, PayPal and others), handling 3-D Secure / SCA, accept and cancel URLs, or settling and refunding payments.
---

# Frisbii Checkout

Read `frisbii-best-practices` first if you have not. It covers auth, test
accounts, handles and amounts. Reference: <https://docs.frisbii.com/docs/billwerk-checkout-1>.

## The flow (always the same shape)

1. **Server:** create a checkout **session** with the Checkout API. The session
   holds everything about the payment (amount, order lines, customer, allowed
   payment methods). The browser cannot change it, so no checksums are needed.
2. **Browser:** open the session (window, overlay/modal or embedded).
3. **Customer** pays; SCA / 3-D Secure is handled inside Checkout.
4. **Browser** gets the Accept event or is sent to `accept_url` / `cancel_url`.
   Treat this as UX only.
5. **Server:** confirm via a verified webhook and/or `GET /v1/charge/{handle}`,
   then fulfil.

## Which session?

All at `https://checkout-api.frisbii.com/v1/…`, authenticated with the private key.

| Goal | Endpoint | Key fields |
|---|---|---|
| Take a payment | `POST /session/charge` | `order` (`handle`, `currency`, `customer` or `customer_handle`, `order_lines` or `amount`), `settle` |
| Take a payment **and** save the method | same, `recurring: true` (or `recurring_optional: true` to let the customer choose) | saved method is returned/announced via webhook |
| Pay an existing invoice | `POST /session/charge` with `invoice` | Pays the invoice only; it does not change a subscription's payment method |
| Only save a method | `POST /session/recurring` | `customer` or `create_customer` |
| Subscription signup in one step | `POST /session/subscription` with `prepare_subscription` | Creates a **pending** subscription when the session is created; it becomes active when the customer completes checkout. Creating a second session with the same subscription handle fails with a duplicate handle error |
| Add/change the method on an existing subscription | `POST /session/subscription` with `subscription` | Also pays the subscription's outstanding invoice, so this is the session for a failed renewal |

Useful options on all sessions: `payment_methods`, `locale` (`da_DK`, `en_GB`,
`de_DE`, …), `ttl` (session expiry, default three months), `accept_url`,
`cancel_url`, `phone` (prefills MobilePay/Vipps/Swish), `configuration`
(admin-defined look), `card_on_file` (pay with a saved card, `ca_…`),
`show_terms`, and `session_data.alternative_return_url` for native apps.
Charge sessions also take `text_on_statement`; other session types ignore it.
End a session early with `DELETE /v1/session/{id}`.

### Charge session example

```json
POST https://checkout-api.frisbii.com/v1/session/charge
{
  "order": {
    "handle": "order-1001",
    "currency": "DKK",
    "customer": { "handle": "cust-42", "email": "jane@example.com" },
    "order_lines": [
      { "ordertext": "T-shirt", "amount": 19900, "quantity": 2, "vat": 0.25, "amount_incl_vat": true }
    ]
  },
  "settle": false,
  "accept_url": "https://shop.example.com/checkout/accept",
  "cancel_url": "https://shop.example.com/checkout/cancel",
  "locale": "da_DK"
}
```

Response contains the session `id` (`cs_…`) and a hosted `url`.

- `order.handle` = your order ID. It becomes the invoice handle and makes
  retries safe. Never randomise it.
- Prefer `order_lines` (better receipts, VAT reporting, required by Klarna) over
  `amount` + `ordertext`.

## Opening the session

```html
<script src="https://checkout.frisbii.com/checkout.js"></script>
<div id="rp_container"></div>
<script>
  // Embedded or modal (charge/recurring sessions):
  const rp = new Reepay.EmbeddedCheckout(sessionId, { html_element: "rp_container" });
  // const rp = new Reepay.ModalCheckout(sessionId);   // overlay
  // subscription sessions: Reepay.EmbeddedSubscription / Reepay.ModalSubscription

  rp.addEventHandler(Reepay.Event.Accept, (data) => {
    // UX only. Tell your server to confirm the payment server-side.
  });
  rp.addEventHandler(Reepay.Event.Error, (data) => { /* show retry */ });
  rp.addEventHandler(Reepay.Event.Cancel, (data) => { /* customer cancelled */ });
  rp.addEventHandler(Reepay.Event.Close, () => { /* customer closed */ });
</script>
```

Window checkout has no events: `new Reepay.WindowCheckout(sessionId)` (or a
redirect to the session `url`) navigates away at once, and the result comes
back through `accept_url` / `cancel_url`. Do not call `addEventHandler` on it.

The JS namespace is still `Reepay` after the rebrand. Options include
`showReceipt: false` and, for Apple Pay in embedded/modal checkout, `domainName`
(see "Apple Pay" in the docs: the domain must also be registered on the Apple
Pay agreement in the Frisbii admin, with Apple's domain-verification file
hosted on it). Even with events, set `accept_url` and `cancel_url`: on mobile,
app-switch methods such as MobilePay return through them.

**Give the embedded container a definite height.** The embedded checkout sizes its
iframe at `height: 100%` of `html_element`. A container with only `min-height` (or no
height) collapses the iframe to the browser default of 150px and hides the card form.
Set e.g. `#rp_container { height: 780px; }` (the card form is about 700px tall).

Checkout can show a "terms and conditions" checkbox and keep the button disabled
until it is ticked. By default it is shown in subscription sessions for a
subscription without a payment method, when the account or the checkout
configuration has terms. `show_terms` overrides the default on any session type.
Expect it in test scripts; set `show_terms: false` only when your own signup
already collects acceptance.

Mobile apps: follow "Checkout Native App Integration" in the docs (a WebView with
the Native Bridge, and `session_data.alternative_return_url` set to the app's URL
scheme) or "Checkout Hybrid App Integration". Do not send
`alternative_return_url` as an empty string.

| Mode | Use when |
|---|---|
| **Embedded** | Payment form inside your page; best for web apps |
| **Overlay / modal** | On top of your page; minimal layout work |
| **Window** (or redirect to session `url`) | Simplest; payment links by email/SMS; no third-party JS |

## Confirming the payment

Never fulfil from the Accept event or `accept_url` query string. Instead:

```text
GET https://api.frisbii.com/v1/charge/{order handle}
→ state "authorized" (settle later) or "settled" (paid)
```

and/or handle `invoice_authorized` / `invoice_settled` webhooks
(`frisbii-webhooks`). Make fulfilment idempotent on the order handle. The
browser callback and the webhook will both arrive.

## Settle, cancel, refund, charge saved methods

| Action | Call |
|---|---|
| Capture an authorisation (ship) | `POST /v1/charge/{handle}/settle` (optionally partial `amount`) |
| Release an authorisation | `POST /v1/charge/{handle}/cancel` |
| Refund a settled charge | `POST /v1/refund` `{ "invoice": "{handle}", "amount": 5000 }` |
| Charge a saved method (MIT, customer not present) | `POST /v1/charge` `{ handle, key, amount, currency, customer_handle, source, settle }` with `source` = the saved method's id (`ca_…` card, `ar_…` Apple Pay, `gr_…` Google Pay, …) |

Charge and settle answer HTTP 200 also when the payment is declined: check
`state` and `error_state` in the response. Always send the idempotency `key`
on `POST /v1/charge` and retry network errors / 5xx with the same `key` +
`handle`. A declined charge is replayed for the same `key`; to try again, keep
the handle and send a new `key`.

When the customer is present and pays with a saved card, use a charge session
with `card_on_file` instead of `POST /v1/charge`: that payment is
customer-initiated and needs SCA.

## Payment methods by market

`payment_methods` takes IDs from "Checkout Payment Methods" in the docs. Omit
it to use the list of the session's `configuration`, or everything the account
has configured. IDs that are misspelled or not enabled on the account are
dropped silently (the session only fails, with error 601, when none are
left), so check that the session shows what you expect. `mobilepay` and `vipps`
are shown as `vipps_epayment` when the account has a Vipps MobilePay ePayments
agreement.

Recurring-capable methods (usable for subscriptions and saved-method charges):

`card` (and specific schemes: `visa`, `mc`, `dankort`, `amex`, `maestro`, …),
`applepay`, `googlepay`, `paypal`, `sepa`, `vipps_recurring`, `twint`,
`klarna` (unified), `offline_bank_transfer`, `offline_cash`, `offline_other`.
PayPal and Google Pay are recurring only when the account's agreement supports
it.

Single-payment only: `mobilepay` (MobilePay Online), `vipps`,
`vipps_epayment`, `swish`, `viabill`, `anyday`, `ideal`, `bancontact`,
`blik_oc`, `p24`, `eps`, `trustly`, `verkkopankki`, `mb_way`, `multibanco`,
`satispay`, `wechatpay`, `klarna_pay_now`, `klarna_pay_later`, …

| Market | Typical set |
|---|---|
| Denmark | `card` (incl. Dankort), `vipps_epayment` (Vipps MobilePay, one-off) / `vipps_recurring` (Vipps MobilePay recurring), `applepay`, `googlepay` |
| Norway | `card`, `vipps_epayment`, `vipps_recurring` |
| Sweden | `card`, `swish` (one-off), `klarna` |
| Finland | `card`, `vipps_epayment`, `verkkopankki` |
| Germany / Austria | `card`, `sepa`, `paypal`, `klarna`, `applepay`, `googlepay`, `eps` (AT) |
| Netherlands / Belgium | `card`, `ideal` / `bancontact`, `sepa` |
| Switzerland | `card`, `twint`, `postfinance` |
| Poland | `card`, `blik_oc`, `p24` |

Availability depends on the merchant's agreements. Check with the account's
configuration rather than assuming every ID is enabled. SEPA Direct Debit comes
from several providers with different rules; see "SEPA Direct Debit" in the docs
(for example, SEPA via Stripe works only in Window Checkout).

## SCA / 3-D Secure

- Customer-initiated payments in Checkout get SCA (3-D Secure) when the card is
  enrolled; the admin can require it for all cards. Pass `sca_data` (customer
  email, address, …) to reduce challenges.
- Sessions that save a card for later merchant-initiated charges (recurring
  sessions, and charge sessions with `recurring`) always present a challenge.
- A customer who is present and pays with a saved card is customer-initiated
  too: use `card_on_file` in a charge session.
- Saved-method charges with the customer not present, and subscription
  renewals, are merchant-initiated; the platform flags them. If an issuer still
  demands authentication (`sca_required`), bring the customer back through
  Checkout instead of retrying: a subscription session with `subscription` for a
  subscription invoice (it also updates the payment method), or a charge session
  with `invoice` otherwise.

## Testing

Use the test account. Visa `4111 1111 1111 1111`, any future expiry. CVV `888`
plus amounts in minor units trigger charge errors (`2001` insufficient funds,
`3001` expired, `1337` SCA required, for payments without 3-D Secure), and CVV
`001`–`006` make saving a card fail (see
`frisbii-best-practices` references). Test at least: success, decline, 3DS,
customer cancel, closing the tab after paying (webhook-only confirmation), and
a duplicate click on "Pay".
