Status: in-progress

================================================================
TICKET S8-05 — Resolve SES Production Access Blocker
================================================================
(INSERTED after S8-04, 2026-08-28. Original S8-05 "Beta Invite
Mechanism" shifts to S8-06, "Feedback Channel & Onboarding
Polish" to S8-07, "Sprint Close" to S8-08.

Root cause: real beta users cannot register at all today — SES
sandbox mode silently refuses delivery to any recipient address
that isn't individually pre-verified, and only two addresses
have ever been verified. This blocks the sprint's actual goal.)

PRIORITY: This is the most urgent open item in the sprint.
Nothing about beta launch works until real strangers can
receive a verification email.

WHAT TO BUILD:

Part 1 — Confirm the diagnosis, don't assume:
- Check SES's current mode (sandbox/production) directly
- Check the exact status of AWS Support Case 178778410400368
  (or whatever case number is current) — resolved, still
  pending, needs more info from us, or was silently closed
- Check CloudWatch/SES sending statistics for a recent real
  registration attempt on a genuinely new, never-verified
  address — confirm it shows a rejection/bounce, not a
  different failure mode entirely
- If the diagnosis is confirmed: proceed to Part 2
- If something else is actually wrong: stop, report exactly
  what, before doing anything else

Part 2 — Push on the AWS Support Case:
- Review the original denial reason if AWS provided one
- If the case is still open/pending: post a follow-up update
  with any additional information AWS's Basic support tier
  might need (use case description, expected volume, this
  being a personal finance app requiring password
  reset/verification email as a core function)
- If Basic support plan visibility is limiting how much can
  be done here, state that plainly — this may be a case where
  the fastest resolution requires Borys's direct attention
  (AWS sometimes responds faster to account-holder follow-up
  than automated case updates)
- Set a real, dated re-check point — don't let this go stale
  in the ledger a third time; if AWS doesn't respond within a
  short, explicit window, escalate to Borys directly rather
  than silently waiting

Part 3 — Contingency, in case production access is still
pending when this ticket needs to close:
- Identify whether a different email-sending path exists that
  doesn't require SES production access — e.g., a different
  verified-domain approach, or whether SES's DKIM/domain
  verification (as opposed to per-recipient verification) can
  unlock broader sending faster than the general production
  access request
- If a real contingency exists and is meaningfully faster:
  propose it explicitly, with real cost/effort tradeoffs,
  rather than just waiting on AWS indefinitely
- If no faster path genuinely exists: state that plainly, and
  this ticket closes with the AWS case as the sole path
  forward, tracked with real urgency in the ledger — not
  quietly deprioritized

ACCEPTANCE CRITERIA:
- Root cause confirmed with real evidence (not assumed)
- AWS Support Case followed up on with real, specific content
- A contingency path investigated and either adopted or ruled
  out with real reasoning
- A real, dated re-check point set, visible in both
  ARCHITECTURE.md and verification_debt.md per the standing
  two-files rule
- If resolved: a genuinely new, never-verified address
  completes real registration and receives a real verification
  email — actual proof, not assumption

WHEN DONE:
- Root cause confirmation evidence
- AWS Support Case follow-up content and current status
- Contingency investigation result
- If resolved: real new-address registration proof
- If not yet resolved: explicit re-check date and what
  triggers escalation to Borys
- Do not start S8-06 (Beta Invite Mechanism) until this is
  either resolved, or a contingency is confirmed sufficient to
  unblock real beta registration some other way
