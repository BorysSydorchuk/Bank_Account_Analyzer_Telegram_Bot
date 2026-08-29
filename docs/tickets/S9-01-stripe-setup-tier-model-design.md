Status: in-progress

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
AMENDMENT (2026-08-29) — decisions confirmed by Borys pre-build
================================================================
- Stripe account: does not exist yet — Borys needs to create it
  himself (identity/business signup can't be done on his behalf).
  Walking him through account + test-mode setup before any Product/
  Price objects can be created.
- Paid tier price point: €9.99/month.
- Paid tier usage-cap change (Part 2): higher daily limits, not
  unlimited — caps still apply at a higher threshold, per
  Recommended option (keeps a technical backstop against runaway
  LLM API cost even on a paid/compromised account).
