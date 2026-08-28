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

**Root cause confirmation evidence:** confirmed via real CloudWatch
Logs, not assumed. `aws sesv2 get-account` shows still-sandbox
(`ProductionAccessEnabled: false`, `ReviewDetails.Status: DENIED`,
`CaseId: 178778410400368`). The real failure mode is more precise
than "sandbox blocks unverified recipients" — CloudWatch Logs shows
the actual exception for a genuinely new registration
(`liyaberry27@gmail.com`, 2026-08-27 22:00):
`botocore.exceptions.ClientError: AccessDenied ... not authorized to
perform 'ses:SendEmail' on resource '...identity/liyaberry27@gmail.com'`
— an IAM authorization failure on the recipient's identity ARN
specifically, the same quirk already documented in ARCHITECTURE.md's
Auth section (sandbox mode's IAM check covers both sender and
recipient identity ARNs). A second real registration
(`secta022024@gmail.com`, 2026-08-27 23:07) failed the same way —
real, ongoing impact, not a one-off.

**AWS Support Case follow-up content and current status:** could not
follow up via API — confirmed definitively, not assumed:
`aws support describe-cases` and `describe-severity-levels` both
return `SubscriptionRequiredException` (this account has no paid
Support plan; the Support API is entirely inaccessible regardless of
what's being requested). Attempted the one API-level lever that does
exist — a fresh `sesv2 put-account-details` resubmission with a
materially stronger use-case description (suppression list, DKIM
status, real current/expected volume) — rejected outright with
`ConflictException`. **No further action is possible from this
environment; the account structurally requires Console access, which
this environment doesn't have.**

**Contingency investigation result:** no faster AWS-native path
exists — sandbox mode's per-recipient restriction is independent of
sender-domain verification (`mymble.be` is already fully DKIM-verified
and it doesn't matter). Two real options identified: wait on the
existing case (needs Borys's console follow-up, response window
already passed), or switch to a different transactional email provider
entirely (real, ~1-2 day engineering effort, sidesteps this specific
SES account's denial). Neither adopted unilaterally — flagged to
Borys as a real decision, not made here.

**Not resolved.** A genuinely new address has not completed real
registration and received a real verification email — cannot be,
until either the case resolves or a contingency is chosen.

**Explicit re-check trigger:** AWS's own stated 24-hour response
window (from the 2026-08-27 01:05 CEST Support Center reply) has
already passed with the case status unchanged — this is the exact
"AWS doesn't respond within a short, explicit window" condition the
ticket names for escalating to Borys directly, not a further quiet
wait. Escalated this session. No further re-check from this
environment until Borys reports what the Console actually shows.

Do not start S8-06 (Beta Invite Mechanism) until this is either
resolved, or a contingency is confirmed sufficient to unblock real
beta registration some other way — status remains blocked on Borys's
decision.

--- ESCALATION OUTCOME (2026-08-28) ---

Presented the AWS-console-vs-switch-provider choice directly. Borys's
call: he checks the AWS Support Center console himself (case
`178778410400368`) — the one channel this environment structurally
cannot reach. Paused here pending his real findings; not proceeding
with a provider switch investigation unless the console shows the
case genuinely can't be resolved through AWS.

Borys checked directly, real result: AWS has not responded — genuinely
still silent, not a visibility gap on this environment's side. This is
not a new finding changing the diagnosis, just confirmation the wait
continues. No further escalation trigger has fired yet (that already
fired once, above); this is Borys reporting back on the escalation, not
a new stale-ledger cycle.

Flagged plainly: AWS's stated "24-hour response" was never a real
guaranteed SLA on Basic support (no paid tier means no committed
response time at all) — the wait has no real end date. Borys's call:
start real research into the provider-switch contingency now, in
parallel with the still-open AWS case, rather than wait unbounded.

--- CONTINGENCY RESEARCH, real current data (2026-08-28) ---

Researched Postmark, Resend, and SendGrid — real 2026 pricing, domain
verification requirements, new-account sending gates, and Python
integration shape, against this app's actual real usage (two
transactional email types, <100/day, mymble.be domain,
`app/email_service.py` currently a direct `boto3` SES v2 call with
zero stored credentials — IAM role auth).

| | Resend | Postmark | SendGrid |
|---|---|---|---|
| Free tier | 3,000/mo, 100/day — covers real stated volume | 100/mo only — too low for real use | Ambiguous in current sources (100/day permanent vs. 60-day trial only, depending on source) |
| New-account gate | None found for transactional domain-verified sending | Yes — new accounts need approval, ~1 business day | Yes — vetting review, reported up to a few hours |
| Domain verification | SPF + single DKIM record, often verified within ~15 min | DKIM + Return-Path record, DKIM shown verified within 48h | SPF+DKIM via Domain Authentication, timing not specified |
| Python integration | Official `resend` SDK — small, clean diff from the current `boto3` call | Official SDK/REST API, token-based | Official `sendgrid` SDK, key-based |
| Credential model | New: API key needs Secrets Manager storage | Same — API token to store | Same — API key to store |

**Recommendation: Resend**, if a contingency is actually adopted — free
tier alone covers real stated volume indefinitely, no new-account
approval gate found (vs. Postmark's ~1 business day and SendGrid's
hours-long vetting — both real but bounded, unlike AWS's open-ended
silence), fastest domain verification, cleanest code diff. Real
tradeoff worth stating plainly: this trades away SES's zero-credential
IAM-role auth for a real (small) API key that needs storing in Secrets
Manager and rotating — a new, if minor, secret-management surface this
app doesn't currently have for email.

Sources checked directly, not assumed: [Resend domain docs](https://resend.com/docs/add-a-domain),
[Resend Python send docs](https://resend.com/docs/send-with-python),
[Postmark domain verification](https://postmarkapp.com/support/article/how-do-i-verify-a-domain),
[Postmark getting started](https://postmarkapp.com/support/article/1002-getting-started-with-postmark),
[SendGrid account review](https://support.sendgrid.com/hc/en-us/articles/360041790293-Account-Under-Review),
[SendGrid sender identity](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/sender-identity).
