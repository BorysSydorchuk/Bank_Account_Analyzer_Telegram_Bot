Status: in-progress

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
