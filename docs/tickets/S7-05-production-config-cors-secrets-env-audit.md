Status: delivered

================================================================
TICKET S7-05 — Production Config: CORS, Secrets & Env Audit
================================================================
(REVISED — much of the original scope was pulled forward
during S7-03/S7-04 out of necessity. This ticket is now
primarily an AUDIT confirming what's already true, closing any
real gaps, and formally documenting the final state — not a
from-scratch build.)

PREMISE CHECK FIRST, before anything else: read through
S7-01 through S7-04's ticket files and ARCHITECTURE.md's
current Secrets/Auth sections to establish exactly what secrets
management already exists (DB credentials via
manage_master_user_password, Google OAuth secret, Enable
Banking private key, SETTINGS_SECRET, etc.) before assuming
anything is missing. Flag anything this ticket describes that
turns out to already be done.

WHAT TO BUILD / VERIFY:

Part 1 — Secrets audit:
- Enumerate every secret the running application needs (DB
  connection, Redis connection if applicable, SETTINGS_SECRET,
  GOOGLE_CLIENT_SECRET, Enable Banking private key/app
  credentials, any others) and confirm each one's actual
  current source: AWS Secrets Manager (correct), a Terraform
  variable (needs fixing if so), or a container env file
  (needs fixing if so)
- Close any gaps found — specifically confirm
  GOOGLE_CLIENT_SECRET's status, since this was left unresolved
  earlier in the sprint and needs a definitive answer here if
  it hasn't already resolved itself
- Confirm no secret value has EVER appeared in: git history,
  CloudWatch logs, Terraform state files (if not using a
  secrets-manager reference), or any committed file

Part 2 — CORS:
- Confirm FRONTEND_ORIGIN is correctly set to
  https://mymble.be in the production environment (not
  localhost, not a wildcard)
- Verify no wildcard CORS configuration exists in any code
  path, dev or prod
- Real evidence: an actual CORS preflight request/response
  against the live https://mymble.be showing the correct
  Access-Control-Allow-Origin header

Part 3 — Environment separation:
- Confirm local dev and production configs cannot
  accidentally cross-contaminate (e.g., no shared credential
  file, no env var that could silently point dev at the real
  RDS/Redis instances)
- Document the full separation model in ARCHITECTURE.md

Part 4 — COOKIE_SECURE final state:
- S7-04 flagged COOKIE_SECURE=true was set before HTTPS
  existed, causing a documented interim breakage. Confirm
  that interim state is now fully resolved — cookies work
  correctly end-to-end against the live HTTPS ALB — and
  remove the interim-limitation note from ARCHITECTURE.md
  since it's no longer current

ACCEPTANCE CRITERIA:
- Every secret's source confirmed and documented, real
  evidence not narration
- GOOGLE_CLIENT_SECRET's status definitively resolved (already
  correct, or fixed now)
- CORS confirmed correct with real evidence against the live
  domain
- Environment separation documented
- COOKIE_SECURE interim-limitation note removed and replaced
  with confirmed-working status
- No secret ever found in git/logs/state files — if one IS
  found, treat with the same severity as this project's prior
  credential-exposure incidents (Sprint 5): stop, flag,
  do not silently fix, get Borys's explicit direction before
  any remediation

WHEN DONE:
- Real secrets-source table (secret name → actual source,
  verified)
- Real CORS preflight evidence against https://mymble.be
- Confirmation of environment separation
- Confirmation of COOKIE_SECURE working end-to-end
- Do not start S7-06 until confirmed

## DELIVERY (2026-08-26)

Premise check confirmed: S7-04's addendum already flagged "S7-05
inherits a head start" on secrets — true. This ticket's real work was
verifying and closing what was open, not building from scratch.

### Part 1 — Secrets audit (real evidence: `aws ecs describe-task-definition`)

