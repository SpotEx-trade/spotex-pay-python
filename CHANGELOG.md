# Changelog

## 0.1.1 (2026-10-28)

- Webhook verification refuses an empty or missing signing secret instead of checking against an empty key, which anyone can sign with. This happens when `SPOTEX_WEBHOOK_SECRET` is set but empty.

## 0.1.0 (2026-10-27)

- First release: checkout sessions, checkouts (with test-mode simulate), coins, balance, payouts, and webhook verification.
