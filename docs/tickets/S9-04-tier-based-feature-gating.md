Status: delivered

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
- Any deferred/non-blocking finding gets its own standalone
  ledger entry in the same commit, per the now-working pattern

WHEN DONE:
- Kill-switch-off regression evidence (nothing changed)
- Kill-switch-on evidence for both tiers
- Do not start S9-05 until confirmed

================================================================
AMENDMENT (2026-08-29) — two ambiguities resolved before building
================================================================
- Paid-tier caps: no ticket ever gave actual numbers, only "higher, not
  unlimited." Confirmed with Borys: 3x the free-tier ceiling — daily
  chat=150/categorize=30/insights=30, monthly chat=1500/categorize=300/
  insights=300.
- The ticket's own text was internally contradictory: WHAT TO BUILD says
  kill-switch-off means "always unlimited," but the acceptance criteria
  demand kill-switch-off be "identical to Sprint 8's current state" —
  and Sprint 8 already has real caps (50/10/10 daily, S8-04), not zero
  cap. Confirmed with Borys: kill-switch-off keeps the existing S8-04
  caps exactly (tier is never even consulted); "unlimited" in the WHAT TO
  BUILD section meant "not tier-differentiated," not "no cap at all."

================================================================
WHEN DONE (2026-08-29)
================================================================

**Kill-switch-off regression evidence (nothing changed).**
`tests/test_usage_limits.py` — the pre-existing S8-04 test file — was not
modified at all for this ticket and still passes completely unchanged:

    tests/test_usage_limits.py::test_daily_cap_hit_after_exactly_the_limit PASSED
    tests/test_usage_limits.py::test_monthly_cap_hit_even_with_daily_cap_untouched PASSED
    tests/test_usage_limits.py::test_caps_are_independent_per_action PASSED
    tests/test_usage_limits.py::test_caps_are_independent_per_user PASSED

Real evidence against the live dev database (billing off, the real
production default), a real user run through the actual daily chat cap:

    BILLING_ENABLED: false
    tier: free
    succeeded: 50/50
    final (blocked) message: You've reached today's beta limit for chat messages (50/day). Try again tomorrow.

Exact S8-04 wording, exact S8-04 count — confirmed live, not assumed from
the unit tests alone. `tests/test_usage_limits_tiered.py` also adds
`test_billing_off_ignores_stored_tier_entirely` — a user already tagged
`tier='paid'` in `subscriptions` still gets the free-tier cap when
billing is off, proving tier is never consulted at all in that state, not
just "defaults to free."

**Kill-switch-on evidence, both tiers**, same real user, live against the
same real dev database (billing flipped on via `crud.set_app_setting`,
the exact mechanism S9-01 already proved live):

    -- free tier, categorize action (cap=10)
    BILLING_ENABLED: true
    tier: free
    succeeded: 10/10
    final (blocked) message: You've reached today's free-tier limit for categorization runs (10/day). Upgrade to Mymble Pro for a higher limit.

    -- flipped to tier='paid', insights action (free cap=10, paid cap=30)
    BILLING_ENABLED: true
    tier: paid
    free-tier cap would have been: 10
    succeeded: 30/30 (paid cap)
    final (blocked) message: You've reached today's beta limit for insight generations (30/day). Try again tomorrow.

The paid user's own cap-hit message correctly keeps the original wording
— no upgrade mention, since a paid user has nothing further to upgrade to
in this two-tier model. Both the kill switch and the test user's tier
were restored to their defaults (`false`/`free`) immediately after
capturing this evidence, confirmed by reading them back afterward.

Full backend suite: 176/176 passing (171 pre-existing + 5 new:
`tests/test_usage_limits_tiered.py`).

KEY DECISIONS

- `DAILY_LIMITS`/`MONTHLY_LIMITS` keep their exact pre-S9-04 names and
  values, used unconditionally when billing is off → this is what makes
  the kill-switch-off path a genuine no-op rather than "the same numbers,
  recomputed a new way" — the existing S8-04 test file needed zero
  changes, which is the strongest evidence this ticket could give that
  nothing changed for a real beta user today.
- Only a free-tier user, with billing actually on, sees the
  upgrade-mentioning message → a paid user hitting their own (higher) cap
  has nothing to upgrade to, and the kill-switch-off path must keep
  S8-04's original wording verbatim regardless of what tier happens to be
  stored for that user (a user could be tagged 'paid' from a past
  subscription while billing is off, e.g. mid-incident rollback — the
  message must not leak billing-on phrasing in that state).
- Paid tier still has a real cap (3x free), not unlimited → Borys's
  confirmed call, matching S9-01's own stated rationale: a technical
  backstop against a compromised or runaway paid account, not just a
  cost question.

WATCH OUT FOR

- The real dev-database evidence above ran through the leftover
  throwaway test user from S9-03
  (`s9-03-billing-test@example.com`, still un-deleted per that ticket's
  own flagged note) rather than creating a new one — reused deliberately
  to avoid adding further test-data pollution. It now also carries ~91
  extra `usage_events` rows from this evidence run (50 chat + 10
  categorize + 31 insights). Same disposition as the S9-03 note: real
  users/transactions are unaffected; let me know if you'd like this
  cleaned up or want to do it yourself.
- No new `docs/verification_debt.md` entry was needed — every claim above
  was checked against the real running database, nothing deferred.

HOW IT CONNECTS

S9-01 built the kill switch and confirmed the free/paid distinction;
S9-02 built the schema and tier read; S9-03 is what actually makes a
user's tier become "paid" for real. This ticket is the first thing that
makes any of that observable to a real user — before now, every user, at
every tier, saw identical behavior no matter what `app_settings
.BILLING_ENABLED` said. S9-05 (Billing UI) is what gives a user a way to
see their own tier and act on the upgrade message this ticket now shows
them.

Ready for S9-05 whenever you confirm this one.

Do not start S9-05 until confirmed.
