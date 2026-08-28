Status: done — Borys confirmed real receipt of the test feedback
email 2026-08-29, closing the one item this ticket was held open for

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

================================================================
WHEN DONE — answered 2026-08-28
================================================================

**Part 1 — feedback channel, real evidence:**

Built as a Resend-backed form (justification: S8-05's Resend
infrastructure was already wired up and proven reliable — a third
`email_service.py` template plus one authenticated route
(`POST /api/feedback`) was strictly less work than getting a `mailto:`
link's behavior consistent across every beta tester's OS/mail-client
setup, and doesn't depend on the tester having a desktop mail client
configured at all, which matters for a web app used from a browser). No
database table — one-shot notification for 10-20 people, not a
persisted support queue, same "don't over-build" call as S8-06's invite
CLI. Real test, run through the actual UI (`/feedback`, reachable from
the sidebar), logged in as the same real test account used for the
onboarding walkthrough below:

- Typed a real message and clicked "Send feedback" → toast: "Thanks —
  your feedback was sent."
- Backend access log: `POST /api/feedback` → `204 No Content`, no
  exception logged (the route logs and returns a clean `502` on any
  send failure — see `routers/feedback.py` — so a clean `204` here means
  `resend.Emails.send()` genuinely succeeded against the real Resend
  API, real API key, real recipient address).
- **Not yet confirmed: Borys actually receiving it in his inbox.** I
  have no access to that inbox to check myself — this is the one part
  of this acceptance criterion I cannot self-verify. Asking directly:
  Borys, can you confirm you got a real email titled "Mymble feedback
  from onboarding-walkthrough@example.com"? Holding this ticket at
  in-progress until you confirm — CLAUDE.md's testing standard doesn't
  let me mark "confirm Borys receives it" done from the sending side
  alone.

**Part 2 — onboarding walkthrough, full findings list:**

Walked the real flow end-to-end via real browser automation (not a
description): invite grant → register → hit the "verify email first"
gate on Sync → verify → log in → Settings → Bank Connection → Connect
→ real Enable Banking consent screen → Transactions/Chat empty states.
Reused S8-06's already-proven invite/registration mechanism, per the
ticket's instruction not to rebuild scaffolding for this.

1. **FIXED — `VerifyEmailPage` hung forever on "Verifying your
   email…"** even though the backend had genuinely completed the
   verification. The single most severe "would a new person get stuck"
   finding — indistinguishable from a broken signup to a real user.
   Full root-cause narrowing and fix in `docs/verification_debt.md`'s
   CLOSED entry (same day). Fixed by replacing `useMutation` with plain
   `useState`/`useEffect` async state in `VerifyEmailPage.tsx`.
2. **FIXED — inconsistent product name.** Three in-repo instances still
   said "KBC Analyzer" while every auth page already said "Mymble":
   the sidebar and the mobile-fallback screen (`Sidebar.tsx`, `App.tsx`)
   — both found by the real browser walkthrough — and the FastAPI app
   title (`main.py`, `FastAPI(title=...)`), which renders on the public,
   unauthenticated `/docs` page at `https://mymble.be/docs` but isn't
   reachable by clicking through the actual app, so the walkthrough
   missed it — caught in review instead. All three now say "Mymble".
3. **DEFERRED — Enable Banking's real consent screen says "KBC Personal
   Tracker."** A third stale product name, on an external page this
   repo doesn't control (Enable Banking's own developer portal). Ledger
   entry: `docs/verification_debt.md`'s "Enable Banking consent screen
   shows stale app name" (OPEN).
4. **Checked, no issue found — the KBC vs ING bank picker (S8-01) is
   clear.** Settings → Bank Connection shows two distinctly labeled
   rows ("KBC — not connected", "ING — not connected"), each with its
   own "Connect" button. Nothing ambiguous about which button connects
   which bank.
5. **Checked, no issue found — the pre-verification gate is clear.**
   A fresh account without a verified email sees a dashboard banner
   ("Verify your email to connect a bank account — check your inbox
   for the link.") and, if it clicks "Sync & Analyze" anyway, a clean
   toast explaining exactly why the sync didn't run and what to do.
6. **Checked, no issue found — empty states.** Dashboard, Transactions,
   and Chat all render clear, non-alarming empty states for a
   brand-new account with zero data ("No transactions found for the
   selected filters.", "Chat with your finances" starter prompts,
   etc.) — nothing that reads as broken.

Did not attempt a real KBC/ING bank login — that needs real banking
credentials this environment doesn't have and shouldn't touch; the
actual bank-connection mechanics (not the onboarding UX around it) were
already proven working in S7-07/S8-01/S8-02, out of this ticket's scope
to re-verify.

**Ledger entries added:** two — the Enable Banking stale-name OPEN
entry, and a CLOSED entry documenting the `VerifyEmailPage` bug's full
root-cause narrowing for future reference.

Ready for S8-08 once you've confirmed both this write-up and that the
feedback email actually landed in your inbox.
