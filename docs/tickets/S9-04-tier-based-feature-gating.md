Status: in-progress

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
