Status: plan
Source: issued directly in Claude Code session, 2026-08-21

---

================================================================
SPRINT 7 — "DEPLOYMENT & PUBLIC ONBOARDING"
KBC Personal Finance Analyzer
================================================================

SPRINT GOAL: the app runs on real AWS infrastructure, reachable
by a real domain over real HTTPS, with per-user bank sessions
and a web-only first-time bank connection flow — no terminal
step left anywhere. Transactional email exists, closing the
S6 email-verification/password-reset deferral. Sprint 6's
Finding A hardening lands here too.

Sprint 6 is fully closed. Read docs/multi_user_migration_plan.md
and ARCHITECTURE.md before starting — both are stale on the
deployment topology until this sprint updates them.

PLATFORM DECISION (already made): AWS. ECS Fargate or App
Runner for compute (Codee's call, justify in S7-01), RDS for
Postgres, ElastiCache for Redis. This is a bigger lift than a
PaaS like Railway/Render — expect this sprint to run longer
than prior ones. If AWS's learning curve threatens to balloon
the sprint the way Sprint 5's security work did, flag it
immediately and we split, same discipline as before.

HOW TO WORK THROUGH THESE TICKETS:
S7-01 through S7-10, in order. Every ticket through Reviewer
review as always. Commit this sprint plan to
docs/tickets/S7-00-sprint-plan.md (Status: plan) before S7-01.

================================================================
TICKET S7-01 — AWS Foundation & IaC Decision
================================================================

WHAT TO BUILD:
The account structure and infrastructure-as-code approach
everything else in this sprint builds on. No app deployment
yet.

DECIDE AND JUSTIFY:
- IaC tool: Terraform (most portable, most commonly requested
  on job postings per the market research) vs AWS CDK vs
  manual console setup for a solo project this size. Recommend
  Terraform unless you have a strong reason otherwise — it's
  the more CV-relevant skill and avoids console drift.
- Compute: ECS Fargate (more control, more AWS-native
  experience) vs App Runner (simpler, less to manage).
  Recommend Fargate — more transferable to real job
  requirements, worth the extra setup.

BUILD:
- AWS account/IAM setup: a dedicated IAM user or role for
  deployment (never use root credentials), least-privilege
  policy for what this project actually needs
- VPC with public/private subnets (app in private, ALB in
  public — standard pattern, and a good thing to be able to
  explain in an interview)
- ECR repository for container images
- State file handling for whichever IaC tool (S3 backend for
  Terraform state, not local)

ACCEPTANCE CRITERIA:
- IaC tool decision made and justified
- A real AWS account has the VPC/subnets/ECR/IAM role
  provisioned via code, not console clicks (or console clicks
  explicitly justified if IaC felt like overkill for a
  specific piece — say which and why)
- Nothing app-related deployed yet — this is foundation only
- No AWS credentials anywhere in git — confirm .gitignore
  covers whatever the IaC tool's local state/credentials
  files are

WHEN DONE:
- Show the provisioned resources (console screenshots or CLI
  output)
- State the IaC and compute decisions with reasoning
- Explain: why private subnets for the app tier?
- Do not start S7-02 until confirmed

================================================================
TICKET S7-02 — Containerize for Production & Push to ECR
================================================================

WHAT TO BUILD:
Production-ready container images, pushed to ECR. Not running
yet — that's S7-03/S7-04 once RDS/Redis exist to connect to.

WHAT TO BUILD:
- Multi-stage Dockerfiles for backend/frontend if not already
  (smaller production images, no dev dependencies shipped)
- Confirm the non-root user from S4-09 carries into the
  production image
- Frontend: production build (Vite build output served
  statically, not the dev server) — decide serving approach
  (nginx sidecar, or served by the backend, or a separate
  static host — your call, justify)
- CI step or documented manual process to build + push to ECR
  (a full CI/CD pipeline is nice-to-have, not required this
  ticket — a working, documented `docker build && push`
  sequence is the acceptance bar; note if you want to
  propose GitHub Actions as a follow-up)

ACCEPTANCE CRITERIA:
- Images build successfully, non-root confirmed in the
  production image
- Images pushed to ECR, tagged sensibly (not just `latest`)
- Frontend serving approach decided and working locally
  against the production build
- Documented build/push process (even if manual)

WHEN DONE:
- Show successful build + push
- State the frontend serving decision and why
- Do not start S7-03 until confirmed

================================================================
TICKET S7-03 — RDS & ElastiCache Provisioning + Data Migration
================================================================

PRIORITY: Real data migration — same care standard as every
prior data-touching ticket in this project.

WHAT TO BUILD:
- RDS PostgreSQL instance (private subnet, security group
  restricting access to the app tier only)
- ElastiCache Redis instance (same network restriction)
- Run the full Alembic chain against the new RDS instance
  from scratch — this is also the first time the whole
  migration history gets tested against a genuinely fresh
  target, not just the local dev DB's incremental history
- Migrate Borys's real data from local dev Postgres to RDS —
  dump/restore, verify row counts match exactly per table
  (same discipline as every prior migration in this project)
- Confirm session/job-lock/rate-limit Redis usage all work
  correctly against ElastiCache (not just local Redis)

ACCEPTANCE CRITERIA:
- RDS and ElastiCache provisioned via the S7-01 IaC approach
- Full migration chain applies cleanly to fresh RDS
- Real data migrated, row counts verified exactly matching
  source
- Local dev stack still works untouched (RDS is a new target,
  not a replacement for local dev)
- Security groups confirmed restrictive (not open to 0.0.0.0/0)

WHEN DONE:
- Show migration chain applying to fresh RDS
- Show before/after row counts for the data migration
- Confirm security group rules
- Do not start S7-04 until confirmed

================================================================
TICKET S7-04 — Domain, Real HTTPS, Retire mkcert
================================================================

WHAT TO BUILD:
- ACM certificate for a real domain (Borys needs to provide
  or register one — flag this dependency immediately if not
  already available)
- Application Load Balancer with the ACM cert, routing to the
  ECS/App Runner service
- Update Enable Banking's registered redirect URI to the real
  domain's callback path — this retires the mkcert-based
  local HTTPS catcher server from S3-07 entirely
- Remove/deprecate the mkcert-specific code path once the
  real HTTPS flow is confirmed working (don't leave dead
  code — but don't delete until proven working end-to-end)
- Update ARCHITECTURE.md's Auth/OAuth sections to reflect the
  new redirect target

ACCEPTANCE CRITERIA:
- Real domain resolves to the ALB over HTTPS, valid cert
- Enable Banking OAuth round-trips correctly against the new
  redirect URI (real test, not just config review)
- mkcert dependency fully retired, confirmed nothing still
  references it
- Local dev environment still works (this is a production
  concern, not a dev workflow change)

WHEN DONE:
- Show the domain resolving over HTTPS
- Show a real Enable Banking auth round-trip against the new
  URI
- Confirm mkcert is gone
- Do not start S7-05 until confirmed

================================================================
TICKET S7-05 — Production Config: CORS, Secrets, Env Separation
================================================================

WHAT TO BUILD:
- Move secrets (DB credentials, Redis connection, SETTINGS_
  SECRET, Google OAuth client secret, Enable Banking creds)
  out of .env-in-the-container and into AWS Secrets Manager
  or Parameter Store — .env stays for local dev only
- CORS: FRONTEND_ORIGIN now points at the real production
  domain, confirm no wildcard anywhere in any environment
  path (dev vs prod both checked)
- Confirm COOKIE_SECURE is correctly forced true in production
  (the env-gated default from S6-01 — this is where it
  actually matters)
- Environment separation: confirm local dev and production
  configs can't accidentally cross-contaminate (e.g. a
  misconfigured env var pointing dev at the real RDS instance)

ACCEPTANCE CRITERIA:
- No secrets in any container image or committed file
- Secrets retrieved from Secrets Manager/Parameter Store at
  runtime, verified working
- CORS confirmed non-wildcard in production
- COOKIE_SECURE confirmed true in production, false only in
  local dev
- ARCHITECTURE.md updated with the real production config
  requirements (this closes the "Sprint 6 must set X" notes
  left by S6-01/S6-05)

WHEN DONE:
- Show secrets retrieval working without any .env in the
  production container
- Show CORS/cookie behavior confirmed in production
- Do not start S7-06 until confirmed

================================================================
TICKET S7-06 — Per-User Enable Banking Session Storage
================================================================

BACKGROUND: Sprint 6 explicitly accepted a limitation — sync
restricted to Borys's account only, enforced rather than
built properly, because doing this right needed the public
deployment context this sprint provides.

WHAT TO BUILD:
- Replace the single global eb_session.json with per-user
  session storage — encrypted at rest (same Fernet pattern as
  API keys), keyed by user_id
- Each user's Enable Banking OAuth flow (requisition, session
  token, refresh) becomes fully independent of every other
  user's
