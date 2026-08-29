Status: delivered

================================================================
TICKET S9-05 — Billing UI
================================================================

WHAT TO BUILD:
- A simple Settings section: current plan, upgrade button
  (when free), cancel/manage button (when paid, likely via
  Stripe's customer portal rather than building a custom one —
  recommend this, justify)
- This UI is visible regardless of the kill switch state, but
  should say something sensible if billing isn't active yet —
  your call on exact copy, keep it honest (e.g. don't show an
  "Upgrade" button that leads nowhere useful while the kill
  switch is off)

ACCEPTANCE CRITERIA:
- Real UI, functional upgrade → real checkout → real return
  flow (test mode)
- Real cancel/manage flow via Stripe's portal (or justified
  custom alternative)
- Sensible, honest state when kill switch is off — real
  screenshot of both states
- Any deferred finding gets its own standalone ledger entry,
  per the now-consistent pattern

WHEN DONE:
- Real UI evidence, both kill-switch states
- Full upgrade/cancel flow evidence
- Do not start S9-06 until confirmed

================================================================
WHEN DONE (2026-08-29)
================================================================

**Recommendation, as asked:** Stripe's Customer Portal, not a custom
cancel/manage UI. Justification: it already handles payment-method
updates, invoice history, and cancellation with Stripe's own compliance
and fraud tooling built in — a custom UI would mean reimplementing all
of that (and staying in sync with it) for a two-tier product with exactly
one paid plan, for no real benefit over redirecting to a page Stripe
already maintains.

**Real UI evidence, both kill-switch states** (screenshots taken live
against the real dev backend, the real throwaway S9-03 test account —
sent to Borys directly in-session, not committed to this repo, matching
this project's practice of keeping real account/UI screenshots out of
version control):

1. Kill switch off, free tier — honest copy, no button:
   `1-billing-off-free-tier.jpg`
2. Kill switch on, free tier — real "Upgrade to Mymble Pro" button:
   `2-billing-on-free-tier-upgrade-button.jpg`

**Full upgrade → real checkout → real return flow:**

3. Clicked "Upgrade to Mymble Pro" → real Stripe-hosted Checkout Session
   (test mode badge visible, €9.99/month matching S9-01's real Price) →
   paid with Stripe's real `4242 4242 4242 4242` test card in a real
   browser → real redirect to `/billing/success` ("You're on Mymble Pro.
   Welcome aboard.") → clicked back to Settings → plan now reads "Mymble
   Pro" with a real "Manage subscription" button:
   `3-after-real-checkout-mymble-pro.jpg`

**Full cancel/manage flow via Stripe's real portal:**

4. Clicked "Manage subscription" → a real Stripe Customer Portal session
   (headline "Mymble Pro subscription management," matching the
   configuration this ticket created) showing the real payment method
   (Visa •••4242) and real paid invoice (€9.99, "Mymble Pro"):
   `4-real-stripe-portal.jpg`
5. Clicked "Отменить подписку" (Cancel subscription) → confirmed real
   scheduled cancellation ("Будет отменено 29 сент." — will be canceled
   Sept 29) → real webhook delivered and applied (see below).

**Kill switch flipped back off, same paid user, "Manage subscription"
still shown** — the deliberate design decision that access to your own
real billing must not depend on the kill switch:
`5-billing-off-still-manage-subscription.jpg`

**Real webhook evidence for the portal cancellation**, via `stripe
listen`:

    2026-08-29 14:02:34   --> customer.subscription.updated [evt_1U9kxx...]
    2026-08-29 14:02:34  <--  [200] POST http://localhost:8000/api/billing/webhook

Database state after: `tier=paid`, `status=active`,
`current_period_end=2026-09-29 11:59:44+00` — correct, not a bug: a
portal cancellation defaults to `cancel_at_period_end`, so the
subscription genuinely remains active until then. Logged as its own
ledger entry that this app's own UI doesn't yet surface "scheduled to
cancel" (Stripe's portal already tells the user directly, so non-blocking
today).

**A real premise-check finding, fixed before any of the above could
work:** this Stripe test-mode account had no Customer Portal
configuration at all — `billing_portal.sessions.create` fails outright
without one. `scripts/create_stripe_portal_configuration.py` (mirroring
S9-01's `create_stripe_products.py` pattern) created the real one now in
use (`bpc_1U9km2PEsUgc23Df0ik0gKkA`, confirmed `is_default=true`).

Full backend suite: 184/184 passing (176 pre-existing + 8 new:
`tests/test_billing_status_portal.py`). Frontend: `tsc -b` and `oxlint`
both clean on every changed/new file.

KEY DECISIONS

- "Manage subscription" is available regardless of the kill switch;
  "Upgrade" is not → a real paying customer must always be able to reach
  their own real Stripe subscription to cancel it — gating that on
  `BILLING_ENABLED` would mean turning the kill switch off (the
  production default) traps anyone who's already paying. "Upgrade" is
  the one gated on it, per the ticket's explicit instruction not to show
  a button that leads nowhere.
- `POST /api/billing/checkout` never wrote to the database (S9-03's
  decision); the same held here — nothing about the Billing UI needed
  it to change.
- `GET /api/billing/status` is a new, small read endpoint rather than
  reusing `GET /api/auth/me` or embedding tier in the user object →
  keeps billing state a separate concern the frontend fetches
  independently, matching how `useSettings`/`useCurrentUser` are already
  split rather than one large "everything about the user" query.

WATCH OUT FOR

- The real throwaway S9-03 test account now has an active-until-2026-09-29
  Stripe test subscription scheduled to cancel, plus the same leftover
  `usage_events` rows from S9-04's evidence — all inert test-mode data,
  same disposition as previously flagged (real users/transactions
  confirmed unaffected throughout). Still not deleted, for the same
  reason as before — flagging for Borys rather than acting unilaterally
  on real data.
- New standalone ledger entry: this app's own Settings UI doesn't yet
  show a pending/scheduled cancellation, only Stripe's portal does — see
  `docs/verification_debt.md`.

HOW IT CONNECTS

This is the first ticket in Sprint 9 a real user would actually see —
everything from S9-01 through S9-04 was plumbing invisible in the UI.
`BillingSection` is the single place all four prior tickets' work becomes
observable: S9-01's price and kill switch, S9-02's tier read, S9-03's
checkout/webhook/now-portal, S9-04's usage-cap messaging a user would
see right after clicking "Upgrade" here. S9-06 (Sprint 9 close) is what
verifies all of this together, end to end, one more time before this
sprint is considered done.

Ready for S9-06 whenever you confirm this one.

Do not start S9-06 until confirmed.
