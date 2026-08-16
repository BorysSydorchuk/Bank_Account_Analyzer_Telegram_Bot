Status: confirmed
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
TICKET S4-10 — Sprint 4 Polish, Verification-Debt Burn-Down &
                 End-to-End Check
================================================================

The sprint closer. No new features.

POLISH ITEMS:
1. Chat nav item: position (between Dashboard and
   Transactions), active state, hover style all correct.
2. Budget widget: appears only when budgets exist,
   disappears when all budgets are deleted, card click
   navigates to Settings → Budgets.
3. Comparison section: collapsed on every page load, not
   just the first.
4. Streaming error recovery — CONSENTED LIVE TEST, procedure
   already recorded in docs/verification_debt.md:
   kill the backend container mid-response → verify partial
   text + "Response interrupted" marker renders → bring the
   container back up.
5. No-API-key toast — CONSENTED LIVE TEST, procedure already
   recorded in the ledger: back up the current Gemini key
   value → blank it via Settings → send a chat message →
   verify the toast directs to Settings → restore the key →
   verify chat works again.
6. Dedup stability: run 3+ consecutive syncs, transaction
   count stays constant.

VERIFICATION-DEBT BURN-DOWN:
Go through every OPEN entry in docs/verification_debt.md:
- Close what the polish items above close (items 4 and 5).
- The Docker-ps port diff owed since S4-03: run
  docker compose ps now and diff against ARCHITECTURE.md's
  Services & Ports table; close the entry.
- Anything that cannot close this sprint gets its status
  re-confirmed as current and its closure condition
  re-stated (Claude live test → S5-06 or key arrival;
  Windows bind-mount permissions → Sprint 6 Linux
  deployment).
The ledger at sprint close should contain zero stale
entries — every line either CLOSED or OPEN with a current
date and a concrete closure condition.

