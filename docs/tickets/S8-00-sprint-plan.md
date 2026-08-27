Status: plan
Source: issued directly in Claude Code session, 2026-08-27

---

================================================================
SPRINT 8 — "MULTI-BANK & BETA LAUNCH"
KBC Personal Finance Analyzer / Mymble
================================================================

SPRINT GOAL: Mymble supports ING alongside KBC, with a real
bank-selection flow rather than a KBC-only default. Basic
per-user usage guardrails exist before real strangers start
using real LLM API calls. A beta invite mechanism exists. By
sprint close, Borys has a path to actually invite 10-20 real
users.

Sprint 7 is fully closed. Read ARCHITECTURE.md and
docs/multi_user_migration_plan.md before starting — both are
current as of S7-10's close.

DECISIONS ALREADY MADE:
- Second bank: ING (not BNP Paribas Fortis this sprint —
  that's Sprint 9+ if this goes well)
- Beta user identification is Borys's own task, running in
  parallel — Codee builds the mechanism, not the user list
- Lead with the technical multi-bank work first, beta
  logistics second

PROCESS (unchanged from Sprint 7): commit this sprint plan to
docs/tickets/S8-00-sprint-plan.md (Status: plan) before S8-01.
Every ticket through Reviewer review before confirmation.
Ledger discipline from S7-08's fix applies: any WHEN DONE
answer containing "pending/not yet/still open" touches BOTH
ARCHITECTURE.md and docs/verification_debt.md, not just one.

================================================================
TICKET S8-01 — ING Support Discovery & Bank Selection UI
================================================================

PRIORITY: Premise check first. Enable Banking is a PSD2
aggregator — it's plausible that "add ING" is mostly
configuration (selecting another supported ASPSP) rather than
new integration code. Don't assume either way.

WHAT TO BUILD:

Part 1 — Discovery (do this before any code):
- Check Enable Banking's actual documentation/API for whether
  ING Belgium is already a supported ASPSP, same as the S7-01
  external_id vendor-doc check — verify against real docs, not
  assumption
- If supported: identify what institution ID/parameters are
  needed to initiate a connection to ING specifically (the
  current flow hardcodes KBC)
- If NOT supported or requires separate onboarding/approval
  with Enable Banking: stop and flag this immediately — this
  changes the whole sprint's scope and needs a PM/Borys
  decision before proceeding

Part 2 — Bank selection UI (assuming ING is available):
- Replace the current "Connect your bank" flow's implicit
  KBC-only assumption with a real bank picker: at minimum
  KBC and ING as selectable options
- The picker should be clearly extensible — adding a third
  bank later should be a data change, not a structural one
- Update the connection flow (S7-06/S7-07's per-user session
  work) to pass the selected institution through to Enable
  Banking correctly

ACCEPTANCE CRITERIA:
- ING's availability via Enable Banking confirmed against
  real documentation, cited specifically
- Bank picker UI built and functional, KBC + ING both
  selectable
- Selecting either bank correctly threads through to the
  Enable Banking authorization request with the right
  institution parameter
- No live bank connection required yet for THIS ticket — that's
  S8-02

WHEN DONE:
- Cite the actual Enable Banking documentation confirming ING
  support
- Screenshot of the bank picker
- Show the correct institution parameter being sent for each
  bank choice (real request evidence, not code review alone)
- Do not start S8-02 until confirmed

--- AMENDED DURING S8-01 DISCOVERY (2026-08-27, Borys confirmed) ---

Discovery surfaced a structural blocker beyond the ticket's
original premise check: `enable_banking_sessions.user_id` is
the table's sole primary key (S7-06), so storage as built
today holds exactly one bank connection per user — connecting
a second institution overwrites the first's session row
in place, it does not add to it. This collides with the
sprint goal's "ING alongside KBC" (simultaneous, not
either/or) and with S8-02/S8-03's acceptance criteria as
originally written, both of which require two live connections
to coexist.

