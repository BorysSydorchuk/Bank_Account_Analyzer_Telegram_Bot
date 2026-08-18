Status: in-progress
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
