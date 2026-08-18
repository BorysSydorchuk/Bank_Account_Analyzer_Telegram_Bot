Status: confirmed
Source: issued directly in Claude Code session, 2026-08-17

*(S5-07 repo-wide check: this file carries real spending totals from live
verification, predating verification_debt.md's Conventions shape-only-
evidence rule — flagged as a known exception, not retroactively scrubbed,
same treatment as that file's own pre-existing entries.)*

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

---

## Delivery notes (Codee)

Backend: `GET /api/insights/compare` (`routers/insights.py`),
`comparison_service.py` (validation + delta computation),
`schemas.PeriodComparison`/`CategoryChange`/`ComparisonDelta`/
`ComparisonResponse`. Reused `crud.list_transactions` +
`statistics.compute_statistics` (live) and `crud.list_insights` (as-stored,
S4-04 Option B) rather than adding new queries. De-privatized
`statistics._format_date_range` → `format_date_range` (one-line rename,
docstring added) since this is now a second real caller, not a
speculative export.

Frontend: `components/dashboard/ComparePeriodsSection.tsx` (collapsed
`Card`, two `DateRangePicker`s reusing the existing shared component and
its standard presets, results grid + category table), `hooks/
useCompareInsights.ts` (a `useMutation`, not a query — nothing else reads
this), `lib/api.ts`'s `compareInsights`, `lib/dateRangePresets.ts`'s new
`getLastMonthRange`. Wired into `DashboardPage.tsx` directly below
`InsightsPanel`, per spec.

Live-tested in a real browser against the real 331-transaction dataset,
Docker stack up:
- Collapsed on page load; toggle expands/collapses correctly.
- Defaults confirmed: Period A = last full calendar month (Jul 1–31,
  2026), Period B = this month (Aug 1 – today).
- Compared Jul 1–31 vs Aug 1–16: totals €3.216,31 vs €81,27; center delta
  ▼ €3.135,04 (-97.5%) in green (decrease); category table sorted by
  absolute change descending, decreases green, and two categories with no
  July spend (Investments, Pet Care) correctly shown as red increases
  (`change_pct: null` on the backend, rendered without a "(N%)" suffix).
- Re-ran with Period B set to Aug 1–9 (an arbitrary, non-calendar-month
  range, and the one exact range with real stored insights): Period A
  column showed "No insights stored for Jul 1–31."; Period B column showed
  "Generated 9 Aug 2026" plus the 5 real stored insight cards — exactly
  the S4-04 Option B contract (never regenerated here).
- `tsc -b` and `oxlint` both pass clean.

Backend validation live-verified via curl directly (not through the UI,
since `DateRangePicker`'s own calendar already prevents picking a backwards
range or one >3 months via the presets): `period_a_from > period_a_to` →
`400 {"detail": "period_a: date_from must be before or equal to date_to."}`;
a 2020–2026 range → `400 {"detail": "period_a: range cannot exceed 365
days."}`. The frontend's handling of a 400 here is code-reviewed, not
UI-triggered: `useCompareInsights`'s `onError` uses the same
`ApiError`-message-in-a-toast pattern already live-verified elsewhere in
this app (`useDashboard.ts`'s sync error toast, S4-06's chat "no API key"
toast) — not logged as new verification debt, since it's the identical,
already-proven code path, not a new one.

Real two-period API response (Jul 1–31 vs Aug 1–9), abbreviated:
```json
{
  "period_a": {"date_range": "Jul 1–31", "total_spent": 3216.31, "insights": [], "insights_generated_at": null},
  "period_b": {"date_range": "Aug 1–9", "total_spent": 48.85, "insights": [/* 5 real rows */], "insights_generated_at": "2026-08-09T07:49:33.211306Z"},
  "delta": {
    "total_spent_change": -3167.46,
    "total_spent_change_pct": -98.5,
    "category_changes": [
      {"category": "Transfers", "period_a": 1872.5, "period_b": 10.0, "change": -1862.5, "change_pct": -99.5},
      {"category": "Investments", "period_a": 0.0, "period_b": 5.65, "change": 5.65, "change_pct": null}
    ]
  }
}
```

WHEN DONE — answered:
- Real two-period API response: above (full payload verified via curl
  during this session, not fabricated from the schema).
- Screenshot: captured expanded comparison with real totals, delta, and
  category table (this session's browser-tool output).
- Signed changes confirmed both directions: decreases green (5 categories),
  increases red (2 categories, both a 0→nonzero swing).
- Why statistics computed live but insights read from storage: this is the
  S4-04 Option B decision this ticket's PRECONDITION names — statistics
  are cheap, deterministic, and always correct straight from `transactions`
  regardless of when/whether insights were last generated; insights are an
  LLM call, expensive to regenerate on every comparison request, and
  storing them lets the UI honestly label *when* they were generated
  rather than silently regenerating (and potentially changing) them just
  because someone opened the comparison view.