- The reconnect/expiry banner (S2-02/S3-07) becomes per-user
  correctly — one user's expiring session shouldn't show a
  banner to another user
- Migrate Borys's existing session into the new per-user store

ACCEPTANCE CRITERIA:
- No global session file remains
- A second real or test user can have their own independent
  Enable Banking connection without touching Borys's
- Expiry/reconnect banner correctly scoped per user
- Borys's existing connection continues working through the
  migration

WHEN DONE:
- Show the per-user storage structure
- Show two independent sessions coexisting (Borys's real one
  + a test scenario)
- Do not start S7-07 until confirmed

================================================================
TICKET S7-07 — Web-Only First-Time Bank Authorization
================================================================

BACKGROUND: since Sprint 1, first-ever bank authorization on
a new setup has required `python -m kbc_analyzer.main` — a
terminal step, blocking real self-serve signup. This was
blocked on having a public callback URL, which S7-04 now
provides.

WHAT TO BUILD:
- A "Connect your bank" flow entirely in the web UI: user
  clicks connect → redirected to Enable Banking → picks their
  bank → authorizes → redirected back to the app, session
  established, zero terminal interaction
- This applies to ANY user's first connection now, not just
  Borys's original one-time setup
- Retire the CLI-based first-auth path as the primary flow
  (can stay as a fallback/debug tool, your call, but the web
  flow is what real users hit)

