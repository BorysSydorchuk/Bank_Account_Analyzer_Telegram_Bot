Status: delivered

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

================================================================
WHEN DONE (2026-08-29)
================================================================

**Real Stripe object evidence:** created via
`scripts/create_stripe_products.py` against the real Stripe test-mode
API (StripeClient, not the deprecated global `stripe.api_key =` pattern
— corrected per the Stripe best-practices skill mid-ticket):

    [stripe] Product created — id=prod_V9tx2wdtpeQNpp name='Mymble Pro'
    [stripe] Price created   — id=price_1U9a9xPEsUgc23DfwIN1Jnzj amount=9.99 EUR/month

`STRIPE_PRICE_ID_PRO` recorded in `.env`/`.env.example`. Test-mode
confirmed defensively — the script refuses to run against anything not
prefixed `sk_test_`/`rk_test_`, so it cannot accidentally touch live mode.

**Confirmed free-vs-paid distinction:** paid tier = higher
`app/usage_limits.py` daily caps, not unlimited (Borys's call, keeps a
cost backstop even on a compromised paid account). Price: €9.99/month
(Borys's call). Purely usage-limit gating for v1, no other paid-only
feature. Full detail in ARCHITECTURE.md's new Billing section.

**Kill switch mechanism and default-off confirmation:** new `app_settings`
table (global, no `user_id` — kept separate from the per-user `settings`
table on purpose, see `app/models.py`'s `AppSetting` docstring), migration
`a2b6e91d4f37` applied for real:

    key              | value | updated_at
    BILLING_ENABLED  | false | 2026-08-29 00:33:25.969004+00

`app/billing.py`'s `is_billing_enabled(db)` proven live, not just by
code review:

    billing enabled (seeded false): False
    billing enabled (after flip to true): True
    billing enabled (flipped back to false): False
    unknown key default: false

Chosen over an env var because a settings-table row is flippable by
Borys with a direct SQL `UPDATE` against production — no new ECS task
definition revision, no deploy. Confirmed inert: nothing in the app
reads `is_billing_enabled` yet (S9-04 is what wires it into real
enforcement), so today's flag state has zero observable effect anywhere.
Regression test coverage added: `tests/test_billing.py` (3 new tests).
Full backend suite: 153/153 passing (150 pre-existing + 3 new).

**Flagged mid-ticket, now tracked as its own ledger entries (correction —
initially buried as prose here instead of a standalone entry, same
pattern as S8-05/S8-06/S8-08; see this ticket's AMENDMENT below):**
- `docs/verification_debt.md`: "Stripe key is a full secret key, not a
  scoped restricted key" — Stripe's best-practices skill recommends a
  restricted key (`rk_test_...`) over the full secret key Borys generated.
  Non-blocking in test mode; closes before live mode.
- `infra/ecs.tf`/`infra/web.tf` now declare Secrets Manager wiring for
  `STRIPE_SECRET_KEY` (matching the `RESEND_API_KEY` pattern), but the
  real AWS secret doesn't exist yet and `terraform apply` has not run —
  this environment has no AWS credentials. Logged as its own entry in
  `docs/verification_debt.md` ("Stripe secret key — Secrets Manager
  wiring committed but not applied to production"), explicitly calling
  out S8-05's own real incident (same category of gap: Terraform
  committed, never applied, silent prod `AccessDeniedException`) as the
  risk this must not repeat. Non-blocking today because nothing in
  production reads Stripe yet.
- ARCHITECTURE.md updated in this same commit (new `app_settings` table
  row, new Billing section) per the architecture-documentation rule —
  this ticket changed a table and added a new invariant (the kill
  switch's default-off/no-deploy-to-flip guarantee).

Do not start S9-02 until confirmed.

================================================================
AMENDMENT (2026-08-29) — RAK finding was buried in prose, corrected
================================================================
Borys caught, before confirming this ticket, that the restricted-API-key
recommendation above had been folded into a "Flagged mid-ticket, not
blocking" aside in this ticket's own WHEN DONE rather than given its own
standalone `docs/verification_debt.md` entry — the exact pattern already
named and supposedly fixed after S8-05/S8-06/S8-08. Given its own entry:
"Stripe key is a full secret key, not a scoped restricted key" (OPEN,
closes before live mode). See that session's response to this ticket for
the root-cause analysis of why the standing reminder didn't catch it a
fourth time.
