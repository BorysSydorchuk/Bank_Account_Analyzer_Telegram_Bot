Status: in-progress

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

================================================================
AMENDMENT — logged during Part 1 discovery, 2026-08-27
================================================================

Part 1 discovery found ING supported (see WHEN DONE below for
citation), so the ticket's original stop condition ("if NOT
supported... flag immediately") didn't trigger. But discovery
also surfaced a different, unanticipated blocker of the same
seriousness: `enable_banking_sessions.user_id` (S7-06) is the
table's sole primary key, so today's storage holds exactly one
bank connection per user — connecting a second institution
overwrites the first's session row via `ON CONFLICT (user_id)
DO UPDATE`, it does not add to it. This conflicts with the
sprint goal's "ING alongside KBC" and with S8-02/S8-03's
acceptance criteria as originally written, both of which
require two live connections to coexist and neither disturb
the other — untestable against the schema as it stood.

Flagged to Borys before writing any picker/threading code.
Decision (2026-08-27): true simultaneous connections. Fold the
`enable_banking_sessions` composite-key migration into this
ticket and S8-02, same nullable-then-backfill, verified-count
discipline as S6-02, since a real session (Borys's live KBC
connection) exists today and must survive the migration intact.
Full decision and consequences for S8-02/S8-03 recorded in
docs/tickets/S8-00-sprint-plan.md's amendment block.

This ticket's own scope now additionally includes:
- Widening `enable_banking_sessions` to a composite key
  (`user_id`, `institution`) so KBC and ING sessions can
  coexist per user
- Real migration evidence: row counts before/after, Borys's
  existing KBC session verified intact post-migration
- `EnableBankingService`/`DatabaseSessionStore`/routers/auth.py
  updated to be institution-aware (which connection a given
  request reads or writes)
- The bank picker UI and institution-threading work as
  originally scoped, now against the per-institution session
  model rather than the old single-row one
