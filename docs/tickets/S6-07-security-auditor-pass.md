Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

================================================================
TICKET S6-07 — Security Auditor Pass
================================================================

THIS IS A SECURITY AUDITOR TICKET, NOT A CODEE TICKET.

Per AGENTS.md, the Security Auditor role activates now,
before auth ships to any real second user. Boot a separate
Claude Code session for this — it never writes code, same
posture as the Reviewer, but its brief is adversarial: try to
find a way through, don't just check the intended path works.

BRIEF FOR THE AUDITOR (paste this as its task):

  Review the full authentication and authorization
  implementation from S6-01 through S6-06. You are not
  checking "does the happy path work" — the Reviewer already
  confirmed that ticket by ticket. Your job is to try to
  break it. Specifically:

  1. Session security: can a session id be guessed, forged,
     or replayed? Is the cookie correctly httpOnly/Secure/
     SameSite? What happens to a session after logout — is it
     truly dead, or just removed client-side?
  2. Password handling: is there any path where a password
     or its hash could leak into logs, error messages, or the
     verification_debt.md ledger (this project's specific
     known risk pattern from S5-06/S5-07)?
  3. IDOR sweep: independently attempt cross-user access on
     every by-ID endpoint, not just the ones S6-06's own test
     covered — look for ones that might have been missed.
  4. Account-linking logic (S6-03): can the Google/password
     linking be abused to take over an account (e.g.
     registering a password account with someone else's
     email, then linking via Google)?
  5. Rate limiting: are login/register genuinely protected
     against brute-force, or does the limit reset in a way
     that's trivially bypassed?
  6. The Category A/B distinction from S6-06: spot-check
     that nothing was miscategorized (a by-ID-shaped endpoint
     treated as list-shaped, missing its ownership check).

  Report findings the same way the Reviewer does — CRITERIA
  CHECK / FINDINGS / VERDICT — but weighted toward "what did
  I break," not "did it match the ticket."

ACCEPTANCE CRITERIA:
- Full audit report produced
- Every finding triaged: fixed immediately (if small), or
  a bounce back to Codee (if it touches real code), same
  confirm/bounce loop as every other ticket
- No sprint-close until this audit's findings are resolved,
  not just filed

WHEN DONE (this is Borys's summary once the audit and any
resulting fixes land):
- Audit report attached/summarized
- Every finding's resolution stated
- Do not start S6-08 until confirmed

---

## Annotation (Borys, 2026-08-21) — added before the audit starts

Two corrections/pointers to the brief above, so the auditor's limited
adversarial attention goes to genuinely open questions rather than
re-deriving what's already settled:

1. **`POST /api/categories` is confirmed protected.** An earlier draft of
   S6-06's own delivery notes wrongly claimed it was still
   unauthenticated — that was corrected (`docs/tickets/
   S6-06-full-query-scoping-ownership-checks.md`'s WATCH OUT FOR/KEY
   DECISIONS, commit `f1a80e5`). `routers/categories.py`'s
   `create_category` is gated by `get_current_user`, same as every other
   categories route. The auditor should not spend time rediscovering
   this — item 6's "spot-check the Category A/B distinction" can start
   from "this one's already confirmed correct," not treat it as unknown.
2. **Two concrete starting targets, both self-flagged by S6-06 itself as
   deferred to exactly this audit** (see that ticket's WATCH OUT FOR):
   - **Rate limiting on `chat`/`sync`/`analysis` is still IP-keyed, not
     `user_id`-keyed**, even though every one of those routes now
     resolves a real `current_user` (S6-06). This is squarely brief
     item 5's territory — worth checking whether IP-keying specifically
     (as opposed to the limit values themselves) creates a real bypass
     or fairness gap now that real user identity exists.
   - **Timing/enumeration side channels on the new by-ID `404` ownership
     checks** (`GET /api/jobs/{job_id}`, `PATCH /api/transactions/{id}`)
     were never audited for whether "doesn't exist" and "exists, not
     yours" are measurably distinguishable by response time — brief
     item 3's IDOR sweep should include this specifically, not just
     confirm the status code is right.

These aren't the only things to look at (the full brief above still
stands) — they're where S6-06's own delivery notes already pointed,
named as the reason this audit ticket exists rather than being folded
into S6-06 itself.
