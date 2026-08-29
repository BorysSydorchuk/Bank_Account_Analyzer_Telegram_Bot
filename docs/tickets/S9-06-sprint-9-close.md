Status: delivered

================================================================
TICKET S9-06 — Sprint 9 Close
================================================================

WHAT TO BUILD:
Full verification, same discipline as every sprint close.

ITEMS:
1. Log the success-page race condition from S9-05's review as
   its own standalone verification_debt.md entry, if not
   already done
2. Delete the accumulated s9-03-billing-test@example.com test
   account and its usage_events rows, if not already cleaned up
3. Full regression with kill switch OFF (the real production
   default) — confirm zero behavior change for any real beta
   user, this is the most important check in this ticket
4. Full regression with kill switch ON in a test environment —
   confirm the entire billing flow works end-to-end: checkout,
   webhook processing, tier gating, portal access
5. ARCHITECTURE.md accuracy pass — billing model, kill switch,
   webhook handling, tier gating, portal flow
6. Security spot-check: webhook signature verification holds,
   webhook rate limiting holds, no way to self-grant paid tier
   without a real Stripe subscription, Stripe keys sourced
   correctly, restricted-key ledger item still tracked
7. Ledger final state, zero stale entries, full read-through
   (not grep)

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
- Ledger state, explicit confirmation
- Sprint 9 complete pending PM confirmation
- Explicit reminder: billing remains OFF; flipping it on is
  Borys's deliberate future action, not part of this sprint

================================================================
WHEN DONE (2026-08-29)
================================================================

**Item 1 — race-condition ledger entry.** Not already logged (the
Reviewer's S9-05 finding hadn't been written up anywhere yet). Added as
its own standalone OPEN entry: `BillingSuccessPage.tsx`'s original
comment falsely claimed the checkout webhook "already happened" by the
time Stripe's redirect lands — Stripe guarantees no such ordering. Fixed
the misleading comment in the same commit (the underlying
poll/retry behavior itself is NOT built — that's the entry's own closure
condition, deliberately left as future work, not silently fixed here).

**Item 2 — test account cleanup.** Not already done.
`s9-03-billing-test@example.com`, its subscription row, 90 `usage_events`
rows, and its 7 seeded categories all deleted, in one transaction, in
FK-safe order. Confirmed before/after: real users 6→5, real transactions
412→412 (untouched), the account itself 1→0.

**Kill-switch-off regression (Item 3) — PASSES.**

    Full backend suite: 184/184 passing.
    Live against the real dev database:
      BILLING_ENABLED: false
      5 real users, every one reads tier=free
      real chat usage today: 0/50 (read-only check, no writes to real users)

Zero real-user impact — confirmed by direct query, not inferred from the
test suite alone.

**Kill-switch-on full billing flow (Item 4) — PASSES.** Ran a complete
real lifecycle on a fresh throwaway account
(`s9-06-close-test@example.com`), then fully cleaned it up afterward —
this ticket's own job is verification, not accumulating more test data:

1. Free-tier gating confirmed first: 10/10 succeeded, blocked with the
   free-tier upgrade message.
2. Real checkout (`4242...` test card, real browser) → real webhook
   (`checkout.session.completed`, `200`) → real row: `tier=paid`,
   `status=active`.
3. Tier gating re-checked post-upgrade: 150/150 succeeded (the free cap
   was 50) — the paid ceiling, not the free one, is what's actually
   enforced.
4. Portal access confirmed: real login, real click into a real Stripe
   Customer Portal session, real headline rendered.
5. Immediately cancelled for real via the Stripe API (`status: canceled`,
   confirmed) — real `customer.subscription.deleted` webhook delivered
   and applied (`200`) before any cleanup.
6. All test-account data deleted (subscription, 160 `usage_events`, 7
   categories, the user, the beta invite). Kill switch restored to
   `false`. Final state: 5 real users, 412 real transactions, **0**
   `subscriptions` rows — the dev database is now cleaner than it was
   before this ticket started.

**ARCHITECTURE.md accuracy pass (Item 5) — done, full top-to-bottom read**
(not a section skim), per CLAUDE.md's sprint-close duty. Five real
corrections landed:
- A stale claim that tier gating wasn't wired in yet (it was, by S9-04).
- `WEBHOOK_RATE_LIMIT` (a real, shipped Reviewer-finding fix) had zero
  documentation anywhere in the file until now.
- The Invariants section's usage-cap entry didn't mention the S9-04
  kill-switch/tier conditionality at all.
- `STRIPE_PUBLISHABLE_KEY` was documented as "will be wired when S9-05
  needs it" — S9-05 shipped and never needed it (checkout/portal are
  pure server-redirect flows, confirmed by grep: zero references to
  `STRIPE_PUBLISHABLE_KEY` or Stripe.js anywhere in the repo). Corrected
  to state plainly it's unused today.
- Stripe had no entry at all in "External Dependencies & Their
  Guarantees" despite being Sprint 9's major new external dependency —
  added one in the section's existing format.

