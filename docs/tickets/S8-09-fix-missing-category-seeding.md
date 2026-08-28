Status: in-progress

================================================================
TICKET S8-09 — Fix Missing Category Seeding for New Users
================================================================

PRIORITY: Blocking. Categorization is non-functional for every
real user except the original bootstrap account. This blocks
Sprint 8's actual stated purpose (real beta users) completely.

WHAT TO BUILD:

Part 1 — Root fix:
- Wherever a new user is created (both register() paths —
  direct and Google OAuth), seed that user's initial categories
  table rows. Base set should match whatever the original
  bootstrap account's categories represent (check what those
  are, use them as the seed template) — or Borys's call if
  there's a reason to differ
- This must happen atomically with user creation, not as a
  follow-up step that could itself be skipped or fail silently

Part 2 — Backfill existing broken accounts:
- Identify every real user account currently missing categories
  (per Codee's finding: every account except the original
  bootstrap one)
- Seed categories for each, same logic as Part 1
- Real evidence: before/after count per affected account,
  same rigor as every prior data-migration ticket this project
  has done

Part 3 — Close the silent-failure gap:
- The S5-02 safety filter rejecting unknown categories is
  correct behavior — but 107 silent rejections with zero
  surfaced error is not. Add real error/warning surfacing so
  this failure mode is visible in the sync status/job state,
  not just a WARNING buried in logs
- Check whether this also affects budget creation (FK'd to
  (user_id, category)) as flagged — confirm and fix if so

ACCEPTANCE CRITERIA:
- A genuinely new registration (real test, another fresh
  account) gets working categorization immediately, no manual
  intervention
- Every existing affected account backfilled, real before/after
  evidence
- Budget creation confirmed working (or fixed) for a
  non-bootstrap account
- Silent per-batch rejection now surfaces visibly, not just in
  logs
- Existing bootstrap account (boris.sydorchuk@gmail.com)
  unaffected by any of this

WHEN DONE:
- Real evidence of a fresh account categorizing correctly
- Backfill results per affected account
- Budget-creation confirmation
- Show the new error surfacing working
- Do not close Sprint 8 until this is confirmed
