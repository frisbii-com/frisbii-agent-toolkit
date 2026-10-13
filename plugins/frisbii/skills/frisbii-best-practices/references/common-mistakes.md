# Common Frisbii integration mistakes

> **Maintainers:** this list is seeded from general platform knowledge. Replace
> and re-rank it using real integration tickets (Intercom / Salesforce cases
> tagged as integration issues). The value of this skill comes from knowledge
> an agent cannot get from the public docs.

| # | Mistake | Symptom | Fix |
|---|---|---|---|
| 1 | Treating the `accept_url` redirect as payment confirmation | Orders marked paid that were never paid; forged query strings | Confirm via verified webhook (`invoice_authorized` / `invoice_settled`) or `GET /v1/charge/{handle}` server-side |
| 2 | No webhook signature verification | Anyone can POST fake "paid" events | HMAC-SHA256 verification with constant-time compare (see `frisbii-webhooks`) |
| 3 | Non-deterministic charge handles | Double charges on retry / double click | Handle = your order ID; retries reuse it |
| 4 | Floats for money, wrong minor units | Off-by-one-cent totals, 100× over/under charges | Integers in minor units end to end |
| 5 | Test keys / secrets / plan handles hard-coded | Production charges hit the test account or fail | All per-environment values in config; go-live review |
| 6 | Slow webhook handlers doing all work inline | Timeouts → retries → duplicate processing | Ack fast, queue, process idempotently |
| 7 | Assuming webhook order | `settled` processed before `authorized`, state goes backwards | Fetch current object state on each event; never derive state from event order |
| 8 | Creating renewal charges with a cron job | Duplicate or missed renewals, broken dunning | Use Billing subscriptions; let the platform invoice |
| 9 | Settling physical goods at checkout | Refund churn for out-of-stock orders | Authorise at checkout, settle on shipment |
| 10 | Ignoring `invoice_failed` / dunning events | Customers keep access after failed payment, or lose it without notice | Handle dunning + `subscription_on_hold` / `subscription_expired` explicitly |
| 11 | Editing a live plan's price in place | Existing customers silently repriced or confused | New plan / plan version, migrate deliberately |
| 12 | Private key in frontend code | Key leak; full account access | Server-side only; rotate immediately if leaked |
