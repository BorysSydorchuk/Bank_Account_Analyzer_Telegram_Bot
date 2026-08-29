Status: plan
Source: issued directly in Claude Code session, 2026-08-29

---

================================================================
SPRINT 9 — "MONETIZATION INFRASTRUCTURE"
KBC Personal Finance Analyzer / Mymble
================================================================

SPRINT GOAL: Real Stripe billing, a simple free/paid tier
model, and tier-based feature gating all exist and are fully
tested — but billing enforcement stays OFF by default via a
global flag. Beta users are completely unaffected until Borys
deliberately flips the flag once the user base justifies it.
This sprint builds the plumbing, not the launch.

Sprint 8 is fully closed. Read ARCHITECTURE.md and
docs/verification_debt.md before starting.

DECISIONS ALREADY MADE:
- Pricing model: simple two-tier (free, paid) — not usage-based,
  not multiple paid tiers
- Billing stays OFF during beta — a global flag/setting gates
  all enforcement, default false
- S8-04's usage-cap infrastructure (per-action daily limits,
  usage_events table) is the natural foundation for what "free
  tier" vs "paid tier" actually means — reuse it, don't rebuild

PROCESS: commit this plan to docs/tickets/S9-00-sprint-plan.md
(Status: plan) before S9-01. Every ticket through Reviewer
review before confirmation, same as every prior sprint.

================================================================
TICKET S9-01 — Stripe Setup & Tier Model Design
================================================================

PRIORITY: Premise check and design first. This is external
integration touching real payments infrastructure — get the
model right before writing code against it.

WHAT TO BUILD:

