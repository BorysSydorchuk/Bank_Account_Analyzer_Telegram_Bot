Status: delivered
Source: issued directly in Claude Code session, 2026-08-18

---

================================================================
TICKET S5-06 — Verification Debt Burn-Down
================================================================

ITEM 1 — Claude provider live test (key now available in .env):
  Save via PATCH /api/settings, switch provider to Claude in
  Settings, run a full sync (categorization + insight
  generation), run a live chat conversation with streaming,
  verify insights are distinguishable in style from Gemini's,
  switch back to Gemini. Close every open Claude-related
  ledger entry: S2-04 (provider structural verification),
  S2-05 (categorization), S2-06 (insights), S4-06 (chat
  streaming). Commit as: chore: close Sprint 2-4 Claude
  provider gaps — first live verification.

ITEM 2 — Windows bind-mount permissions (S4-09):
  Cannot close on this host. Re-date to current, confirm
  closure condition remains Sprint 6's Linux deployment.

ITEM 3 — Remaining open entries:
  Review every entry in docs/verification_debt.md. Close
  anything S5-03/S5-04's test suite now covers automatically
  — point to the specific test. Re-date and restate anything
  that still can't close.

ITEM 4 — Ledger hygiene:
  Zero entries without a current date and a concrete closure
  condition at sprint end. Add a short header to the file
  documenting its own conventions if one doesn't exist yet.

ACCEPTANCE CRITERIA:
- Claude live-verified across categorization, insights, and
  chat, or a clear reason recorded if something blocks it
- All closeable entries closed with evidence
- Ledger has zero stale entries

WHEN DONE:
- Show the live Claude run (categorization output, insights,
  chat conversation)
- Before/after ledger state
- Do not start S5-07 until confirmed

## WHEN DONE — answered (2026-08-18, all live against the real stack):

**Live Claude run:**

- Blocker found first: switching to Claude and calling
  `POST /api/analysis/categorize` failed with `"No API key configured for
  claude"` despite `anthropic_api_key` showing saved. Real bug, not a
  missing key — `settings_service.get_decrypted_api_key` assumed
  `f"{provider}_api_key"`, which is `"claude_api_key"` for the Claude
  provider, but the actual field has always been `"anthropic_api_key"`.
  Flagged to Borys before touching code; he chose an explicit
  `API_KEY_FIELD_BY_PROVIDER` map over renaming the field. Fixed,
  live-reloaded (backend logs confirmed clean reload, no traceback).
- **Categorization**, 5 real transactions (values recorded, cleared to
  `NULL`, restored after):
  `{"categorized":5,"skipped_already_categorized":40,"failed":0,"provider":"claude","error_message":null}`.
  4/5 matched Gemini's original categories exactly; the 5th (€233.93 KU
  LEUVEN) got `Other/Shopping` from Claude vs. `Other/Rest` from Gemini —
  a real difference in judgment, not an error.
- **Insights**, same range, `"provider":"claude"`, 5 real insights —
  noticeably more quantitative/prescriptive than Gemini's (precise
  percentages, ratios, a concrete "20–30% reduction" estimate with a
  suggested action) vs. Gemini's more narrative style from the S4-06
  closure.
- **Chat**, real SSE via `curl -N`, two turns: turn 1 asked for biggest
  expense and groceries-vs-transport, got back correct grounded numbers
  (matching `GET /api/statistics`/`GET /api/budgets` exactly) delivered as
  real incremental token frames, plus real `usage: {"input":1046,"output":229}`
  from `stream_complete()`. Turn 2 (with turn 1 in history) correctly built
  on it, referencing the same figures and real merchant names from the
  actual data (Carrefour, Delhaize, Too Good To Go, NMBS, De Lijn) —
  multi-turn history confirmed working.
- Provider switched back to `gemini`; all 5 transactions restored to their
  original recorded values. Full transcript in
  `docs/verification_debt.md`'s CLOSED section.

**Item 2 (Windows bind-mount permissions):** re-dated to 2026-08-18;
closure condition unchanged — still Sprint 6's move to a Linux host.

**Item 3 (remaining OPEN entries reviewed):**
- `Sync lock release on two failure early-returns` (S5-05) — **review
  bounce (2026-08-18):** the Reviewer caught that this entry's `Status:`
  line, added the prior S5-05 session, had never actually been dated —
  it read `OPEN — belongs to the Tester agent's...` with no date at all,
  not the current-dated status this ticket's own Item 4/Conventions rule
  requires. Corrected to `Status: OPEN (2026-08-18) — no target session
  assigned yet; belongs to the Tester's S5-04 follow-on work.`
- `Three regression tests deferred` (S5-04) — re-checked
  `kbc_analyzer/frontend/package.json` directly: still no `test` script,
  no vitest/jest. Re-dated, restated, nothing closeable.
- `Non-root file-permission protection` (S4-09 Item 1) — see Item 2 above.
- `Claude provider — chat streaming, no API key` (S4-06) — **closed**, see
  Item 1 above. This was the one entry S5-03/S5-04's suite doesn't touch
  (it's a live-API concern, not something a mocked test suite can close) —
  closed by this ticket's own live run instead.
- `SPRINT 5 AUDIT SCOPE` (`_provider_cache` singleton) — not verification
  debt in the ledger's sense; added a dated `Status:` line per Item 4
  anyway, since the ledger-hygiene rule (below) applies to every entry in
  the file, not just the ones under `## OPEN`.

**Item 4 (ledger hygiene):** added a `## Conventions (S5-06)` section
documenting what every entry needs (what/why/closure condition/dated
status) and the re-dating-at-sprint-close practice. Every remaining entry
in the file — OPEN and the audit-scope singleton note — now has a
current-dated `Status:` line with a concrete closure condition.

**Before/after ledger state:**
- Before: 1 SPRINT 5 AUDIT SCOPE item (no dated status), 4 OPEN entries
  (sync-lock — added S5-05, no date at all on its `Status:` line; frontend
  tests, non-root permissions, Claude — S4-06/S4-10-dated or older), no
  Conventions section.
- After: 1 SPRINT 5 AUDIT SCOPE item (dated, closure condition stated), 3
  OPEN entries (sync-lock — dated 2026-08-18 per the review bounce above;
  frontend tests and non-root permissions — re-dated 2026-08-18, closure
  conditions confirmed unchanged), 1 new CLOSED entry (Claude, closing
  S2-04/S2-05/S2-06/S4-06
  together), Conventions section added.
