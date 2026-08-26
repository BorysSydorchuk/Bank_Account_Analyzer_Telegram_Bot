Status: delivered

================================================================
TICKET S7-08 — Transactional Email Infrastructure
================================================================

WHAT TO BUILD:
- AWS SES setup: verify a sending domain or address for
  mymble.be (likely no-reply@mymble.be or similar). Note SES
  starts in sandbox mode — sandbox can only send to verified
  recipient addresses, which is fine for testing but blocks
  real users receiving email. Request production access if
  needed and FLAG THE APPROVAL WAIT TIME explicitly — this has
  taken 1-2 days for other approvals in this project (the
  Anthropic key), plan around it, don't assume it's instant.
- A minimal email-sending service in the backend: one function
  that sends a templated email given a recipient, template
  name, and template variables
- Two templates needed for S7-09: email verification link,
  password reset link. Plain and functional — polish is not
  the goal this ticket, working delivery is.
- Confirm SES credentials/config are sourced from Secrets
  Manager or IAM role, not hardcoded — same standard as every
  other credential in this project post-S7-05's audit
- This unblocks docs/verification_debt.md entries deferred
  since S6-08 (email verification, password reset) — don't
  close them yet, that's S7-09's job, but confirm which
  entries this unblocks

ACCEPTANCE CRITERIA:
- SES verified and sending real emails to a real test address
  you control
- Both templates render correctly with real variables
  substituted (not placeholder text left in)
- Credentials sourced correctly (Secrets Manager/IAM role)
- If production access is pending: clearly state this as a
  known wait, and confirm sandbox-mode sending works for at
  least one verified test recipient in the meantime, so S7-09
  isn't fully blocked on SES approval

WHEN DONE:
- Show a real email sent and received (actual inbox
  screenshot or equivalent proof, not a "send succeeded" log
  line alone — mail delivery has failure modes an API success
  response won't catch, e.g. spam folder, bounce)
- State SES's current mode (sandbox/production) and, if
  sandbox, the production access request status
- Do not start S7-09 until confirmed

## DELIVERY (2026-08-27)

### What was built

- **`infra/ses.tf`** — `aws_sesv2_email_identity` for `mymble.be` (Easy
  DKIM), three Route53 CNAME records for the DKIM tokens,
  `aws_sesv2_email_identity` for a real test recipient
  (`var.ses_test_recipient_email`, sandbox mode requires the recipient
  verified too, not just the sender), and an IAM policy on
  `aws_iam_role.ecs_task` (the one role web + worker already share)
  granting `ses:SendEmail`/`ses:SendRawEmail` scoped to the domain
  identity's ARN.
- **No credentials anywhere** — boto3 resolves permission entirely from
  the ECS task's IAM role. Better than Secrets Manager here, not just
  equivalent: there is no key material to rotate or leak at all.
- **`app/email_service.py`** — `send_templated_email(to_email,
  template_name, **template_vars)`, two templates
  (`verify_email`, `password_reset`), each real HTML + text-fallback
  bodies with one substituted link. `UnknownEmailTemplateError` for a
  bad `template_name` — a clear caller error, not a raw `KeyError`.
- **`requirements.txt`** — `boto3` added.
- **Tests** — `tests/test_email_service.py`, real substitution asserted
  (no `{link}`/`{{` leftovers), the SES client itself mocked per
  TESTER.md's no-live-external-calls rule.

### Real evidence (not narration)

```
$ python -m pytest -q   # full suite
113 passed, 1 warning in 8.81s
```

**Domain verified fast** (DKIM `SUCCESS` within about a minute — the
Route53 zone is already fully delegated and controlled by this
project):
```
$ aws sesv2 get-email-identity --email-identity mymble.be
VerifiedForSendingStatus: true
DkimStatus: SUCCESS
```

**Production access — real, unexpected finding, not a rubber-stamp
wait.** The ticket anticipated a 1-2 day pending approval; instead
`aws sesv2 put-account-details` came back `ReviewDetails.Status:
DENIED` almost immediately. This account has no paid AWS Support plan
(`aws support describe-cases` → `SubscriptionRequiredException`), so
the actual reason wasn't retrievable via API — AWS emailed it instead,
asking for detail the bare API call doesn't have fields for: sending
frequency, recipient-list handling, bounce/complaint/unsubscribe
handling, example email content. Drafted the full reply from real,
verified facts (not invented): SES's account-level suppression list is
already active for both `BOUNCE` and `COMPLAINT`
(`aws sesv2 get-account` → `SuppressionAttributes`), confirmed before
citing it. Borys submitted it to Case `178778410400368` via AWS Support
Center (Basic support blocks posting to a case via API, confirmed —
only the console works). AWS's own message states an initial response
within 24 hours of that reply. **Still pending as of this delivery.**

**Sandbox-mode sending confirmed working — real email, real inbox.**
Borys's test-recipient identity is now verified
(`VerifiedForSendingStatus: true`, confirmed after he clicked SES's
confirmation link). First real send attempt (through the real
`send_templated_email` code path, no mocks) hit a real, informative
`AccessDenied`: sandbox mode's IAM check covers the recipient identity
ARN as well as the sender's, and the policy only granted the sender's.
Fixed properly in `infra/ses.tf` (added the test-recipient identity's
ARN to the policy's `Resource` list, not widened to `ses:*`), reapplied,
retested:

```
$ send_templated_email("boris.sydorchuk@gmail.com", "verify_email", link="https://mymble.be/verify-email?token=S7-08-real-send-test-token")
SEND_CALL_RETURNED_NO_EXCEPTION
```

**Real receipt confirmed by Borys** — "I got it" — not just the API
response, which mail delivery's own failure modes (spam folder,
bounce) an API success wouldn't catch.

### Which verification_debt.md entries this unblocks (confirmed, not closed)

- **"Email verification — not built (S6-04)"** — the "no transactional
  email infrastructure exists" blocker this entry names is now false;
  the entry itself stays OPEN, its closure needs S7-09's actual
  verification-token flow, not just the sending capability.
- **"Email-based password reset — not built (S6-04)"** — same: the
  shared blocker is closed, the entry's own closure is S7-09's job.

Neither entry edited in this ticket, per the ticket's own instruction.

### Answers to WHEN DONE

- **Real email sent and received:** confirmed above — real send
  through the real code path, real `AccessDenied` finding and fix
  along the way, real receipt confirmed by Borys directly ("I got
  it"), not inferred from the API's success response alone.
- **SES's current mode:** sandbox. Production access request status:
  an initial automated response came back `DENIED` almost immediately
  (faster than the 1-2 day wait the ticket anticipated), asking for
  more detail rather than being a final rejection. A full reply citing
  real, verified account facts was submitted via AWS Support Center
  (Case `178778410400368`) — Basic support blocks doing this via API,
  confirmed. AWS's own message states an initial response within 24
  hours of that reply; still pending as of this delivery.
- **Sandbox-mode sending confirmed working for S7-09:** yes — one
  verified test recipient can receive real templated email right now,
  so S7-09 is not blocked on the production-access outcome to build
  and test the verification/reset flows against that one address.
  Sending to arbitrary real users still needs production access.

Do not start S7-09 until confirmed.