DECISION (Borys, 2026-08-27): true simultaneous connections.
`enable_banking_sessions` moves to a composite key
(`user_id`, `institution`), same nullable-then-backfill,
verified-row-count discipline as S6-02's migration, since a
real session (Borys's live KBC connection) already exists and
must not be lost. Folded into S8-01/S8-02 as foundational work,
not deferred.

Also flagged as part of the same decision: `transactions`'
existing `UNIQUE (user_id, external_id)` dedup key was
deliberately scoped off `account_id` (S6-02, because Enable
Banking's `account_id` is not stable across reconnects — see
CLAUDE.md's EXTERNAL SYSTEM ASSUMPTIONS). That was safe under
the one-bank-per-user model, where "same user, same
external_id" implicitly meant "same bank." Once a user can
hold simultaneous KBC + ING connections, Enable Banking's own
FAQ (quoted in docs/multi_user_migration_plan.md, S6-02 Step 0)
already establishes `entry_reference` collisions are possible
*across different accounts* — including, now, across different
institutions under the same user. This needs real verification
and, if confirmed live, a real fix (widen the uniqueness key
to include a stable institution dimension, not `account_id`
itself) — this is S8-03's scope, brought forward here only to
record why S8-03's acceptance criteria change below.

Borys also asked, in the same decision, that once both
connections are live: confirm `transactions.account_id`
correctly disambiguates KBC-sourced from ING-sourced
transactions with real data from both banks (not assumed),
and confirm no KBC-only assumption is baked into
categorization/statistics/dashboard code anywhere.

================================================================
TICKET S8-02 — ING Live Connection & Per-Institution Handling
================================================================

WHAT TO BUILD:
- Complete real, live ING connection flow — same evidence
  standard as every credential-touching ticket this project has
  had: this needs Borys to have or create a real ING account
  (or a test/sandbox path if Enable Banking + ING offers one —
  check first, flag if a real account is the only option)
- Handle any real data-shape differences between KBC and ING
  transaction data: description formats, account structure,
  currency handling, date formats — whatever a real connection
  reveals, don't assume KBC's shape generalizes
- Confirm the existing categorization/sync/insights pipeline
  works correctly against real ING data without KBC-specific
  assumptions baked in anywhere

ACCEPTANCE CRITERIA:
- A real ING connection completes successfully end-to-end,
  same web-only flow standard as S7-07
- Real ING transactions sync, categorize, and appear correctly
  in the dashboard
- Any per-institution quirks found are documented in
  ARCHITECTURE.md, not silently special-cased without
  explanation
- Existing KBC connection/data unaffected — real regression
  check, not assumption
- **AMENDED (2026-08-27):** "unaffected" now means: with the
  composite-key `enable_banking_sessions` model from S8-01,
  the real KBC connection remains live and independently
  usable *while* the ING connection is also live — not just
  "reconnecting doesn't corrupt old transaction rows." Both
  connections coexisting simultaneously is the actual test,
  not a fallback interpretation.
- **ADDED (2026-08-27):** real evidence that
  `transactions.account_id` correctly disambiguates KBC-sourced
  from ING-sourced rows once both are connected, checked
  against real data from both banks, not assumed.

WHEN DONE:
- Real evidence of a live ING connection and sync
- Any data-shape differences found, and how they were handled
- Confirm KBC still works, unaffected (per the amended
  simultaneous-connection meaning above)
- Do not start S8-03 until confirmed

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

WHEN DONE:
- Real dual-connection test results
- Confirm whether a fix was needed and, if so, what and why
- Do not start S8-04 until confirmed

================================================================
TICKET S8-04 — Per-User Usage Guardrails
================================================================

BACKGROUND: Sprint 9 (Monetization) will handle real billing
and formal tiers. But Sprint 8 is when real strangers — not
just Borys — start making real LLM API calls against Borys's
(or their own) API keys. Shipping beta access with zero usage
ceiling is a real cost/abuse risk worth closing now, not after
an incident.

WHAT TO BUILD:
- Basic per-user daily/monthly caps on LLM-calling actions
  (categorization runs, chat messages, insight generation) —
  generous enough not to annoy a real beta user, present
  enough to prevent runaway cost from a bug or misuse
- Clear, honest user-facing messaging when a cap is hit (not
  a cryptic error) — this is a beta limit, communicate it as
  such
- Confirm this doesn't conflict with S5-07's existing
  rate-limiting work — check before building a second,
  overlapping mechanism

ACCEPTANCE CRITERIA:
- Real caps enforced, tested by actually hitting them
- Clear user-facing messaging confirmed, not just a raw 429
- No conflicting overlap with existing S5-07 rate limits —
  state how they relate if both exist

WHEN DONE:
- Real evidence of a cap being hit and enforced
- Screenshot/example of the user-facing message
- Do not start S8-05 until confirmed

================================================================
TICKET S8-05 — Beta Invite Mechanism
================================================================

WHAT TO BUILD:
- A simple way for Borys to grant beta access to specific real
  people without opening registration to the general public —
  an invite-code system, an admin-granted allowlist, or
  equivalent (your call, justify the choice)
- Should be simple to operate manually (Borys adding a handful
  of people), not an over-engineered general-purpose invite
  system — this is for 10-20 people, not scale

ACCEPTANCE CRITERIA:
- Borys can grant access to a specific real email/person
  without public registration being open to everyone
- Tested with a real invite granted and used end-to-end

WHEN DONE:
- Real evidence of the invite mechanism working end-to-end
- Do not start S8-06 until confirmed

================================================================
TICKET S8-06 — Feedback Channel & Beta Onboarding Polish
================================================================

WHAT TO BUILD:
- A simple, real way for beta users to send feedback or report
  problems (could be as lightweight as a mailto link, a form
  that emails Borys via S7-08's SES infrastructure, or
  similar — don't over-build this)
- A quick pass over the first-time user experience with fresh
  eyes: does a genuinely new person understand what to do
  first? Fix anything glaringly confusing, don't do a full
  redesign

ACCEPTANCE CRITERIA:
- Feedback channel real and functional, tested with a real
  message sent through it
- Onboarding walkthrough done with real fresh-account eyes,
  issues found are listed even if not all fixed this ticket

WHEN DONE:
- Real evidence feedback channel works
- List of onboarding issues found and which were fixed
- Do not start S8-07 until confirmed

================================================================
TICKET S8-07 — Sprint 8 Close
================================================================

WHAT TO BUILD:
Full regression and documentation accuracy, same discipline
as every sprint close.

ITEMS:
1. Full regression sweep against production, with BOTH banks:
   KBC connection/sync/categorization, ING connection/sync/
   categorization, usage caps, invite mechanism, feedback
   channel
2. ARCHITECTURE.md accuracy pass — multi-bank model, usage
   guardrails, invite system
3. Security spot-check: confirm the invite mechanism doesn't
   introduce a new unauthenticated-access path, confirm
   usage caps can't be trivially bypassed
4. Cost check: real usage data if any beta users have started,
   compare against S8-04's guardrail assumptions
5. Ledger: zero stale entries

ACCEPTANCE CRITERIA:
- Both banks fully regression-tested in production
- ARCHITECTURE.md accurate
- Security spot-check passes
- Ledger current
- Sprint 8 complete pending PM confirmation

WHEN DONE:
- Regression results for both banks
- Security spot-check results
- Sprint 8 complete pending PM confirmation

================================================================
SPRINT 8 → SPRINT 9 HANDOFF
================================================================
Sprint 9 — "Monetization": Stripe integration, free/paid tier
gating replacing S8-04's blunt beta caps with real plan limits,
formal usage-based billing. Whatever real usage patterns
emerge during Sprint 8's beta period directly inform Sprint 9's
tier design — worth Borys watching actual beta usage, not just
guessing at tiers cold.

================================================================
END OF SPRINT 8 TICKETS
================================================================