FULL END-TO-END CHECK (document each step's result):
  a. docker compose up from a clean stop — 5 containers
     healthy, no SecurityWarning anywhere, non-root uids
  b. POST /sync → job_id in <500ms
  c. Poll: fetching → storing → categorizing (batch X/Y)
     → generating_insights → done
  d. Dashboard: categories, colors, insights correct
  e. Chat: "What was my biggest expense?" → matches
     GET /api/statistics (the S4-06 bounce fix, end-to-end)
  f. Two more chat messages — history holds
  g. Budgets in Settings reflect current-month spending
     correctly
  h. Dashboard budget widget states (on-track/warning/
     exceeded) match GET /api/budgets
  i. Transactions → manual edit one row
  j. Re-sync → edited row untouched
  k. Compare Periods: July vs August → deltas match
     statistics; arbitrary range works; Option B insight
     display correct
  l. Change a category color in Settings → donut + pills
     update
  m. Reconnect flow end-to-end (no copy-paste)
  n. 3+ syncs → stable transaction count
  o. If Claude key available: switch provider, re-sync,
     verify insights + chat streaming on Claude
     (if not: already covered by the ledger)

ARCHITECTURE.md SPRINT-CLOSE AUDIT (CLAUDE.md duty):
Read ARCHITECTURE.md top to bottom and verify every claim
against the running system. Stale claims are bugs — fix
them in this commit. Explicitly re-check: Services & Ports
(now with non-root uids), Data Flow (chat + comparison
flows), Database Tables (budgets), Invariants (including
the documented-as-NOT-enforced sync lock).

ACCEPTANCE CRITERIA:
- All 6 polish items pass, including both consented live
  error tests executed per their recorded procedures
- Ledger has zero stale entries
- End-to-end a–n pass (o conditional on the key)
- ARCHITECTURE.md verified accurate in this commit
- No console errors on any page; no regressions in
  Sprint 1–3 features

WHEN DONE:
- Per-step results for the full end-to-end check
- Before/after ledger state (which entries closed, which
  re-confirmed)
- The two error-test results specifically (screenshot or
  exact observed behavior)
- Any stale ARCHITECTURE.md claims found and fixed
- Sprint 4 complete pending PM confirmation

---

## Delivery notes (Codee)

### Real blocker hit mid-ticket, resolved

`docker compose build` failed with "No space left on device" — the host
C: drive was at 0 bytes free. Docker Desktop then crashed ("unable to
start"). Not something to fix myself (host-level, outside this project);
flagged immediately and paused. Borys freed space and restarted Docker
(8.6G free afterward); work resumed from there.

Separately, real live syncs against Enable Banking/KBC failed 3 times in a
row with `400 {"code":400,"message":"Error interacting with ASPSP",
"detail":"Unknown error","error":"ASPSP_ERROR"}` (session was active, not
expired; different `account_id` each time, per the known S4-01 behavior).
A 4th attempt — via the actual UI, not curl — succeeded and brought in 19
new transactions (331 → 350). Given the explicit instruction to treat a
working sync as fully closing the sync-dependent items rather than waiting
for a scheduled Monday retry, items 6/b/c/n and step j's re-sync half were
all completed live today against real data. (Flagging for the record: I
cannot self-schedule a retry against your local Docker stack even if asked
to — a cloud-scheduled agent has no path to `localhost:8000` on your
machine. Future "retry tomorrow" asks need you to resume the session.)

### Polish items

1. **Chat nav position/active/hover** — confirmed correct in every
   screenshot taken this session (between Dashboard and Transactions,
   active state highlighted, matches Sidebar.tsx's existing pattern for
   every other nav item — no separate styling path to regress).
2. **Budget widget show/hide** — confirmed by code
   (`BudgetsWidget.tsx:29`: `if (!budgets || budgets.length === 0) return
   null`, invalidated on delete via `useDeleteBudget`'s
   `invalidateQueries`); the "appears with real data" half already
   live-verified all session. Did not delete Borys's real budgets just to
   watch the widget disappear — the code path is a one-line, unambiguous
   guard.
3. **Comparison section collapse-every-load** — live-verified beyond the
   S4-08 check: expanded it, navigated to Chat and back to Dashboard,
   confirmed it reset to collapsed (not just "collapsed on first mount").
4. **Streaming error recovery (consented)** — live-verified. See ledger
   CLOSED entry for the full record: killed `backend` mid-stream, partial
   text + red "Response interrupted — please try again" marker rendered
   correctly, input re-enabled, `backend` restored, chat confirmed working
   again with history intact.
5. **No-API-key toast (consented)** — live-verified. Backed up the
   *encrypted* Gemini key directly at the database level (never decrypted,
   never seen in plaintext) rather than reading it through Settings' UI —
   safer than the literal procedure and achieves the same thing. Blanked
   via `PATCH /api/settings`, toast confirmed reading "No API key
   configured for gemini. Add one in Settings before running analysis.",
   no orphaned assistant bubble. Restored the exact encrypted value via
   direct `UPDATE`, confirmed chat works again.
6. **Dedup stability, 3+ syncs** — 3 consecutive real syncs (1 with new
   data, 2 with none) against the live 350-transaction dataset; count
   verified stable at 350 after each.

### Verification-debt burn-down

Before: 3 OPEN entries (chat error paths, Claude no-key, non-root
Windows-bind-mount caveat — the last one added this same session, during
S4-09 follow-up).

After:
- **CLOSED:** chat frontend error paths (both live-triggered today, see
  Polish items 4–5 above).
- **OPEN, re-confirmed 2026-08-17:** non-root file-permission protection
  (still genuinely unverifiable on this host — closes at Sprint 6 Linux
  deployment).
- **OPEN, re-confirmed 2026-08-17:** Claude provider streaming (still no
  `ANTHROPIC_API_KEY`; suggested next checkpoint S5-06 or key arrival).
- Docker-ps port diff owed since S4-03: was never a formal ledger entry
  (S4-03 predates the ledger's creation) — it was a caveat note directly
  in ARCHITECTURE.md's own header. Resolved directly there: ran
  `docker compose down && docker compose up -d`, confirmed `docker compose
  ps` matches the Services & Ports table exactly, replaced the stale
  "couldn't verify, Docker was down" note with a dated confirmation.

Zero stale entries remain — every ledger line is CLOSED with a dated
record, or OPEN with a 2026-08-17 re-confirmation and a concrete closure
condition.

### Full end-to-end check — per-step results

- **a.** `docker compose down && docker compose up -d`: all 5 containers
  healthy. `docker compose logs | grep -i securitywarning` → none.
  `backend`/`celery_worker` both `uid=100(appuser)`.
- **b.** `POST /sync`: 59ms and 8ms on two real runs (both well under
  500ms).
- **c.** Full stage progression observed live in the browser across 3 real
  syncs: fetching → (storing/categorizing happen fast, not individually
  screenshotted) → generating insights → done, each ending in a real
  "Done — N categorized, M insights generated" status message.
- **d.** Dashboard categories/colors/insights: real Gemini-generated
  insights displayed with a real `generated_at` label; colors render from
  `categories` table (confirmed further by step l's live color-change
  test).
- **e.** Chat "What was my biggest expense?" → "€ 800,00 paid to BORYS
  SYDORCHUK on 27 July 2026 (2026-07-27)" — exact match against
  `GET /api/statistics`'s `biggest_expense` field, re-run against today's
  refreshed 350-transaction dataset (not just the S4-06 bounce-fix
  dataset).
- **f.** 3-turn conversation ("biggest expense" → "what category" →
  "how does that compare") — history held correctly across all 3; the
  assistant correctly declined to guess a category it didn't have data
  for rather than inventing one.
- **g./h.** Settings' Budgets section and the Dashboard budget widget both
  cross-checked directly against `GET /api/budgets`: Groceries
  €143.24/€40.00 Exceeded, Restaurants and Cafes €9.64/€50.00 On track,
  Traveling €27.88/€6.00 Exceeded — exact match in both places.
- **i./j.** Manually edited MARK SHEVCHENKO's category (Transfers → Other)
  via the Transactions page; confirmed `manually_edited = true` in
  Postgres. Re-synced live afterward: row stayed "Other"/`manually_edited
  = true`; Dashboard category totals shifted by exactly the edited
  transaction's €6.00 (Transfers 16.00→10.00, Other 19.99→25.99) —
  confirming the edit is respected by both categorization-skip logic and
  the aggregate stats.
- **k.** Compare Periods re-run against today's fresh data: Jul 1–31 vs
  Aug 1–16 (a full-month comparison, €3.216,31 vs €226,77, -92.9% in
  green) and Jul 1–31 vs Aug 1–9 (an arbitrary range hitting the one exact
  stored-insights range) — Option B contract confirmed again: "No insights
  stored for Jul 1–31" on one side, 5 real cards + "Generated 16 Aug 2026"
  on the other.
- **l.** Changed Groceries' color via Settings (validation UI correctly
  rejected a too-light color and a too-close-to-danger-red color before
  accepting a valid one) — Dashboard donut's largest wedge and the
  category legend dot both updated to the new color immediately. Reset to
  AI afterward to leave state as found.
- **m. PASSED — completed live with Borys, 2026-08-17.** Codee temporarily
  bumped `SessionBanner.tsx`'s `WARNING_THRESHOLD_DAYS` from 7 to 90 (a
  mechanism the file already anticipated: "Bump this to test the warning
  banner... put back to 7 before shipping" — S2-02) so the real,
  not-actually-expiring session (5 Nov 2026) tripped the warning banner
  without faking or shortening anything. Confirmed the amber banner fired
  correctly: "Your bank connection expires on 5 November 2026. Reconnect
  now to avoid interruption." Codee did not touch the Reconnect button or
  enter any credentials — Borys clicked Reconnect and completed the real
  KBC login himself in the new tab. Result: `GET
  /api/auth/enable-banking/status` → `{"status": "active", "expires_at":
  "2026-11-13T20:27:27...`"}` (a fresh ~90-day PSD2 consent, not the old
  one) — auto-caught by the port-3001 callback catcher, zero copy-paste.
  Browser showed the green "Bank connection reconnected — you're all set."
  success banner. Threshold reverted to 7 immediately after; confirmed the
  banner correctly disappeared again (real expiry is ~88 days out, above
  the 7-day threshold).
- **n.** Same 3 syncs as Item 6 — count stable at 350 throughout.
- **o.** Skipped — no Claude key, already covered by the ledger.

No console errors on Dashboard, Chat, Transactions, or Settings (checked
fresh via `read_console_messages` after navigating to each).

### ARCHITECTURE.md stale claims found and fixed (this commit)

- Header's "Verification note" was still the S4-03 Docker-was-down caveat
  — replaced with a dated live confirmation (this ticket's step a).
- `main.py`'s CORS middleware line reference (`22-28`) was stale — my
  S4-09 `logging.basicConfig` addition shifted it to `34-40`. Fixed.
- `lib/api.ts`'s `VITE_API_URL` line reference (`18`) was stale — S4-06/08
  type imports shifted it to `22`. Fixed.
- Added: `backend`'s new INFO-level logging config (a real S4-09 change
  not yet documented anywhere).
- Added: a documented Invariant that CLAUDE.md's date-range validation
  rule is only actually enforced on the newest endpoint
  (`/api/insights/compare`), not the four older ones — a genuine,
  pre-existing gap surfaced by this audit, not introduced this sprint.

Everything else read top-to-bottom against the running system (Services &
Ports, URLs, Data Flow, Database Tables, External Dependencies) checked
out accurate — mkcert dates verified against the actual certificate file
via `openssl x509 -dates` (exact match), migration count/names verified
against `migrations/versions/`.

---

## UPDATE 2026-08-17 (same day) — step m closed live with Borys

Step m (reconnect flow) was the one item left open above. Borys asked to
test it together: Codee bumped the warning threshold (a mechanism the code
already anticipated for exactly this), confirmed the banner fired
correctly, then Borys completed the real KBC login himself — Codee never
touched credentials or the Reconnect button. Result: a fresh session,
auto-caught with zero copy-paste, exactly as designed. Threshold reverted
and confirmed clean afterward. Full detail folded into step m's entry
above rather than duplicated here.

**All of a–n now pass.** Step o (Claude) remains the only deferred item,
covered by the existing verification-debt ledger entry (no key available).

**Sprint 4 complete.** Status flipped to `confirmed` per Borys's "done...
S4-10 closes clean, all of a–n" — PM sign-off is the remaining downstream
step, tracked separately from this ticket's own Status field.
