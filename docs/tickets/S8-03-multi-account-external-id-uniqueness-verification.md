Status: in-progress

================================================================
TICKET S8-03 — Multi-Account external_id Uniqueness Verification
================================================================

BACKGROUND: S7-01's audit flagged that Enable Banking's
entry_reference (external_id) uniqueness scope is per-account,
not per-user or globally — this was accepted as a Sprint 7
watch-item because one user only had one account. Now that
ING support means a user could plausibly have KBC AND ING
connected (or multiple accounts at either), this needs real
verification, not continued deferral.

WHAT TO BUILD:
- Confirm the current UNIQUE(user_id, external_id) constraint
  (from Sprint 6's migration) is genuinely sufficient once a
  single user has multiple real bank accounts connected
  simultaneously
- Real test: connect both KBC and ING to the same user account
  (or two accounts at the same bank if that's easier to
  arrange), confirm no false-duplicate rejection and no missed
  duplicate across the two connections
- If a real collision risk is found: fix it (likely scoping
  further, e.g. by account identifier within the user), don't
  just document around it — this is a data-integrity concern of
  the same class as S4-01's original dedup incident

ACCEPTANCE CRITERIA:
- Real test with two simultaneous bank connections on one
  account, confirmed no duplicate/collision issues
- If a fix was needed: real evidence it resolves the issue,
  same rigor as S4-01
- ARCHITECTURE.md's Invariants section updated to reflect
  the now-verified (not just planned) state
- **AMENDED (2026-08-27):** "if a fix was needed... likely
  scoping further, e.g. by account identifier within the
  user" is superseded by the S8-01 decision: the fix must NOT
  key on Enable Banking's `account_id` (CLAUDE.md's EXTERNAL
  SYSTEM ASSUMPTIONS — `account_id` is not stable across
  reconnects, S3-08/S4-01). If widening is needed, it widens
  on a stable institution dimension introduced by S8-01's
  `enable_banking_sessions` migration, not on `account_id`
  itself.

--- AMENDED, pre-check before starting (2026-08-28) ---

Per S8-02's real finding, the real ING connection on
boris.sydorchuk@gmail.com has zero linked accounts (Enable
Banking itself confirms this — not a bug, cause unresolved,
tracked in docs/verification_debt.md). Checked whether this
blocks S8-03 before assuming it does: it does not. The ticket's
own text already anticipates this exact substitute — "connect
both KBC and ING... **or two accounts at the same bank if
that's easier to arrange**." The underlying vendor risk (Enable
Banking's FAQ, docs/multi_user_migration_plan.md, S6-02 Step 0)
is scoped **per-account**, not per-institution — two real KBC
accounts collide the same way two banks would, for the same
reason.

boris.sydorchuk@gmail.com's KBC connection already has two
real, distinct accounts with real data: account_id
`f0329f08-8504-43bd-8824-73761b6f1430` (1 transaction) and
`08ce6229-e5aa-420a-98a6-86a65e937b3d` (55 transactions) —
confirmed during S8-02's evidence gathering. This ticket
proceeds using that real pair for its core collision test.

The specifically cross-institution (KBC+ING) variant of this
test remains genuinely blocked on the same S8-02 gap and stays
deferred — the existing docs/verification_debt.md entry is
updated to reflect the core mechanism is now verified via the
two-account case, not closed, since the cross-institution
variant is still real, open, untested.