Part 1 — Stripe account and product setup:
- Set up a real Stripe account (test mode) if not already done
- Create the Product and two Price objects: Free (or no Stripe
  price needed at all — a free tier may not need a Stripe
  object, your call, justify) and Paid (a real monthly price —
  Borys to confirm the actual price point before this is built,
  don't guess a number)
- Confirm Stripe API keys are sourced via Secrets Manager/IAM,
  same standard as every other credential this project has
  handled since S7-05

Part 2 — Define what "paid tier" actually changes:
- Concretely: which of S8-04's usage caps change for a paid
  user? (e.g., higher daily limits, or no limits at all —
  Borys's call, present the options)
- Any other paid-only feature to gate, or is it purely usage
  limits for this first version? (Recommend: purely usage
  limits for v1 — simpler, matches "simple two-tier" framing)

Part 3 — The kill switch:
- A global setting (env var or a real settings table row,
  your call) — e.g. BILLING_ENABLED, default false
- When false: every user behaves as unlimited/free regardless
  of any Stripe state — billing logic exists but enforces
  nothing
- This must be trivially flippable by Borys later without a
  code deploy if possible (a settings-table value is probably
  better than an env var for this reason — justify your choice)

ACCEPTANCE CRITERIA:
- Real Stripe test-mode account and products/prices created,
  real evidence (not screenshots described, actual API
  confirmation)
- Concrete free-vs-paid distinction defined and confirmed with
  Borys before Part 2 code lands elsewhere in the sprint
- Kill switch exists, defaults to off, confirmed to make
  billing fully inert when off

WHEN DONE:
- Real Stripe object evidence
- The confirmed free-vs-paid distinction
- Kill switch mechanism and default-off confirmation
- Do not start S9-02 until confirmed

================================================================
TICKET S9-02 — Subscription Schema & User-Tier Model
================================================================

WHAT TO BUILD:
- A subscriptions table (or equivalent): user_id, stripe
  customer/subscription IDs, current tier, status (active,
  canceled, past_due, etc.), relevant dates
- Every user defaults to "free" tier with no Stripe objects
  until they actually subscribe
- Nullable/optional fields for users who never touch billing —
  don't force a Stripe customer to exist for every user
  up front

ACCEPTANCE CRITERIA:
- Schema exists, migration applies cleanly (real evidence,
  same rigor as every prior migration this project has done)
- A user with no subscription history reads correctly as
  "free" tier
- No existing user/data disrupted by this addition

WHEN DONE:
- Real migration evidence
- Confirm existing users unaffected
- Do not start S9-03 until confirmed

================================================================
TICKET S9-03 — Stripe Checkout & Webhook Handling
================================================================

WHAT TO BUILD:
- A real Stripe Checkout flow: user clicks "Upgrade," lands on
  Stripe's real hosted checkout, completes a real test-mode
  payment, gets redirected back
- Webhook endpoint handling the real events that matter:
  checkout completed, subscription updated, subscription
  canceled, payment failed — update S9-02's schema accordingly
- Webhook signature verification (Stripe's standard mechanism)
  — this endpoint is public by necessity, verify Stripe is
  really who's calling it
- All of this works correctly regardless of the kill switch —
  the plumbing should be real and correct even while
  enforcement stays off

ACCEPTANCE CRITERIA:
- Real test-mode checkout completes end-to-end
- Webhook correctly updates subscription status for at least:
  successful subscribe, cancellation, failed payment
- Signature verification confirmed rejecting an unsigned/fake
  webhook call
- Real evidence throughout, same standard as every
  credential/payment-adjacent ticket this project has had

WHEN DONE:
- Real checkout completion evidence
- Real webhook handling evidence for each event type
- Signature verification rejection test
- Do not start S9-04 until confirmed

================================================================
TICKET S9-04 — Tier-Based Feature Gating
================================================================

WHAT TO BUILD:
- Wire S9-01 Part 2's defined free-vs-paid distinction into
  S8-04's actual usage-cap enforcement
- Gate check reads: kill switch (S9-01) → if off, always
  unlimited; if on, check user's real tier (S9-02) and apply
  the correct limit
- Clear user-facing messaging when a free-tier cap is hit that
  billing is on (different from S8-04's original generic
  message — this one should mention upgrading)

ACCEPTANCE CRITERIA:
- With the kill switch off: behavior is identical to Sprint
  8's current state, real regression test confirming this
- With the kill switch on (test environment only): free tier
  correctly capped, paid tier correctly gets the higher/no
  limit, real evidence for both

WHEN DONE:
- Kill-switch-off regression evidence (nothing changed)
- Kill-switch-on evidence for both tiers
- Do not start S9-05 until confirmed

================================================================
TICKET S9-05 — Billing UI
================================================================

WHAT TO BUILD:
- A simple Settings section: current plan, upgrade button
  (when free), cancel/manage button (when paid, likely via
  Stripe's customer portal rather than building a custom one —
  recommend this, justify)
- This UI is visible regardless of the kill switch state, but
  should probably say something sensible if billing isn't
  active yet — your call on exact copy, keep it honest

ACCEPTANCE CRITERIA:
- Real UI, functional upgrade → real checkout → real return
  flow
- Real cancel/manage flow via Stripe's portal (or justified
  custom alternative)
- Sensible state when kill switch is off

WHEN DONE:
- Real UI evidence, full flow
- Do not start S9-06 until confirmed

================================================================
TICKET S9-06 — Sprint 9 Close
================================================================

WHAT TO BUILD:
Full verification, same discipline as every sprint close.

ITEMS:
1. Full regression with kill switch OFF (the real production
   default) — confirm zero behavior change for any real beta
   user, this is the most important check in this ticket
2. Full regression with kill switch ON in a test environment —
   confirm the entire billing flow works end-to-end
3. ARCHITECTURE.md accuracy pass — billing model, kill switch,
   webhook handling, tier gating
4. Security spot-check: webhook signature verification holds,
   no way to self-grant paid tier without a real Stripe
   subscription, Stripe keys sourced correctly
5. Ledger final state, zero stale entries, full read-through

ACCEPTANCE CRITERIA:
- Kill-switch-off regression passes, zero real-user impact
  confirmed
- Kill-switch-on full billing flow passes
- ARCHITECTURE.md accurate
- Security spot-check passes
- Ledger current
- Sprint 9 complete pending PM confirmation

WHEN DONE:
- Both regression results
- Security spot-check results
- Sprint 9 complete pending PM confirmation
- Explicit reminder note: billing remains OFF; flipping it on
  is Borys's deliberate future action, not part of this sprint

================================================================
END OF SPRINT 9 TICKETS
================================================================
