# Stripe → Frisbii webhook event mapping

Frisbii payloads carry references (`invoice`, `subscription`, `customer`), not
objects. Fetch the object after verifying the signature.

| Stripe event | Frisbii event(s) | Notes |
|---|---|---|
| `checkout.session.completed` | `invoice_authorized` / `invoice_settled` (charge), `customer_payment_method_added` (recurring) | Do not rely on the accept redirect |
| `payment_intent.succeeded` | `invoice_settled` | |
| `payment_intent.amount_capturable_updated` | `invoice_authorized` | |
| `payment_intent.payment_failed` | `invoice_failed` | |
| `payment_intent.canceled` | `invoice_cancelled` | |
| `charge.refunded` | `invoice_refund` (`invoice_refund_failed` for async failures) | |
| `charge.dispute.*` | `invoice_dispute_opened/_waiting_for_response/_under_review/_resolved` | |
| `setup_intent.succeeded` | `customer_payment_method_added` | |
| `customer.created/updated/deleted` | `customer_created/changed/deleted` | |
| `customer.subscription.created` | `subscription_created` | Not paid yet: wait for `invoice_settled` |
| `customer.subscription.updated` | `subscription_changed`, `subscription_cancelled`, `subscription_uncancelled`, `subscription_on_hold`, `subscription_reactivated` | Frisbii splits Stripe's catch-all update |
| `customer.subscription.deleted` | `subscription_expired` (+ `_dunning` variant) | |
| `customer.subscription.trial_will_end` | none (`subscription_trial_end` fires at the end) | Use plan `trial_reminder_email_days` or your own scheduler |
| `invoice.created` | `invoice_created` | |
| `invoice.paid` / `invoice.payment_succeeded` | `invoice_settled` | |
| `invoice.payment_failed` | `invoice_failed`, `invoice_dunning` | |
| `invoice.upcoming` | none (`subscription_renewal` fires at renewal) | Use plan `renewal_reminder_email_days` or your own scheduler |
| `payment_method.attached` / `.updated` / `.detached` | `customer_payment_method_added` / `_updated` / `_deleted` | |