ACCEPTANCE CRITERIA:
- A genuinely new user (test account) can connect a bank
  account entirely through the browser, no terminal, no
  copy-paste
- Uses the per-user session storage from S7-06
- Real live test against Enable Banking's production flow

WHEN DONE:
- Show a real new-user bank connection completing entirely
  in-browser
- Do not start S7-08 until confirmed

================================================================
TICKET S7-08 — Transactional Email Infrastructure
================================================================

WHAT TO BUILD:
- AWS SES setup (sandbox → production access request if
  needed — flag the SES production access approval timeline,
  it can take a day or two, similar to the Anthropic key wait)
- A minimal email-sending service in the backend (from-address,
  templates for: verification link, password reset link)
- This unblocks the two items S6-08 explicitly deferred to
  Sprint 7

ACCEPTANCE CRITERIA:
- SES sending real emails to a real test address
- Email templates exist for verification + password reset
  (plain, functional — polish later)
- Close the S6-08 verification_debt.md entries this unblocks

WHEN DONE:
- Show a real email sent and received
- Do not start S7-09 until confirmed

================================================================
TICKET S7-09 — Email Verification, Password Reset & Finding A
================================================================

WHAT TO BUILD:
Three related hardening items, using S7-08's new capability:

1. Email verification: registration sends a verification
   link; unverified accounts get a clear, honest UI state
   (not blocked from using the app necessarily — your call,
   but state the decision)
2. Password reset: "forgot password" now actually works via
   email, replacing S6-04's "not available yet" placeholder
3. Finding A from S6-07's Security Auditor pass: make
   crud.link_google_id enforce its own invariants (reject
   overwriting an existing different google_id, reject
   linking an already-claimed google_id) rather than relying
   solely on the one caller's discipline

ACCEPTANCE CRITERIA:
- Registration → verification email → click link → verified,
  full round-trip
- Password reset round-trip works end-to-end
- link_google_id independently tested to reject both invalid
  cases even if called incorrectly (the point of Finding A)
- Security Auditor re-check on Finding A specifically before
  this ticket confirms

WHEN DONE:
- Show both email round-trips working
- Show link_google_id's new self-enforcement tested
- Do not start S7-10 until confirmed

================================================================
TICKET S7-10 — Sprint 7 Close
================================================================

WHAT TO BUILD:
Full production verification, same discipline as every prior
sprint close.

ITEMS:
1. Full regression sweep against the REAL production
   deployment, not local dev — every surface from prior
   sprint closes, plus the new deployment-specific flows
   (bank connect, email verification, password reset)
2. ARCHITECTURE.md: full accuracy pass reflecting AWS
   topology, real domain, production config
3. Cost check: confirm actual AWS spend matches expectations
   for a low-traffic solo deployment — flag anything
   surprising
4. verification_debt.md: zero stale entries; external_id
   per-account watch-item and any new deployment-specific
   gaps logged with real closure conditions
5. Security spot-check: re-run S6-07's IDOR sweep against
   the real production URLs, not just local dev

ACCEPTANCE CRITERIA:
- Production deployment fully regression-tested
- ARCHITECTURE.md accurate
- Cost within reasonable bounds, documented
- Ledger current
- Sprint 7 complete pending PM confirmation

WHEN DONE:
- Production regression results
- Cost summary
- Sprint 7 complete pending PM confirmation

================================================================
SPRINT 7 → SPRINT 8 HANDOFF
================================================================
Sprint 8 — "Multi-Bank": bank selection beyond KBC (start:
KBC + ING + BNP Paribas Fortis per the original roadmap),
per-institution API quirk handling, onboarding polish, soft
launch to 10-20 beta users. This is the first sprint where
someone other than Borys is meant to actually use the product.

================================================================
END OF SPRINT 7 TICKETS
================================================================
