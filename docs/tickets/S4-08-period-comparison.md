Status: in-progress
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
TICKET S4-08 — Period Comparison  (built on the S4-04
                 semantics decision, Option B)
================================================================

PRECONDITION: S4-04's Option B is implemented. The numeric
comparison below is computed LIVE from transactions in all
cases; stored insights appear as supplementary context with
generated_at labels.

BACKEND:
  GET /api/insights/compare
  Params: period_a_from/to, period_b_from/to
  Response:
  {
    "period_a": {"date_range": "...", "total_spent": ...,
                 "by_category": [...], "insights": [...]},
    "period_b": {...},
    "delta": {
      "total_spent_change": 300.00,
      "total_spent_change_pct": 14.3,
      "category_changes": [
        {"category": "Groceries", "period_a": 180.00,
         "period_b": 220.00, "change": 40.00,
         "change_pct": 22.2}
      ]
    }
  }
  Statistics computed live; insights read from the table
  per the S4-04 decision (empty array if none stored for
  a range — never generate on the fly here).
  Validate: both ranges valid, ≤365 days each (per
  CLAUDE.md security rules).

FRONTEND — Dashboard "Compare Periods" section:
  Below the insights panel; collapsed by default on every
  load; toggle to expand.
  Two date-range pickers (Period A / Period B) with the
  standard presets; defaults last month vs this month.
  "Compare" button → results:
    Two columns with totals; center delta indicator
    (▲ red for increase, ▼ green for decrease, amount
    and percentage).
    Category comparison table: Category | Period A |
    Period B | Change (signed, colored).
    If insights exist for a period: show beneath its
    column with "generated <date>" label.

ACCEPTANCE CRITERIA:
- Correct deltas for two real ranges from actual data
- Signs and colors correct (increase red, decrease green)
- Collapsed by default on every page load
- Works for arbitrary ranges, not just calendar months
- Insight display matches the S4-04 Option B decision

WHEN DONE:
- Real two-period API response
- Screenshot of expanded comparison with real data
- Confirm signed changes render correctly both directions
- Explain: why are statistics computed live here while
  insights are read from storage?
- Do not start S4-09 until confirmed
