# Webhook event catalogue

Verified against <https://docs.frisbii.com/reference/event> and the API (October
2026); the two reminder events are not in the event reference yet. Not every
event generates a webhook by default: select events in the webhook settings,
spelled out in full. Events can also be listed with `GET /v1/event` for
reconciliation.

## Invoice events (charges and subscription invoices)

| Event | Meaning | Typical action |
|---|---|---|
| `invoice_created` | Invoice created | Usually informational |
| `invoice_authorized` | Payment authorised, not settled | Reserve stock; settle on shipment |
| `invoice_settled` | Payment captured: invoice paid | Fulfil / grant or extend access |
| `invoice_failed` | Failed (may later be authorised, settled, cancelled or fail again) | Notify; check dunning |
| `invoice_cancelled` | Cancelled | Release reservation |
| `invoice_reactivate` | Failed/cancelled invoice back to pending | Re-open order |
| `invoice_changed` | Attributes changed without state change | Re-fetch |
| `invoice_refund` | Refund performed | Update order / accounting |
| `invoice_refund_failed` | Asynchronous refund failed | Alert ops |
| `invoice_credited` | Credit note + subscription credit created | Accounting |
| `invoice_dunning` | Entered dunning | Start dunning UX |
| `invoice_dunning_notification` | Time to send a dunning notification per plan | Own notification if not using Frisbii emails |
| `invoice_dunning_cancelled` | Dunning stopped (settled or cancelled) | Clear dunning flags |
| `invoice_dispute_opened` / `_waiting_for_response` / `_under_review` / `_resolved` | Chargeback/dispute lifecycle | Provide evidence; adjust access |
| `sepa_chargeback_processed` | SEPA chargeback being retried (with SEPA chargeback handling enabled) | Informational |

## Subscription events

| Event | Meaning |
|---|---|
| `subscription_created` | Created (not necessarily paid) |
| `subscription_payment_method_added` | First payment method added |
| `subscription_payment_method_changed` | Payment method replaced |
| `subscription_trial_end_reminder` | Trial ends soon; sent `trial_reminder_email_days` before, when the plan sets it |
| `subscription_trial_end` | Trial ended |
| `subscription_renewal_reminder` | Renewal is coming up; sent `renewal_reminder_email_days` before, when the plan sets it |
| `subscription_renewal` | Invoice made and new period started |
| `subscription_changed` | Scheduling or pricing changed |
| `subscription_cancelled` | Cancelled to expire at end of period |
| `subscription_uncancelled` | Cancellation withdrawn |
| `subscription_on_hold` | On hold by request |
| `subscription_on_hold_dunning` | On hold after failed dunning |
| `subscription_reactivated` | Back to active |
| `subscription_expired` | Expired (request, fixed life time, or cancelled period ended) |
| `subscription_expired_dunning` | Expired after failed dunning |

## Customer events

| Event | Meaning |
|---|---|
| `customer_created` / `customer_changed` / `customer_deleted` | Customer lifecycle |
| `customer_payment_method_added` | Payment method saved (`payment_method`, `payment_method_reference` included) |
| `customer_payment_method_updated` | e.g. network token updated with new expiry |
| `customer_payment_method_failed` | Method failed; do not use again. Also sent when the customer revokes a wallet agreement (e.g. Vipps MobilePay) in their app |
| `customer_payment_method_reactivated` | Failed method active again |
| `customer_payment_method_deleted` | Method deleted |

## Payouts and settlements

`payout_created`, `payout_paid`, `payout_failed`, `settlement_data_updated`.
`settlement_data_updated` is account-level and carries no `customer`.