| Secret | Source | Verified how |
|---|---|---|
| `DATABASE_URL` | Secrets Manager, `kbc-analyzer/database-url` (assembled from RDS's AWS-managed secret) | `secrets` field ARN, both task defs |
| `SETTINGS_SECRET` | Secrets Manager, `kbc-analyzer/settings-secret` | Same |
| `GOOGLE_CLIENT_SECRET` | Secrets Manager, `kbc-analyzer/google-client-secret` | Same, web only |
| `EB_PRIVATE_KEY_CONTENT` | Secrets Manager, `kbc-analyzer/eb-private-key` | Same, both |
| RDS master password | AWS-managed, never held by this project | Unchanged since S7-03 |

No secret appears as plaintext `environment` in either task definition
— confirmed by diffing the full `environment` list against the
`secrets` list for both. `infra/ecs.tf`'s `data
"aws_secretsmanager_secret"` blocks are read-only ARN lookups; checked
both local `.tfstate` caches directly for `GOCSPX`/`AKIA` patterns —
zero matches. Full repo git history checked the same way — zero
matches, and no `.env` file was ever committed (`git log --diff-filter=A
--name-only | grep -i '\.env$'` — empty). CloudWatch (`/ecs/kbc-analyzer`,
full history) checked for `GOCSPX`/`MasterUserPassword`/`AKIA` — zero
matches on all three.

**GOOGLE_CLIENT_SECRET status:** real evidence found that it was already
rotated — `describe-secret` shows two versions
(`AWSCURRENT`/`AWSPREVIOUS`), and CloudTrail confirms a `PutSecretValue`
by `KBC_analyser_deploy` at `2026-08-25 23:20:34 CEST`, ~7 minutes after
the commit (`4079462`, 23:13:05 CEST) that disclosed the exposure and
made the recommendation. Timing strongly suggests the regeneration
happened as recommended. **Not fully closeable from this environment**:
I have no API access to Google Cloud Console, so I cannot independently
confirm the *old* exposed value was actually revoked there — only that
the AWS-side value changed and the *current* value works (Google
sign-in confirmed live end-to-end by Borys, S7-04). Logged as OPEN in
`docs/verification_debt.md`, needs a one-line confirmation from Borys.

### Part 2 — CORS (real evidence)

```
$ curl -sv -X OPTIONS https://mymble.be/api/auth/login \
    -H "Origin: https://mymble.be" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type"
< HTTP/1.1 200 OK
< access-control-allow-origin: https://mymble.be
< access-control-allow-credentials: true

$ curl -sv -X OPTIONS https://mymble.be/api/auth/login \
    -H "Origin: https://evil.example.com" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type"
< HTTP/1.1 400 Bad Request
(no access-control-allow-origin header)
```

`FRONTEND_ORIGIN=https://mymble.be` confirmed directly in the live web
task definition — not localhost, not a wildcard. No second CORS
configuration path exists anywhere in the codebase (unchanged finding
from S5-07, re-verified).

### Part 3 — Environment separation

Documented in `ARCHITECTURE.md` (new subsection under AWS Deployment
Infrastructure). Structural, not just conventional: local `.env` points
at docker-compose service names unreachable outside that network;
production secrets are injected at the ECS layer with no file on disk
at all; RDS/Redis have no route from outside the VPC regardless of
credentials; `infra/.env` (AWS deploy creds) is a third, separate file
from both.

### Part 4 — COOKIE_SECURE (real evidence)

```
$ curl -s -D - -c cookies.txt -X POST https://mymble.be/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"s7-05-verify-test@example.com","password":"..."}'
< HTTP/1.1 201 Created
< set-cookie: session_id=...; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax; Secure

$ curl -s -w "\nHTTP %{http_code}\n" -b cookies.txt https://mymble.be/api/auth/me
{"id":"...","email":"s7-05-verify-test@example.com"}
HTTP 200
```

The interim-limitation note in `ARCHITECTURE.md` (S7-04's documented
~1-hour window where `Secure` cookies didn't survive the HTTP-only ALB)
is replaced with this confirmed-working evidence.

**Honest gap:** the test account above was not cleaned up — deleting it
requires `aws ecs execute-command` into the migration-runner task (same
pattern S7-04 used), which needs the Session Manager plugin; it isn't
installed on this machine. The migration-runner task was started,
confirmed running, then stopped cleanly (no ongoing cost) once exec
failed. Logged in `docs/verification_debt.md` — low urgency, an inert
test row, but not silently left undocumented.

### Acceptance criteria — final status

- Every secret's source confirmed with real evidence: **done**.
- GOOGLE_CLIENT_SECRET definitively resolved: **not fully** — AWS side
  confirmed with strong evidence, Google Console side needs Borys's
  one-line confirmation (logged as OPEN, not silently assumed).
- CORS confirmed with real evidence against the live domain: **done**.
- Environment separation documented: **done**.
- COOKIE_SECURE confirmed working end-to-end: **done**, real evidence
  above.
- No secret ever found in git/logs/state files: **confirmed**, zero
  matches across all three surfaces checked.

Two items need Borys before this closes fully: confirm the Google
Console secret rotation, and either install the SSM plugin or delete
the leftover test row directly. Everything else meets its acceptance
criterion with real evidence. Do not start S7-06 until confirmed.

## CLEANUP (2026-08-26) — test account deleted, ledger entry closed

Borys asked for the fastest path to delete
`s7-05-verify-test@example.com`. RDS Query Editor checked and ruled out
first (`aws rds describe-db-instances` confirms plain `postgres`
16.13 — Query Editor needs Aurora + Data API, not available on this
engine). Installed the Session Manager plugin (`winget install
Amazon.SessionManagerPlugin`), then repeated the migration-runner exec
pattern: `SELECT` before (row present), `DELETE` (rowcount 1), `SELECT`
after (empty) — plus a third, independent check against the live
`/api/auth/login` endpoint (`401 Invalid email or password`, proving
the deletion is visible from outside the exec session too, not just
inside the same DB connection that did it). Migration-runner task
stopped afterward. `docs/verification_debt.md`'s OPEN entry for this
moved to CLOSED with the real evidence.

Only the Google Console confirmation remains open.
