Status: in-progress

================================================================
TICKET S9-05 — Billing UI
================================================================

WHAT TO BUILD:
- A simple Settings section: current plan, upgrade button
  (when free), cancel/manage button (when paid, likely via
  Stripe's customer portal rather than building a custom one —
  recommend this, justify)
- This UI is visible regardless of the kill switch state, but
  should say something sensible if billing isn't active yet —
  your call on exact copy, keep it honest (e.g. don't show an
  "Upgrade" button that leads nowhere useful while the kill
  switch is off)

ACCEPTANCE CRITERIA:
- Real UI, functional upgrade → real checkout → real return
  flow (test mode)
- Real cancel/manage flow via Stripe's portal (or justified
  custom alternative)
- Sensible, honest state when kill switch is off — real
  screenshot of both states
- Any deferred finding gets its own standalone ledger entry,
  per the now-consistent pattern

WHEN DONE:
- Real UI evidence, both kill-switch states
- Full upgrade/cancel flow evidence
- Do not start S9-06 until confirmed
