Status: delivered
Source: issued directly in Claude Code session, 2026-08-19

---

================================================================
TICKET S5-08 — Sprint 5 Close
================================================================

WHAT TO BUILD:
No new work. Verification, regression, and documentation
accuracy — plus properly closing out the security excursion
that ran through S5-06/S5-07.

ITEMS:

  1. Full test suite run — green, with timings and coverage
     reported.

  2. Full regression check against Sprint 1–4 features:
     a. Dashboard: summary cards, category donut, both time
        charts, budget widget, insights panel, compare periods
     b. Transactions: list, filters, search, pagination,
        manual edit with the edited badge
     c. Chat: empty state, streaming, multi-turn, markdown
     d. Settings: provider selection (Gemini AND Claude, now
        that both are live-verified), API key, categories
        with color picker, budgets, bank connection status
     e. Sync end-to-end with real data
     f. Rate limiting doesn't interfere with normal use —
        confirm the S5-07 limits are generous enough that a
        real work session doesn't hit them accidentally

  3. ARCHITECTURE.md sprint-close audit (CLAUDE.md duty).
     Use section or symbol names rather than line numbers in
     references — line numbers went stale twice during
     Sprint 4. Explicitly re-verify: Services & Ports
     (non-root uids), Data Flow (chat, comparison, the
     sync-lock addition), Database Tables, Invariants
     (sync concurrency lock now enforced, not just
     documented-but-unenforced).

  4. docs/multi_user_migration_plan.md re-verification:
     S5-02, S5-05, and S5-07 all changed schema or endpoints
     since S5-01 wrote it. Confirm it's still accurate
     against the code as it now stands; update anywhere those
     tickets changed the picture. Sprint 6 executes this plan
     — it must be correct at handoff.

  5. Security-excursion documentation (NEW — this sprint's
     real story, not in the original ticket):
     Add a short, factual dated note — in ARCHITECTURE.md's
     history/changelog area if one exists, or as a new brief
     entry in docs/ — recording what actually happened:
     a suspected credential exposure in analysis.py was
     investigated during S5-06/S5-07, a precautionary full
     history rewrite was performed and verified (GitHub +
     local both confirmed clean), and a subsequent forensic
     check across all reachable commit history found no
     evidence real financial data was ever actually
     committed. State plainly that this may have been a
     false alarm rather than a confirmed leak, and that the
     rewrite was precautionary. This is worth recording
     accurately now, while the full context is fresh — not
     left to be reconstructed later from a chat transcript.

  6. Ledger final state: zero stale entries. Explicitly
     confirm the Claude-related entries closed in S5-06
     remain closed and accurate.

  7. Sprint 5 backlog sweep: confirm every item that was
     supposed to land in Sprint 5 actually did (multi-user
     audit, categories FK, test foundation, invariant tests,
     job reliability, verification debt, security pass) and
     nothing silently slipped through uncaptured.

ACCEPTANCE CRITERIA:
- Test suite green
- All regression surfaces verified working, including Item 2f
- ARCHITECTURE.md accurate, stable references (not line
  numbers)
- Multi-user migration plan re-verified post-S5-02/05/07
- Security-excursion note written, factual, dated
- Ledger current
- No console errors on any page

WHEN DONE:
- Suite output and coverage
- Regression results per surface
- What the migration plan re-verification changed
- Confirm the security-excursion note is written and where
- Sprint 5 complete pending PM confirmation

## WHEN DONE — answered (2026-08-19, all live against the real stack):

**Item 1 — suite output and coverage:** `57 passed, 1 warning in 4.78s`.
75% overall coverage (`app/schemas.py`, `app/models.py`, `job_store.py`,
`rate_limit.py` at 100%; lowest-covered files are provider SDK wrappers
and OAuth-callback edge paths, consistent with what unit tests can
reasonably reach without live third-party calls). Slowest test: 0.4s
setup on `test_budgets.py::test_budget_status_boundaries` — nothing
close to a real bottleneck.

**Item 2 — regression results per surface**, browser-driven, zero
console errors on every page visited:
- **Dashboard:** summary cards, budget widget, category donut, both
  Spending Over Time charts (Daily/Weekly toggle), 5-card AI Insights
  panel (real Gemini output), Compare Periods section (present,
  collapsed as designed; its endpoint already live-verified in S5-07) —
  all render correctly.
- **Transactions:** list, category filter, search (`Carrefour` → 20
  real matches), manual edit with the edited-badge (changed a real
  row's category, got the "Transaction updated" toast + pencil badge,
  reverted via API afterward). Pagination logic itself re-verified via
  its existing backend tests rather than re-clicking through pages —
  the current dataset (49 rows) doesn't exceed one page, so a UI click-
  through wouldn't exercise anything the API-level tests don't already
  cover.
- **Chat:** empty state with suggested prompts, real streaming
  response, markdown rendering (bulleted list, bold), multi-turn (second
  message correctly built on the first). One **pre-existing, unrelated
  finding**: a minor markdown-rendering glitch where nested bold syntax
  inside a parenthetical occasionally renders as literal `**` characters
  instead of being parsed — flagged, not fixed (outside this ticket's
  "no new work" scope).
