# Changelog

## 0.2.0 (2026-10-28)

- Prices in your own currency: `price=` with `currency=` (EUR, GBP, JPY and others) when creating checkout sessions and checkouts. `amount_usd` still works for dollars, positionally too.
- Checkouts carry `price`, `currency` and `currency_rate_usd`; checkout sessions carry `price` and `currency`, with `amount_usd` None for a price not in dollars.

## 0.1.1 (2026-10-28)

- Webhook verification refuses an empty or missing signing secret instead of checking against an empty key, which anyone can sign with. This happens when `SPOTEX_WEBHOOK_SECRET` is set but empty.

## 0.1.0 (2026-10-27)

- First release: checkout sessions, checkouts (with test-mode simulate), coins, balance, payouts, and webhook verification.
