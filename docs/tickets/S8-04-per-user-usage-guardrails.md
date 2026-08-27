Status: delivered

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

--- PREMISE CHECK, before building (2026-08-28) ---

Checked S5-07's existing rate-limiting work first, per the ticket's
own instruction. `rate_limit.py`'s slowapi limiter is short-window
(N/minute, IP-keyed) burst protection — a different mechanism from
what this ticket needs (long-window daily/monthly cumulative caps,
per-user). No overlap, no second mechanism duplicating the first;
documented precisely in ARCHITECTURE.md.

Also found: `POST /api/analysis/categorize`/`insights` are not called
by the frontend at all — the real LLM-cost path for those two actions
is the sync job pipeline (`tasks/analysis.py`), calling
`analysis_service.categorize_transactions`/`generate_insights`
directly. Guarding only the REST endpoints would have protected a path
nobody uses while leaving the real one open — the cap check is placed
inside `analysis_service.py` itself, the one shared call site both the
real job pipeline and the unused REST endpoints go through.

WHEN DONE:

**Real evidence of a cap being hit and enforced:** seeded a real test
account to exactly the daily chat limit (50 real `usage_events` rows),
then made a real `POST /api/chat` request:

    HTTP 429
    {"detail":"You've reached today's beta limit for chat messages (50/day). Try again tomorrow."}

Confirmed the rejected call did not consume a slot — row count stayed
at 50 after the rejection, not 51. `test_usage_limits.py` (4 new
tests, all passing) exercises the exact boundary (limit-th call
succeeds, limit+1-th is rejected), the monthly window independently
of the daily one, and that caps are independent per-action and
per-user.

**Screenshot/example of the user-facing message:** real screenshot,
via the actual Chat UI (a fresh registered test account, seeded to the
same limit) — sent to Borys directly. Toast text: "You've reached
today's beta limit for chat messages (50/day). Try again tomorrow." —
not a raw 429, not a stack trace.

**No conflicting overlap with existing S5-07 rate limits:** confirmed,
documented in ARCHITECTURE.md's Invariants section — the two mechanisms
operate on different time scales (per-minute vs. per-day/month), keyed
differently (IP vs. authenticated user_id), and run independently.

Full backend test suite: 131/131 passing (127 pre-existing + 4 new).

Do not start S8-05 until confirmed