Also explicitly verified and confirmed already accurate (not skipped):
every column/constraint on `subscriptions`/`app_settings`/`usage_events`/
`users` against live `\d tablename` output, all four billing routes
against the real router decorators, dependency version pins, and several
"as of Sprint N" historically-scoped claims correctly left untouched
(they describe a past state on purpose, not current drift). AWS
infrastructure claims were read for internal consistency but not
re-verified live — this environment still has no AWS credentials, and
Sprint 9 touched no AWS infrastructure, so there was no code-side reason
to suspect drift there; flagged as the one section still owed a live
re-check whenever AWS access exists again.

**Security spot-check (Item 6) — PASSES**, each checked fresh, not
carried over from earlier tickets:
- Signature verification: a real unsigned request to the live server →
  real `400 {"detail":"Invalid signature."}`.
- Rate limiting: 61 real forged requests to the live server → `429` well
  before the 61st (the limiter's bucket already held a prior check from
  this same session, confirming it accumulates correctly across calls).
- No self-grant path: grepped every write to `Subscription.tier` in the
  codebase — both writer functions (`crud.upsert_subscription_from_checkout`,
  `crud.update_subscription_by_stripe_subscription_id`) are called only
  from `app/routers/billing.py`'s four webhook-event handlers, themselves
  only reachable through the signature-verified `stripe_webhook` route.
  No PATCH/PUT endpoint on subscriptions exists anywhere.
- Stripe keys sourced correctly: `.env` confirmed still gitignored
  (`git check-ignore` — not committed, never was).
- Restricted-key ledger item: confirmed still present and OPEN in
  `docs/verification_debt.md` ("Stripe key is a full secret key, not a
  scoped restricted key," S9-01) — not lost or silently closed.

**Ledger final state (Item 7) — CURRENT, explicit confirmation.** Read
the entire file top to bottom (not grep) — all ~1140 lines, every OPEN
and CLOSED entry. Per the file's own Conventions ("re-dating at sprint
close... re-confirms every remaining OPEN entry against current
reality"), re-confirmed and re-dated 8 OPEN entries unrelated to Sprint 9
(`account_uids_encrypted`, Enable Banking stale name, `users.email`
case sensitivity, AWS credit balance, `GOOGLE_CLIENT_SECRET` rotation,
date-range validation tests, sync-lock release, frontend test harness —
the last one re-verified directly: `package.json` still has no
`test`/vitest/jest, and Sprint 9 shipped real untested frontend code on
top of that gap, noted explicitly). Two Sprint-9-specific entries needed
no re-dating (already dated today, still accurate: the restricted-key
gap and the Secrets-Manager-not-applied gap, both S9-01, neither touched
this sprint). One entry closed same-sprint already stands correctly in
CLOSED (`subscriptions` id uniqueness, S9-02→S9-03). One new entry added
this ticket (the success-page race). Zero entries found stale beyond what
was already known and logged.

**Sprint 9 complete, pending PM confirmation.**

**Billing remains OFF.** `BILLING_ENABLED` is `false` in the real dev
database right now, confirmed by this ticket's own final check —
production's actual default. Flipping it on is Borys's own deliberate
future action; nothing in this sprint does that automatically, and
nothing should.

KEY DECISIONS

- Fixed Item 1's misleading comment but deliberately did NOT build the
  poll/retry fix itself → the ticket item said "log," not "fix," and a
  sprint-close ticket's job is verification/audit, not new feature work;
  building it unprompted would be exactly the kind of scope creep PROMPT
  5 exists to prevent.
- Used a fresh throwaway account for Item 4 rather than reusing anything
  from earlier tickets, and fully deleted it afterward → a sprint-close
  ticket whose own job includes "clean up accumulated test data"
  shouldn't accumulate more of it while doing so.
- Delegated the full ARCHITECTURE.md read-through to a sub-agent rather
  than doing it inline → CLAUDE.md's sprint-close duty explicitly
  requires a genuine top-to-bottom read (2110 lines) cross-checked
  against live system state, not a targeted grep of "just the billing
  parts" — large enough and self-contained enough to delegate, with the
  diff reviewed afterward before trusting it.

WATCH OUT FOR

- Nothing new found beyond what's now logged in the ledger (the
  success-page race, both already-open Sprint-9 billing gaps, and the
  AWS-infrastructure-section re-verification gap noted above).

HOW IT CONNECTS

This closes Sprint 9. S9-01 through S9-05 built real Stripe billing —
account setup, schema, checkout/webhooks, tier gating, and UI — with the
kill switch defaulting off at every step so beta users were never
affected until this ticket explicitly proved that with live evidence,
not just code review. Whatever comes next (a Sprint 10, or Borys
deciding when to actually flip the switch) starts from a verified-clean
state: zero test-account residue, zero stale documentation, zero known
security gaps in the billing surface, and a ledger that accurately
reflects everything still genuinely open.

Sprint 9 complete pending PM confirmation.
