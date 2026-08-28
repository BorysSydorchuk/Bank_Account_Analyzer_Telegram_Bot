Status: in-progress

================================================================
TICKET S8-07 — Feedback Channel & Onboarding Polish
================================================================

WHAT TO BUILD:

Part 1 — Feedback channel:
- A simple, real way for beta users to send feedback or report
  problems. Don't over-build this — a form that emails Borys
  via S8-05's Resend infrastructure, or even a straightforward
  mailto link, is sufficient for 10-20 people. Pick whichever
  is genuinely faster to build correctly and justify the choice
- Real test: send an actual message through it and confirm
  Borys receives it

Part 2 — Onboarding polish:
- A fresh-eyes walkthrough of the first-time user experience,
  starting from receiving a beta invite through to seeing real
  synced data. Use the same real invite/registration flow
  Borys just validated in S8-06 as the starting point — no need
  to build new scaffolding to test this, reuse what already
  works
- Specifically check: is the bank-picker step (KBC vs ING, from
  S8-01) clear to someone who's never seen this app? Is there
  any point where a genuinely new person would plausibly get
  stuck or confused?
- Fix anything glaringly confusing found. This is a polish
  pass, not a redesign — list what's found even if not
  everything gets fixed this ticket, don't silently skip items

ACCEPTANCE CRITERIA:
- Feedback channel real and functional, tested with a real
  message sent and received
- Onboarding walkthrough done with genuinely fresh eyes (or as
  close as achievable), issues found are listed explicitly,
  clear indication of which were fixed vs. deferred
- Anything deferred gets a real docs/verification_debt.md entry
  per the standing two-files rule — not just a mention in
  ARCHITECTURE.md prose, per the exact gap found and fixed in
  S8-06

WHEN DONE:
- Real evidence the feedback channel works end-to-end
- Full list of onboarding issues found, with fixed/deferred
  status for each
- Any deferred items' ledger entries
- Do not start S8-08 until confirmed
