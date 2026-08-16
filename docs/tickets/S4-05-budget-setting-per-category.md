Status: confirmed
Source: sprint4_tickets_v2.txt (revised set)
Shipped as: 25e827d — feat: S4-05 budget setting per category

---

================================================================
TICKET S4-05 — Budget Setting Per Category  (MODIFIED:
                 user_id-ready schema per supervision report)
================================================================

WHAT TO BUILD:
Users set a monthly spending limit per category; the
dashboard shows budget usage.

BACKEND:
New Alembic migration — NOTE the user_id column, added
now so Sprint 6's multi-user migration does not need to
retrofit this table:

  CREATE TABLE budgets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NULL,          -- NULL = single-user era;
                                     -- Sprint 6 backfills and
                                     -- adds NOT NULL
    category     TEXT NOT NULL REFERENCES categories(name)
                 ON UPDATE CASCADE,
    amount       DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    period       TEXT NOT NULL DEFAULT 'monthly',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, category, period)
  );

  (Postgres treats NULLs as distinct in unique constraints —
  use UNIQUE NULLS NOT DISTINCT (user_id, category, period)
  on PG15+ so the single-user era still enforces one budget
  per category. Verify against PG16 and choose accordingly.)

New endpoints:
  GET /api/budgets
  Response: [
    {
      "category": "Groceries",
      "amount": 300.00,
      "period": "monthly",
      "spent_this_month": 187.40,
      "percentage_used": 62.5,
      "status": "on_track"
    }
  ]
  status: "on_track" (<80%), "warning" (80–100%),
  "exceeded" (>100%)
  spent_this_month = calendar month of today, not a
  rolling 30 days.

  POST /api/budgets
  Body: {"category": "Groceries", "amount": 300.00}
  409 if a budget for that category+period already exists.

  PATCH /api/budgets/{category}   Body: {"amount": 350.00}
  DELETE /api/budgets/{category}  → 204

All queries in crud must take user_id as a parameter
(pass None for now) — write the signatures multi-user-
ready even though the value is None until Sprint 6.

FRONTEND — Settings "Budgets" section:
  Budget cards: category name + color swatch, progress
  bar (green/amber/red by status), "€ X.XX spent of
  € Y.YY", edit + delete icons.
  "+ Set budget" inline form: category dropdown (from
  GET /api/categories, excluding categories that already
  have a budget), positive amount input, Save.

DASHBOARD — Budget overview widget:
  Between summary cards and category donut, rendered only
  if at least one budget exists. Compact horizontal cards:
  category, mini progress bar, status badge. Clicking
  navigates to Settings → Budgets.

ACCEPTANCE CRITERIA:
- Create / edit / delete budgets works in Settings
- Progress and status computed from real current-month
  spending
- Dashboard widget appears only when budgets exist
- Exceeded shows red, warning amber, on-track green
- budgets.user_id column exists, nullable, and every
  crud function signature accepts user_id
- ARCHITECTURE.md tables section updated in same commit

WHEN DONE:
- Screenshot: Budgets section with ≥2 real budgets
- Screenshot: dashboard widget
- Show one budget in warning or exceeded state from real
  spending data
- Explain: why calendar month rather than rolling 30 days?
- Explain: why add user_id now instead of in Sprint 6?
- Do not start S4-06 until confirmed
