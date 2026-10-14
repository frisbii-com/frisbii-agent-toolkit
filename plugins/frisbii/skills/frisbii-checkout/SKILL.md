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
| Pay an existing invoice | `POST /session/charge` with `invoice` | e.g. a failed subscription invoice |
| Only save a method | `POST /session/recurring` | `customer` or `create_customer` |
| Subscription signup in one step | `POST /session/subscription` with `prepare_subscription` | creates the subscription when the customer completes checkout |
| Add/change the method on an existing subscription | `POST /session/subscription` with `subscription` | |

Useful options on all sessions: `payment_methods`, `locale` (`da_DK`, `en_GB`,
`de_DE`, …), `ttl` (session expiry), `accept_url`, `cancel_url`, `phone`
(prefills MobilePay/Vipps/Swish), `configuration` (admin-defined look),
`card_on_file` (pay with a saved `ca_…`), `text_on_statement`.

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
  // choose one (charge/recurring sessions):
  const rp = new Reepay.EmbeddedCheckout(sessionId, { html_element: "rp_container" });
  // const rp = new Reepay.ModalCheckout(sessionId);   // overlay
  // const rp = new Reepay.WindowCheckout(sessionId);  // full-page redirect
  // subscription sessions: Reepay.EmbeddedSubscription / Reepay.ModalSubscription

  rp.addEventHandler(Reepay.Event.Accept, (data) => {
    // UX only. Tell your server to confirm the payment server-side.
  });
  rp.addEventHandler(Reepay.Event.Error, (data) => { /* show retry */ });
  rp.addEventHandler(Reepay.Event.Close, () => { /* customer closed */ });
  // Modal also fires Reepay.Event.Cancel
</script>
```

The JS namespace is still `Reepay` after the rebrand. Options include
`showReceipt: false`. Mobile apps: see "Checkout Native/Hybrid App
Integration" in the docs.

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
| Charge a saved method (MIT) | `POST /v1/charge` `{ handle, key, amount, currency, customer_handle, source: "ca_…", settle }` |

Always send the idempotency `key` on `POST /v1/charge` and retry network
errors / 5xx with the same `key` + `handle`.

## Payment methods by market

`payment_methods` takes IDs from "Checkout Payment Methods" in the docs. Omit
it to show everything the account has configured. Recurring-capable methods
(usable for subscriptions and saved-method charges):

`card` (and specific schemes: `visa`, `mc`, `dankort`, `amex`, `maestro`, …),
`applepay`, `googlepay`, `paypal`, `sepa`, `vipps_recurring`, `twint`,
`klarna` (unified), `offline_bank_transfer`, `offline_cash`, `offline_other`.

Single-payment only: `mobilepay` (MobilePay Online), `vipps`,
`vipps_epayment`, `swish`, `viabill`, `anyday`, `ideal`, `bancontact`,
`blik_oc`, `p24`, `eps`, `trustly`, `verkkopankki`, `mb_way`, `multibanco`,
`satispay`, `wechatpay`, `klarna_pay_now`, `klarna_pay_later`, …

| Market | Typical set |
|---|---|
| Denmark | `card` (incl. Dankort), `mobilepay` (one-off) / `vipps_recurring` (Vipps MobilePay recurring), `applepay`, `googlepay` |
| Norway | `card`, `vipps` / `vipps_epayment`, `vipps_recurring` |
| Sweden | `card`, `swish` (one-off), `klarna` |
| Finland | `card`, `mobilepay`, `verkkopankki` |
| Germany / Austria | `card`, `sepa`, `paypal`, `klarna`, `applepay`, `googlepay`, `eps` (AT) |
| Netherlands / Belgium | `card`, `ideal` / `bancontact`, `sepa` |
| Switzerland | `card`, `twint`, `postfinance` |
| Poland | `card`, `blik_oc`, `p24` |

Availability depends on the merchant's agreements. Check with the account's
configuration rather than assuming every ID is enabled.

## SCA / 3-D Secure

- Customer-initiated payments in Checkout get SCA automatically. Pass
  `sca_data` (customer email, address, …) to reduce challenges.
- Saved-method charges and subscription renewals are merchant-initiated; the
  platform flags them. If an issuer still demands authentication
  (`transaction_error` such as `sca_required`), bring the customer back
  through Checkout (e.g. charge session with `invoice`) instead of retrying.

## Testing

Use the test account. Visa `4111 1111 1111 1111`, any future expiry. CVV `888`
plus amounts trigger charge errors (`2001` insufficient funds, `3001` expired,
`1337` SCA required), and CVV `001`–`006` make saving a card fail (see
`frisbii-best-practices` references). Test at least: success, decline, 3DS,
customer cancel, closing the tab after paying (webhook-only confirmation), and
a duplicate click on "Pay".
