Status: in-progress

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

WHEN DONE:
- Real evidence of a cap being hit and enforced
- Screenshot/example of the user-facing message
- Do not start S8-05 until confirmed
