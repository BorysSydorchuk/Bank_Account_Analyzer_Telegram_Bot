Status: delivered
Source: docs/tickets/S5-00-sprint-plan.md

---

================================================================
TICKET S5-02 — Categories Referential Integrity Decision
================================================================

BACKGROUND (from the supervision report):
categories.name is a primary key. transactions.category is
free text with no foreign key. budgets.category HAS a
proper FK with ON UPDATE CASCADE. Nothing renames categories
today, so this is dormant — but the moment a rename feature
exists, transactions orphan silently and their colors break.

WHAT TO BUILD:

Part 1 — Present the decision, wait for Borys's answer
before implementing:

  Option A — Add the foreign key:
  ALTER TABLE transactions ADD CONSTRAINT ...
  FOREIGN KEY (category) REFERENCES categories(name)
  ON UPDATE CASCADE ON DELETE SET NULL.
  Requires: backfill validation first (every distinct
  transactions.category value must exist in categories, or
  the constraint fails to apply). Renames then propagate
  automatically; category deletion nulls the transaction's
  category rather than orphaning it.
  Cost: the categorization agent writes category values
  from LLM output — if it ever emits a category name not
  in the table, the insert now fails hard instead of
  silently storing an unknown value. This is arguably
  correct behavior, but it is a behavior change and needs
  handling in the agent's write path.

  Option B — Formally forbid renames:
  No schema change. Document in ARCHITECTURE.md Invariants
  that category names are immutable once created, and that
  any future rename feature must be implemented as
  create-new + reassign-transactions + delete-old, never
  an UPDATE to categories.name.
  Cost: the protection is documentation, not enforcement —
  a future ticket could violate it.

  PM RECOMMENDATION: Option A. The failure mode Option B
  guards against is exactly the kind that survives review
  and detonates later; a hard constraint is worth the
  agent write-path handling. But present both fairly and
  take Borys's call.

Part 2 — Implement the chosen option.
  Option A: run the backfill validation FIRST and report
  results before applying the constraint (if any
  transactions.category value has no matching categories
  row, that is a data issue to surface, not silently
  fix). Then the migration, then the agent write-path
  handling.
  Option B: ARCHITECTURE.md Invariants entry plus a
  comment at the categories model.

ACCEPTANCE CRITERIA:
- Decision presented with both options and their real
  costs; Borys's choice recorded before implementation
- If A: backfill validation results shown BEFORE the
  migration is applied; constraint verified live; the
  categorization agent's behavior on an unknown category
  name is tested and described
- If B: invariant documented in both places
- ARCHITECTURE.md updated in the same commit

## AMENDMENT (2026-08-17)

Borys's decision: **Option A** (add the FK), per the PM's recommendation.

Part 2 implemented: migration `d3f8a5c6b9e2_add_fk_transactions_category.py`
(pre-flight backfill validation that raises with offending category values
before `ADD CONSTRAINT`, then the FK itself, `ON UPDATE CASCADE ON DELETE
SET NULL`), `models.py`'s matching `ForeignKey` declaration, and
`analysis_service.categorize_transactions`'s unknown-category filter on the
categorization agent's write path. ARCHITECTURE.md updated (Database Tables
row + new Invariants entry).

**Blocked, then closed (2026-08-18):** live backfill validation and the
live constraint test were blocked in the prior session — Docker Desktop's
backend processes were up but not responding to the CLI. Borys restarted
Docker Desktop; `docker compose up -d` brought the stack up, and the
backend's own startup applied migration `d3f8a5c6b9e2` automatically with
no pre-flight `RuntimeError` against the real 350-row dataset. Live-verified:
the FK exists exactly as designed (`\d transactions`), a rename of `'Other'`
→ `'Test Rename'` carried all 62 transactions with zero orphans then was
reverted, and a raw `UPDATE` to an unknown category name was rejected live
by the FK (rolled back cleanly) while the exact filter now in
`analysis_service.py` was confirmed to exclude that same value using the
real `categories` table. Full detail in `docs/verification_debt.md`'s
CLOSED section.

WHEN DONE:
- State the chosen option and show the implementation
- If A: show the backfill validation output and a live
  test of the constraint (rename a category, show
  transactions follow)
- Explain: why does budgets.category already have this
  FK while transactions.category does not?
- Do not start S5-03 until confirmed