- **Settings:** provider selection confirmed both directions (Gemini →
  Claude → Gemini, API-key field label and "A key is currently saved"
  text update correctly each time), bank connection shows real "Active —
  expires 13 November 2026", categories grid with working color-picker
  popover (opened, inspected, cancelled without changing data), budgets
  section with edit/delete/add controls.
- **Sync end-to-end:** triggered via the real "Sync & Analyze" button,
  completed cleanly, no errors.
- **Rate limiting vs. normal use (Item 2f):** never triggered once
  during this entire regression pass, despite multiple chat messages,
  provider switches, and a real sync — direct evidence the 20/min
  (chat) and 10/min (sync + both analysis endpoints) limits set in
  S5-07 don't interfere with a real work session.

**Item 3 — ARCHITECTURE.md:** every `file.py:NN` line-number reference
in the file replaced with a stable section/symbol name (5 found: the
`celery_worker` port mapping, the Enable Banking redirect URI, the CORS
middleware setup, the frontend `API_URL` constant, and the
`biggest_expense` symbol reference). Non-root UIDs re-confirmed live
(`docker compose exec backend/celery_worker whoami` → `appuser`).
Data-flow symbol names (`start_chat_stream`, `ChatAgent.stream`,
`compare_periods`, `compare_insights`) re-confirmed to still exist.
Database Tables cross-checked column-by-column against current
`models.py` — no drift. Sync-lock Invariant entry already correctly
described as enforced (from S5-05), re-confirmed live via this ticket's
own sync test. A dated re-verification note added at the top of the
file recording this pass.

**Item 4 — what the migration plan re-verification changed:** found and
closed three real gaps, not just re-confirmed old text —
1. **New:** S5-02's `transactions.category` FK (and the pre-existing
   `budgets.category` FK) both reference `categories.name` alone; once
   `categories`' primary key becomes `(user_id, name)` per the already-
   DECIDED ruling, a single-column FK to `name` stops being valid.
   Neither FK was mentioned anywhere in the original plan. Added to
   Constraints and folded into Ordering step 6 as a same-migration
   requirement.
2. **New:** `sync_lock.py` (S5-05) was never catalogued in Singletons —
   added as an already-multi-user-ready module (same category as
   `budgets`, zero migration work needed, by design).
3. **New:** `rate_limit.py` (S5-07) was never catalogued either — added
   as a genuinely-not-ready singleton (IP-keyed, needs to become
   `user_id`-keyed at Sprint 6).
Everything else in the document re-checked against current
`models.py`/`routers/*.py`/`crud.py` and found unchanged and accurate.

**Item 5 — security-excursion note confirmed written:**
`docs/security_excursion_2026-08.md` — factual, dated, states plainly
this may have been a false alarm rather than a confirmed leak, and that
the rewrite was precautionary. Cross-referenced from ARCHITECTURE.md's
Invariants section, whose own entry on this was updated from
"flagged, unresolved" to "resolved, see [that file]."

**Item 6 — ledger current:** all 5 dated OPEN entries (the
`_provider_cache` singleton, date-range regression tests, sync-lock
early-return tests, frontend test harness, non-root permissions)
re-confirmed against current reality and re-dated to 2026-08-19; none
had actually changed status, all remain open for the same reasons.
Claude-related CLOSED entry explicitly re-confirmed accurate — re-tested
live via the real Settings UI (not just the API) during this ticket's
own regression sweep, both directions clean.

**Item 7 — Sprint 5 backlog sweep:** all 8 planned tickets (S5-00
through S5-08) exist in `docs/tickets/` and were built — multi-user
audit (S5-01, confirmed), categories FK (S5-02, confirmed), test
foundation (S5-03, delivered), invariant tests (S5-04, delivered), job
reliability (S5-05, confirmed), verification debt (S5-06, delivered),
security pass (S5-07, delivered), this sprint-close ticket (S5-08,
in-progress). **Flagging honestly, not silently assuming:** S5-03 and
S5-04 (the Tester-agent tickets, built in a separate session per
`AGENTS.md`'s role split) show `Status: delivered` in their ticket
files, not `Status: confirmed` — I have no direct visibility into
whether Borys separately confirmed those with the Tester session, so
I'm not marking them confirmed on his behalf. Worth a quick check on
your end if that confirmation hasn't happened yet. All four of the
sprint plan's own stated goals are met: an automated test suite exists
and is green (S5-03/04), a documented multi-user migration plan exists
and is re-verified accurate (Item 4 above), no known standing-rule
violation remains unaddressed in shipped code (S5-07 closed the one
that existed; the handful of related-but-out-of-scope gaps it found
are explicitly flagged for a PM call, not silently unresolved), and the
verification ledger is current (Item 6).

**Sprint 5 complete, pending PM confirmation of this ticket** (and,
per the flag above, worth confirming S5-03/S5-04 are formally closed
too if that hasn't happened separately).
