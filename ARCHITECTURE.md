# ARCHITECTURE.md

Current-state record of the KBC Personal Finance Analyzer. Describes what
**is**, never what was or what's planned — see git history for the former,
sprint tickets for the latter. Project root is `kbc_analyzer/`; all paths
below are relative to it unless stated otherwise.

**Verification note:** Services & Ports below verified live 2026-08-17
(S4-10 sprint close) via `docker compose ps` against a clean
`docker compose down && docker compose up -d` — all five containers
healthy, port bindings match exactly. (Originally written S4-03 against
static config only, since Docker Desktop's daemon wasn't running then;
that gap is now closed.)

**Sprint 5 close re-verification (2026-08-19, S5-08):** every claim in this
file re-checked against the running system and current source, top to
bottom — non-root UIDs confirmed live (`docker compose exec backend
whoami` / `celery_worker` → `appuser`), every referenced symbol name
confirmed to still exist at its stated location, Database Tables
cross-checked against `models.py` column-by-column (no drift), sync-lock
enforcement re-confirmed live. All line-number references (`file.py:NN`)
replaced with stable section/symbol names throughout this file — line
numbers had already gone stale twice during Sprint 4 and are no longer
used as anchors here.

**Sprint 6 close re-verification (2026-08-21, S6-08):** every claim
re-checked against the running system, live, not recalled — non-root UIDs
re-confirmed (`docker compose exec backend`/`celery_worker whoami` →
`appuser`), the full public/protected route split live-curled end to end
(`/health` 200, `google/login` 307, `logout` 204 with no cookie required;
`categories`/`budgets`/`transactions`/`statistics`/`insights`/`jobs/{id}`/
`settings` all 401 with no session cookie), bcrypt pin (`<4.1`) and all
five rate-limit constants (`CHAT`/`SYNC`/`ANALYSIS` 20-or-10/minute,
`LOGIN`/`REGISTER` 5/minute) confirmed against `rate_limit.py` and
`requirements.txt` directly. A full browser regression pass ran as the
real authenticated user against the real dataset (49 transactions):
Dashboard, Transactions (list/search/filter), Chat (real streamed,
correctly-scoped reply), and Settings (including the new S6-07
`AccountSection` linking control) all rendered cleanly with zero console
errors. Logout was deliberately not clicked live this pass — the only
active session on this machine, with no way to re-authenticate from it
in the moment — covered instead by the existing automated
session-destruction tests. No drift found beyond what this file's own
S6-07 entries already captured.

## Services & Ports

| Service | Image/build | Port | Serves |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | Postgres, `pg_isready` healthcheck |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI (`app.main:app`); runs `alembic upgrade head` then `uvicorn --reload` on every start |
| `frontend` | `frontend/Dockerfile` | 5173 | Vite dev server |
| `redis` | `redis:7-alpine` | 6379 | Celery broker (db 0) + result backend (db 1) |
| `celery_worker` | `backend/Dockerfile` (same image as backend) | none published | `celery -A app.celery_app worker` |

**RETIRED (S7-04):** `celery_worker` used to also publish port 3001 for a
local HTTPS catcher server that caught Enable Banking's OAuth redirect
(S3-07 Item 2) — that server, its Celery task, and the mkcert
certificate it used are all deleted, not just unused. Enable Banking's
OAuth redirect now lands directly on the real production domain's own
`GET /api/auth/enable-banking/callback` route (see the ACM/HTTPS section
further down) — proven working end-to-end via a real live reconnect
against `https://mymble.be`, which is what closed this out. A developer
who needs to exercise the Enable Banking OAuth flow purely locally
(without hitting the real production domain) uses the `POST /callback`
manual-paste fallback instead — same mechanism as before S3-07 Item 2
ever existed.

`backend` and `celery_worker` both run as a non-root `appuser`
(`backend/Dockerfile`, S4-09 Item 1) — the image's final `USER appuser`
directive, after dependencies are installed and the source is copied as
root. Verified this doesn't break `eb_session.json`/cert access: Docker
Desktop's Windows bind mounts report `rwxrwxrwx` regardless of the
container's UID, so this isn't the classic root-owned-files failure mode a
native Linux host would hit — worth re-verifying if this project ever runs
on a Linux Docker host.

`frontend`'s Vite dev server watches with polling (`vite.config.ts`,
S4-09 Item 2: `usePolling: true, interval: 1000`) — Docker Desktop's
bind-mounted volumes don't reliably deliver native filesystem change
events into the container, so the default watcher silently missed edits
without this.

`backend` has `logging.basicConfig(level=logging.INFO, ...)` (`main.py`,
S4-09 Item 3) — before this, the uvicorn process had no logging
configuration at all, so every `logger.info()` call anywhere in the app
was silently dropped for it (Python's root-logger fallback only emits
WARNING+). `celery_worker` never had this problem — its `--loglevel=info`
CLI flag already configures its own root logger.

## AWS Deployment Infrastructure

**Foundation only — no application runs here yet.** The app itself still
only runs via local Docker Compose (see Services & Ports above). This
section describes the AWS account structure provisioned in S7-01, which
later S7 tickets deploy the actual application onto.

**IaC:** Terraform, root at `infra/` in the monorepo. State is remote (not
local): an S3 backend bucket `kbc-analyzer-terraform-state-<account-id>`
(versioned, AES256-encrypted, all public access blocked) with DynamoDB
table `kbc-analyzer-terraform-lock` for state locking. The bucket and lock
table themselves are created by a separate small config, `infra/bootstrap/`,
which necessarily uses local state (it creates the backend the main config
depends on — a chicken-and-egg the bootstrap config exists to solve).
Credentials for `terraform`/`aws` commands are never committed — they live
in `infra/.env` (gitignored) for local dev use only.

**Region:** `eu-central-1` (Frankfurt) — chosen over `eu-west-1` for
proximity to the target Belgian bank APIs and because GDPR data-residency
is already on the Sprint 9 roadmap; keeping data in an EU region other
than the account default was a deliberate choice, not AWS's default.

**Compute model (final, after three rounds of revision — see
`docs/tickets/S7-01-aws-foundation.md`):** unified ECS Fargate, one
cluster, two services — a web service (FastAPI + frontend, behind an ALB,
not yet created) and a worker service (Celery, no ALB — it has no HTTP
listener to route to). App Runner was evaluated and rejected because its
single-container HTTP-serving model doesn't cleanly host a non-HTTP
background worker like Celery. Redis will be a self-hosted container in
the same cluster, not ElastiCache — a deliberate cost saving at this
traffic scale, not yet provisioned as of S7-01.

**Network (provisioned, S7-01 — resource IDs live-verified 2026-08-25.
Raw `terraform output`/`terraform show` and raw `aws budgets
describe-budget`/`describe-notifications-for-budget` output, plus
independent live-AWS cross-check, are in
`docs/tickets/S7-01-aws-foundation.md`'s second Reviewer-follow-up
amendment — not duplicated here to avoid two copies of the same
evidence drifting apart):**

| Resource | ID | Value |
|---|---|---|
| VPC | `vpc-0ff5461f79e531821` | CIDR `10.0.0.0/16` |
| Public subnet (1a) | `subnet-0e75497bcd1a73a6f` | `10.0.0.0/24` — hosts the NAT Gateway |
| Public subnet (1b) | `subnet-00a04d56c7b5ef82e` | `10.0.1.0/24` — will host the ALB |
| Private subnet (1a) | `subnet-0f95c89b63cf3becd` | `10.0.10.0/24` — will host both Fargate services, RDS, Redis container |
| Private subnet (1b) | `subnet-03bff6a6b9d70b530` | `10.0.11.0/24` — same, other AZ |
| NAT Gateway | `nat-09837d89472437832` | **Single** (not one per AZ) — both private subnets route through it |
| Internet Gateway | (see `infra/vpc.tf` — 1, attached to the VPC) | |
| ECR repo (web) | `arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-web` | |
| ECR repo (worker) | `arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-worker` | |
| IAM deploy user | `arn:aws:iam::904854373619:user/deploy/kbc-analyzer-deploy` | ECR push/pull only |

The single NAT Gateway is a deliberate cost/availability tradeoff for a
portfolio-scale solo project: if the AZ holding the NAT Gateway has an
outage, the *other* AZ's private subnet loses outbound internet access
too, even though that subnet itself stays healthy. This is intentional,
not an oversight — see the NAT Instance follow-up entry in
`docs/verification_debt.md` for the (deferred) cheaper alternative and its
own tradeoffs.

**IAM (provisioned, S7-01):** a dedicated deployment identity,
`kbc-analyzer-deploy` (IAM user, path `/deploy/`), scoped today to ECR
push/pull only against the two repos below — not broader, since nothing
else exists yet for it to need access to. Permissions grow ticket-by-
ticket as ECS/RDS/Secrets Manager resources are created, not granted
upfront. **Note:** this account also has a pre-existing IAM user,
`KBC_analyser_deploy` (different casing, created outside this project's
Terraform), holding `AdministratorAccess`. That user was used to bootstrap
S7-01 (create the budget, state backend, and the new scoped deploy user)
but is not managed by this project's Terraform and is not the identity
CI/deploy processes should use going forward — flagged for Borys to
decide whether to retire it.

**Container registry (provisioned, S7-01):** two ECR repositories,
`kbc-analyzer-web` and `kbc-analyzer-worker`, both with
`image_tag_mutability = IMMUTABLE` (a tag, once pushed, can't be
overwritten — enforces the "tag sensibly, not just `latest`" discipline
S7-02 asks for at the infrastructure level) and scan-on-push enabled.

**Image build (S7-02):** one Dockerfile, `kbc_analyzer/Dockerfile.prod`
(build context `kbc_analyzer/`, not `backend/` alone — the web target
needs `frontend/` too), multi-stage with two build targets:

- `worker` — Celery only. `docker build -f Dockerfile.prod --target worker`.
- `web` — FastAPI + the compiled frontend (Vite production build,
  `npm run build`), served by FastAPI itself via a `StaticFiles` mount
  and an SPA-fallback catch-all route in `app/main.py` (only active when
  a `static/` directory exists — absent in local dev, where the frontend
  still runs via its own Vite dev server, so dev behavior is unchanged).
  `docker build -f Dockerfile.prod --target web`.

Both targets share a `python-deps` stage (dependencies installed once
into a venv, so both images are guaranteed to run identical dependency
versions) and a `runtime-base` stage (non-root `appuser`, S4-09's
convention carried into both — verified live via `docker run ... whoami`
on both images, not just asserted from the Dockerfile). `runtime-base`
copies only `app/`, `kbc_analyzer/`, and `alembic.ini` from `backend/` —
an explicit allowlist, not `COPY backend/ .` — because `backend/` also
holds `eb_session.json`, `private.pem` (Enable Banking's real private
key), and `certs/` (a TLS key), none of which should ever be able to
land in an image pushed to a registry. `kbc_analyzer/.dockerignore`
excludes them too, but the allowlist doesn't depend on that staying
correct. Verified empirically: neither built image contains any of
those files.

Images are tagged `<git-short-sha>` (immutable repos reject a repeat
tag outright, which is the point — see S7-02's ticket file for the real
`docker build`/`push` output and `aws ecr describe-images` evidence).
No CI pipeline yet — build/push is a documented manual sequence; S7-02's
ticket file flags GitHub Actions as a worthwhile follow-up, not built
now.

**Real bug found and fixed (2026-08-26, S7-04): `VITE_API_URL` was
never wired into the build.** `frontend/src/lib/api.ts` reads
`import.meta.env.VITE_API_URL ?? "http://localhost:8000"` — a Vite
**build-time** substitution, not something a container's runtime
environment can influence. S7-02's `Dockerfile.prod` never declared it
as a build `ARG`, so every image (including the ones actually deployed
in S7-04) silently baked in the `localhost:8000` dev fallback. Real
production symptom: registration and Google sign-in both failed on
`mymble.be` with **zero requests ever reaching the backend** — confirmed
via CloudWatch (`/ecs/kbc-analyzer` web log streams filtered for
`register`/`google`/error patterns and by time range: only `/`,
`/assets/*`, `/health` traffic, no `/api/auth/*` POSTs at all) — because
the browser was silently POSTing to the visitor's own machine, not the
deployed backend. This ruled out an earlier hypothesis (that
`GOOGLE_CLIENT_SECRET` was never actually wired into Secrets Manager) —
the request never got far enough for that secret to matter.

Fixed: `ARG VITE_API_URL=""` in `Dockerfile.prod`, promoted to `ENV` for
the `npm run build` step (Vite only reads real env vars, not raw Docker
args). Defaults to an **empty string, not the ALB/domain URL** — S7-02's
own design already serves the frontend and API from one FastAPI origin,
so `api.ts`'s `${API_URL}${path}` pattern produces plain relative paths
(`/api/...`) that resolve against whatever origin actually served the
page. More robust than hardcoding `mymble.be` into the image: works
unchanged if the domain ever changes, and doesn't require rebuilding
images per-environment.

**RDS & Redis (provisioned, S7-03):** real bank data now lives on AWS
for the first time. RDS PostgreSQL 16, `db.t4g.micro`, Single-AZ, 20 GB
gp3, private subnets only (`aws_db_subnet_group`), deletion protection
and a final snapshot on destroy both on — this instance holds real
migrated financial data, not throwaway test data. Master credentials are
AWS-managed (`manage_master_user_password`, an auto-rotated Secrets
Manager secret) — this project never holds the master password itself,
anywhere.

| Resource | Identifier |
|---|---|
| RDS instance | `kbc-analyzer-db` |
| RDS endpoint (host:port, no credentials) | `kbc-analyzer-db.c34kquggcima.eu-central-1.rds.amazonaws.com:5432` |
| RDS security group | `sg-0a5edd4f0ba3c0dce` — inbound 5432 from the app SG only, no CIDR ranges at all |
| Redis (self-hosted, Fargate, S7-01's decision) | ECS service `kbc-analyzer-redis`, own task, no ALB |
| Redis reachable at | `redis.kbc-analyzer.internal:6379` (AWS Cloud Map private DNS, namespace `kbc-analyzer.internal`) — not a raw task IP, which changes on every task replacement |
| Redis security group | `sg-0fe7c9d8fb1dfe17e` — inbound 6379 from the app SG only, no CIDR ranges at all |
| App security group (placeholder) | `sg-016088c92a7c160f7` — represents whatever runs the Fargate web/worker services (not created until a later ticket) and one-off in-VPC tasks; RDS/Redis name only this SG as their allowed source |
| ECS cluster | `kbc-analyzer-cluster` |

**Migration verified, not just executed:** the full Alembic chain
(`1149a517cb33` baseline through `5c9a2e6b8f14` head — every migration
since S2-01) applied cleanly to a genuinely fresh RDS instance with zero
errors. Real local dev data (366 transactions, 50 insights, 10
categories, 3 budgets, 3 settings, 1 user) migrated via `pg_dump`/
`pg_restore`, verified matching exactly, per table, before vs after. A
real Fernet-encrypted API key (`gemini_api_key`, `anthropic_api_key`)
decrypted correctly post-migration using the same `SETTINGS_SECRET` —
the encryption round-trip survives the environment crossing. All three
genuinely Redis-backed features (`app/auth/session.py`, `app/sync_lock.py`,
`app/job_store.py`) confirmed working end-to-end against the new AWS
Redis via real function calls, not just a container health check.
`rate_limit.py` is explicitly **not** Redis-backed (in-memory, see this
file's Auth section) — nothing to verify there; the gap is tracked in
`docs/backlog.md`, not silently assumed fixed.

**How this was actually run:** RDS and Redis sit in private subnets with
no route from outside AWS at all — a security group can't fix that,
only a route table can. All of the above ran from *inside* the VPC, via
a temporary `kbc-analyzer-migration-runner` ECS task (reusing the S7-02
worker image, which already has `alembic`/`psycopg`/`redis-py`),
connected to via `aws ecs execute-command` (ECS Exec), then stopped —
never a persistent service. Full real command output, including the
migration chain, row-count verification, and decryption test, is in
`docs/tickets/S7-03-rds-redis-migration.md`.

**Free Tier discovered:** this AWS account is on AWS Free Tier — found
empirically when RDS rejected a 7-day backup retention with
`FreeTierRestrictionError` (reduced to 1 day). This likely means actual
spend for the first 12 months is meaningfully lower than S7-01's ~$122/mo
estimate, which didn't assume Free Tier eligibility. Not re-priced here —
flagged for whoever next reviews the cost picture (S7-10 sprint close is
the natural point).

**Web/worker ECS services & ALB (provisioned, S7-04 — product renamed
"Mymble," domain `mymble.be`):** the app's actual compute finally exists.
`kbc-analyzer-web` and `kbc-analyzer-worker` ECS services (Fargate, one
task each, private subnets, the `app` security group), running the
S7-02 images. Both confirmed live: `GET /health` through the real ALB
returns `{"status":"ok"}` (a genuine RDS connection via Secrets
Manager, not a stub), target group health `healthy`, worker service
`running`.

| Resource | Identifier |
|---|---|
| ALB | `kbc-analyzer-alb`, DNS `kbc-analyzer-alb-537799089.eu-central-1.elb.amazonaws.com` |
| ALB security group | `sg-0bd8965cccddf22bc` — the **one** legitimate `0.0.0.0/0` rule in this architecture (80/443 inbound); everything else stays locked to the `app` SG |
| Web target group | `kbc-analyzer-web`, health check `GET /health`, matcher `200` only (a 503 correctly marks the target unhealthy, same as any other outage) |
| Route 53 zone | `mymble.be` (`Z083187235H4ID5UIOWLI`) — **not yet delegated**; registered externally, needs NS delegation at the registrar (Borys's action, see below) |

**Secrets (Secrets Manager, created directly via CLI — values never
touch Terraform state):** `kbc-analyzer/settings-secret`,
`kbc-analyzer/google-client-secret`, `kbc-analyzer/eb-private-key`,
`kbc-analyzer/database-url` (assembled from the RDS-managed secret).
Injected into both task definitions via the container `secrets` field,
resolved by the execution role before the container starts. The Enable
Banking private key (`private.pem`, deliberately excluded from the
S7-02 image) is written to `/tmp/private.pem` by a command-override
script at container start, matching `ENABLEBANKING_PRIVATE_KEY_PATH` —
no image rebuild needed to supply it.

**Production Enable Banking callback route
(`GET /api/auth/enable-banking/callback`, `app/routers/auth.py`):**
replaced the mkcert-based local catcher server's role for production.
That server (`app/eb_callback_server.py`, now deleted) only ever
existed because local dev has no publicly-reachable HTTPS endpoint for
Enable Banking's redirect to land on — it ran its own temporary HTTPS
listener on a separate port. A real domain behind an ALB doesn't need
that: this route *is* the reachable endpoint. **Retired (S7-04):**
`eb_callback_server.py`, `app/tasks/auth.py`, and the mkcert certificate
they used are all deleted — a real live Enable Banking reconnect against
`https://mymble.be` proved the new path works end-to-end first, per this
project's standing practice of not deleting the old path until the new
one is proven working.

**CSRF state validation (added same day, before this route had ever run
against real production traffic):** `POST /reauthorize` now generates
its own `state` (`secrets.token_urlsafe(24)`), stores it in a new
`eb_oauth_state` cookie (httponly, `secure=COOKIE_SECURE`,
`samesite=lax` — same shape as `user_auth.py`'s `oauth_state`), and
passes it through to Enable Banking (`enablebanking.py`'s `start_auth`,
`eb_service.py`'s `get_reauthorize_url`) instead of the value those
methods used to generate and immediately discard ("not checked by us
but required by the spec"). The callback compares the cookie against
Enable Banking's returned `state` and rejects any mismatch or missing
cookie with a 400 before ever calling `complete_reauthorization`. This
mattered here specifically because moving the callback from
localhost-only to a public domain turned a latent gap into a real one —
a forged link could otherwise trick an already-authenticated user's
browser into completing reauthorization with an attacker-supplied code.
Verified with a real `TestClient` round-trip (dependency-overridden, no
live bank credentials needed): matching state passes through to
`complete_reauthorization`, mismatched state and no-cookie-at-all both
correctly 400.

`enablebanking.py`'s `REDIRECT_URL` is `EB_REDIRECT_URL`-driven (defaults
to `https://localhost:3001/callback`, a placeholder-only value now that
mkcert is retired — see below; set to
`https://mymble.be/api/auth/enable-banking/callback` in the web ECS
task's environment) — the request Enable Banking receives has to carry
the same redirect URL that's actually registered for it, or it's
rejected regardless of what's registered in the portal.

**RESOLVED (2026-08-26):** the interim COOKIE_SECURE/no-HTTPS limitation
below no longer applies — real HTTPS is live (see the ACM/ALB section
further down). Left here, struck through in spirit rather than deleted,
as a record of a real interim state this project actually shipped
through, not because it's still true: the web task set
`COOKIE_SECURE=true` while the ALB only had an HTTP:80 listener, so no
session/state cookie survived a round trip against the ALB for the
roughly one-hour window between S7-04's first delivery and DNS
delegation actually going live. Nothing shipped to real users during
that window; local dev was never affected.

**ACM certificate & HTTPS (S7-04, real evidence — 2026-08-26):**
`mymble.be` now serves real, CA-validated HTTPS. ACM certificate
(`infra/acm.tf`), DNS-validated via a CNAME in the Route 53 zone this
project controls (not email validation — survives renewal
automatically without action). ALB has two listeners: HTTP:80 (301
redirects to HTTPS), HTTPS:443 (`ELBSecurityPolicy-TLS13-1-2-2021-06`,
forwards to the web target group). A Route 53 alias A record at the
zone apex (`infra/dns.tf`) points `mymble.be` itself at the ALB —
previously only the zone and its NS records existed, nothing routed the
bare domain anywhere.

```
$ echo | openssl s_client -connect mymble.be:443 -servername mymble.be
depth=0 CN=mymble.be
verify return:1
Certificate chain: mymble.be -> Amazon RSA 2048 M01 -> Amazon Root CA 1
Verify return code: 0 (ok)

$ curl -sv https://mymble.be/health
< HTTP/1.1 200 OK
{"status":"ok"}
```

Full evidence (openssl chain dump, curl output for both HTTP redirect
and HTTPS response) in `docs/tickets/S7-04-domain-https-retire-mkcert.md`.
DNS delegation itself took roughly 90 minutes to actually activate
after being configured at the registrar (domain was registered fresh
via behostings.com right before this ticket, which appears to have
added its own registry-activation delay beyond ordinary NS
propagation) — resolved, not currently actionable, noted for the
historical record.

**CONFIRMED (2026-08-26):** both live round-trips — password login →
explicit Google account linking from Settings (S6-07's linking-safety
fix), and Enable Banking reconnect — completed successfully by Borys
against `https://mymble.be`. This is what closed the "mkcert stays until
proven working" condition; see the mkcert-retirement section further
down for what was actually deleted.

**DNS delegation:** `mymble.be` was registered externally (behostings.com);
Route 53's nameservers (`ns-1030.awsdns-00.org`, `ns-1821.awsdns-35.co.uk`,
`ns-409.awsdns-51.com`, `ns-935.awsdns-52.net`) were configured at the
registrar and confirmed live (independently checked against three public
resolvers). **Google Cloud Console:** `https://mymble.be/api/auth/google/callback`
was added as an authorized redirect URI on the OAuth client. **Enable
Banking developer portal:** `https://mymble.be/api/auth/enable-banking/callback`
was registered as a redirect URI. All three completed by Borys; both
live round-trips confirmed working (see above).

**Branding survey (KBC Personal Finance Analyzer → Mymble), enumerated
per the ticket's ask, not all fixed:** `frontend/index.html`'s `<title>`,
`frontend/src/pages/LoginPage.tsx`, and `frontend/src/pages/RegisterPage.tsx`
fixed directly (2026-08-26 — the wordmark shown on the two pages the
Finding 1 bug directly touched, closing two real items from this list
rather than leaving them open indefinitely). Verified live in the
deployed bundle after rebuild, not just in source.

**Google's own OAuth consent screen text is NOT fixable from this
codebase at all** — it's a Google Cloud Console setting (the app name
shown during the Google sign-in flow), entirely outside anything the
backend or frontend can control. Flagged for Borys to update directly
in Console; noted here so it isn't mistaken for a code gap.

Still referencing the old name: `frontend/src/App.tsx`,
`frontend/src/components/layout/Sidebar.tsx` (left alone — out of scope
for this fix, which was about the login/register pages specifically),
`ARCHITECTURE.md` (this file's own title/header), `CLAUDE.md`,
`REVIEWER.md`, `TESTER.md`, `docs/multi_user_migration_plan.md`, and
several `docs/tickets/*.md` files (S4-03, S4-09, S4-10, S5-00, S6-00,
S6-01, S7-00). Ticket files are historical record, not live-fixed.
`ARCHITECTURE.md`/`CLAUDE.md`/`REVIEWER.md`/`TESTER.md` are a real,
larger rename worth a deliberate pass, not scattered edits mid-ticket —
flagged for Borys to decide scope/timing.

**Static asset caching (2026-08-26, S7-04):** neither `StaticFiles` nor
`FileResponse` set `Cache-Control` by default — found while
investigating the Finding 1 Google-redirect-uri report (see the ticket
file): without it, a browser's heuristic caching could keep serving a
stale `index.html` (and therefore a stale bundle reference) across a
deploy indefinitely, which is the most likely explanation for what
looked like a live config bug but wasn't one. Fixed: `/assets/*`
(Vite's content-hashed filenames, safe to cache forever) now serves
`Cache-Control: public, max-age=31536000, immutable`; `index.html` and
any other top-level static file serve `Cache-Control: no-cache` (always
revalidate — this is what determines which hashed bundle a visitor
loads next).

**Cost guardrail:** an AWS Budget (`kbc-analyzer-monthly-budget`), COST
type, **$150/month limit** (raised from the initial $50 once the full
target architecture's real projected cost — see S7-01's ticket file
amendment — was priced out and accepted as the real cost of a
deliberately-chosen architecture, not something to redesign around),
notifying `boris.sydorchuk@gmail.com` at 50/80/100% of actual spend
(now $75/$120/$150). Created via the AWS CLI directly (not Terraform) as
the literal first resource in the account, per S7-01's Step 0, then
imported into Terraform state so it's IaC-managed going forward.
**Denominated in USD, verified correct:** AWS Budgets, Cost Explorer, and
the Cost & Usage Report always track and display in USD internally,
regardless of what currency an account is actually invoiced in — this is
a structural property of those AWS services, not a configuration choice,
so no currency mismatch risk exists here even if this account's invoices
are settled in EUR.

**S3 Gateway VPC Endpoint:** not created. The ticket's condition for
adding one ("if the app uses S3 for anything") checked negative — no
`boto3`/S3 references exist anywhere in `kbc_analyzer/` as of S7-01.
Revisit if S3 usage is introduced later.

## URLs & Redirects

| URL | Value | Served by |
|---|---|---|
| Enable Banking redirect URI (local dev) | `EB_REDIRECT_URL`, default `https://localhost:3001/callback` | `kbc_analyzer/enablebanking.py`'s `REDIRECT_URL` — this is a placeholder value only; **nothing automatically completes a redirect to it** since S7-04 retired the local catcher server. Use `POST /api/auth/enable-banking/callback` (manual code paste) to test this flow purely locally. |
| Google OAuth redirect URI (S6-03) | `GOOGLE_REDIRECT_URI`, default `http://localhost:8000/api/auth/google/callback` | `backend` / `routers/user_auth.py`'s `google_callback` — must exactly match a redirect URI registered on the Google Cloud OAuth client, or Google rejects the request outright |
| Frontend origin (CORS) | `FRONTEND_ORIGIN`, default `http://localhost:5173` | `backend/app/main.py`'s `CORSMiddleware` setup, `allow_credentials=True` as of S6-03 (session cookie must reach a cross-origin frontend fetch) |
| Frontend's API base | `VITE_API_URL`, default `http://localhost:8000` | `frontend/src/lib/api.ts`'s `API_URL` constant, injected via compose, no `.env` file on disk |

The redirect URI must be `https://` — Enable Banking's `/auth` endpoint
rejects `http://` live (400). In production this is real HTTPS on
`mymble.be` (see the ACM/HTTPS section); locally, since S7-04 retired
the mkcert-based catcher, `POST /api/auth/enable-banking/callback` (a
manual fallback since S2-02) is how a developer completes this flow
without hitting the real production domain.

Live-verified end-to-end 2026-08-17 (S4-10 step m, with Borys completing
the real KBC login himself — Codee never handles bank credentials):
`SessionBanner.tsx`'s warning threshold was temporarily raised so the
real (not-actually-expiring) session tripped the banner without faking
anything; after a real reconnect, `GET /api/auth/enable-banking/status`
returned a genuinely new ~90-day expiry, auto-caught by the port-3001
callback catcher with zero copy-paste — confirming this flow works
exactly as described above, not just as designed.

## Data Flow

`POST /api/transactions/sync` (`routers/transactions.py`) does almost
nothing synchronously: creates a `job_id`, acquires `sync_lock` (S5-05,
below) for it, seeds Redis with `{"status": "processing", "stage":
"fetching"}`, dispatches `run_sync_job.delay(...)`, returns immediately.
If the lock is already held, no job is created — the endpoint raises
`SyncAlreadyRunningError`, mapped by `main.py`'s
`sync_already_running_handler` to `409 {"message": ..., "job_id":
<in-flight job's id>}`.

Celery task `run_sync_job` (`tasks/analysis.py`, takes `user_id` as of
S6-06 — Celery serializes it as a string, parsed back to `UUID` inside
the task) runs the pipeline, updating the Redis job record as it
progresses: `fetching` → `storing` (`crud.upsert_transactions`, upsert on
`(user_id, external_id)` conflict) → `categorizing` (batch progress
reported via `on_batch_complete`) → `generating_insights` (only on
success does `crud.replace_insights` run — a failed generation leaves
prior insights untouched) → `complete`/`failed`. `sync_lock.release()`
runs in a `finally` block around the whole task (S5-05) — released on
every path that returns or raises inside the task; a worker killed hard
enough to skip even that leaves the lock to its own TTL instead (see
Invariants).

Job state lives only in Redis (`job_store.py`, key `job:{job_id}`, 24h
TTL) — never Postgres. Every `job_store.set_job` call (every stage
transition, every categorization batch) also stamps `heartbeat_at`
(S5-05) and, as of S6-06, `user_id` — `GET /api/jobs/{job_id}` compares
it against the caller and 404s (never `403`) on any mismatch, the same
as a key that never existed or whose 24h TTL expired. While a job is
`processing`, it also checks `heartbeat_at` against a 2-minute staleness
threshold and reports `status: "failed"` (naming the stage) if exceeded
— this is computed at read time, not written back to Redis, and does
not itself release `sync_lock` (see Invariants).

Frontend polling (`frontend/src/hooks/useDashboard.ts`): `useQuery` with
`refetchInterval` of 2s while `status === "processing"`,
`refetchIntervalInBackground: true`, plus an independent `setTimeout`
enforcing a 10-minute cap — now mostly a backstop behind the 2-minute
server-side staleness check above, kept because it also covers a job
whose Redis key vanished outright (React Query's structural sharing means
a dead worker never produces a new `data` reference to key an effect
off, so a plain state-comparison effect can't detect it either). On a
sync request's `409`, the frontend attaches to the in-flight job's
polling instead of showing an error (`useDashboard.ts`'s
`syncMutation.onError`, `SyncConflictError`) — the user asked for a sync,
one is already running, that's not a failure.

`POST /api/chat` (`routers/chat.py`, S4-06) streams a chat reply as
Server-Sent Events. `chat_service.start_chat_stream` (takes `user_id` as
of S6-06, replacing the `CURRENT_USER_ID = None` hardcoding S5-01
flagged) runs everything synchronous first — resolves the configured
provider (`agents/registry.get_provider`) and assembles a fresh, scoped
financial context (last-90-days summary, last 20 transactions, active
budgets, all read straight from Postgres for this user only, never
cached) — so a missing API key is a normal 400 JSON error, not a broken
stream. Only then does
`ChatAgent.stream()` (`agents/chat.py`) start yielding tokens from
`LLMProvider.stream_complete()`, forwarded one SSE frame per chunk
(`{"token": ..., "done": false}`), ending with
`{"token": "", "done": true, "usage": {...}}`. Conversation history is
entirely client-held — the backend is stateless across turns; no
`chat_messages` table exists.

Live-verified 2026-08-16 (Gemini, real 331-row dataset): tokens arrive as
separate incremental frames, not one flush; a 3-turn conversation correctly
built on prior turns; every number the assistant computed from the summary/
category/budget context matched `GET /api/statistics` and `GET /api/budgets`
exactly. That first run surfaced a real gap: the "last 20 transactions"
section is a small slice of a much larger summary window (293 transactions
fell in the 90-day window tested), so a "what was my single biggest
expense" question couldn't be answered from it — the assistant correctly
said so rather than guessing. Review caught that this was a one-line
omission, not a design limitation: `compute_statistics()` already returns
`summary.biggest_expense`, and `_summary_text()`
just wasn't surfacing it. Fixed in-ticket (S4-06 review bounce,
2026-08-17) — `summary_text` now includes a `Biggest expense: ...` line,
re-verified live against the same dataset: exact match on amount,
merchant, and date.

Frontend consumption (`frontend/src/pages/ChatPage.tsx` + `lib/api.ts`'s
`streamChat`, S4-07): plain `fetch` with `response.body.getReader()`, not
`EventSource` — `EventSource` only supports GET, and this endpoint needs a
POST body (message + history). `useChatSession` (a hook, not React Query —
there's nothing here to cache) owns the message list as plain React state;
history is never persisted, matching the backend's statelessness.

`GET /api/insights/compare` (`routers/insights.py`, `comparison_service.py`,
S4-08) computes spending deltas between two arbitrary date ranges.
`total_spent`/`by_category` for both ranges are always computed live from
`transactions` via `statistics.compute_statistics` — never read from a
stored snapshot. `insights` per range are read from the `insights` table
exactly as stored for that exact range (the S4-04 Option B decision) and
never generated on the fly; a range with no matching stored insights just
returns an empty list, labeled `insights_generated_at: null`. Both ranges
are validated (`date_from <= date_to`, ≤365 days) before either is queried,
returning 400 on violation. Frontend:
`components/dashboard/ComparePeriodsSection.tsx`, collapsed on every page
load (plain `useState`, no persistence), a `useMutation`
(`hooks/useCompareInsights.ts`) rather than a cached query — nothing else
in the app reads a comparison result.

## Database Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | Sprint 6 (S6-01) — real accounts | `id` UUID PK; `email` UNIQUE; `password_hash`/`google_id` both nullable, `CHECK (password_hash IS NOT NULL OR google_id IS NOT NULL)` |
| `transactions` | One row per bank transaction | `user_id` UUID FK → `users(id)`, NOT NULL (S6-02); `UNIQUE (user_id, external_id)` — **not** `external_id` alone: Enable Banking's own docs confirm `entry_reference` is not globally unique (S6-02 Step 0, see `docs/multi_user_migration_plan.md`); `manually_edited` boolean, default `false`; `category` FK → `categories(user_id, name)` `ON UPDATE CASCADE ON DELETE SET NULL`, composite since S6-02 |
| `settings` | Per-user key/value store (LLM provider + encrypted API keys) | `(user_id, key)` composite PK (S6-02 — was a flat global store through Sprint 5); `user_id` FK → `users(id)` |
| `categories` | Category → display color, per user | `(user_id, name)` composite PK (S6-02 — a category name is only unique per user); `source` ∈ `seed`\|`ai`\|`user`; `ai_color` holds the last AI color separately so "reset to AI" survives a user override |
| `insights` | Generated AI insight cards per date range | `user_id` UUID FK → `users(id)`, NOT NULL (S6-02); `crud.list_insights`/`replace_insights` both scoped by it (S6-06) — the `(date_from, date_to)` index itself stays unchanged, scoping happens in the query's `WHERE`, not the index shape; **delete-and-replace** per range on every successful sync — no history retained |
| `budgets` | Monthly spending limit per category (S4-05) | `category` FK composite → `categories(user_id, name)` `ON UPDATE CASCADE` (S6-02); `amount` CHECK `> 0`; `user_id` UUID FK → `users(id)`, NOT NULL as of S6-02 (was nullable, always `NULL`, through Sprint 5 — the first table built multi-user-ready); `UNIQUE NULLS NOT DISTINCT (user_id, category, period)` |

`manually_edited`: true once a human has set category/subcategory/
description by hand; the categorization agent excludes these rows even
when `category` is null again (a manual clear is still a decision).
Enforced in `crud.get_uncategorized_transactions` and
`crud.update_transaction_categories`, both filtering
`manually_edited IS FALSE` server-side. Any `PATCH /api/transactions/{id}`
sets it to `true` unconditionally, even for a no-op edit.

**S6-02 (2026-08-20) made every table's `user_id` `NOT NULL`, backfilled to
one real bootstrap user; S6-06 (2026-08-21) is what actually threads a
real `user_id` through every query and write path** (`crud.py`'s
`list_*`/`get_*`/`upsert_*` functions all filter/write by it now — see
the Auth section below for the full endpoint-by-endpoint account).
`docs/multi_user_migration_plan.md` (S5-01, executed by S6-02, scoped by
S6-06) is the complete, code-verified inventory this closed out.

`insights` delete-and-replace is a deliberate decision (S4-04), not an
oversight — see Invariants below.

## Auth

**S6-01 built the session/cookie infrastructure; S6-03 (Google) and S6-04
(email/password) are both live login methods. S6-05 is the first real
protection of application routes (`GET /api/categories`, `GET
/api/budgets`) and the frontend route guard — proof-of-concept for
S6-06's full sweep across every remaining endpoint.**

Sessions are server-side state in Redis, referenced by an opaque cookie
value — not a JWT. The cookie carries no claims of its own; every request
looks the session id up in Redis to resolve the real user, so a session
can be killed server-side (logout) with the client having no way to keep
using a token it still physically holds, unlike a JWT that stays valid
until its own expiry regardless of server-side state.

`users` table (`app/models.py`'s `User`, migration `1f7634448483`):
`id` UUID PK, `email` TEXT unique, `password_hash` TEXT nullable
(NULL = OAuth-only account), `google_id` TEXT unique nullable (NULL =
password-only account), `display_name` TEXT nullable, `created_at`.
`CHECK (password_hash IS NOT NULL OR google_id IS NOT NULL)` — a row with
neither is unrepresentable, enforced at the database level, not just in
application code.

Password hashing: `app/auth/password.py`, passlib's bcrypt scheme (bcrypt
chosen over argon2id — no unusual threat model here, and no extra native
dependency beyond what `passlib[bcrypt]` already pulls in). `bcrypt`
pinned `<4.1` in `requirements.txt` — passlib 1.7.4's bcrypt backend reads
an attribute bcrypt 4.1 removed, otherwise logging a spurious warning on
every hash/verify call.

Session storage: `app/auth/session.py`, Redis key `session:{session_id}`
→ `{"user_id": ..., "created_at": ...}`. `session_id` is
`secrets.token_urlsafe(32)` (256 bits from Python's CSPRNG) — not derived
from anything guessable. TTL 30 days, **sliding**: `get_session()`
re-issues the full 30-day TTL once less than `REFRESH_THRESHOLD_SECONDS`
(5 days) remains, rather than on every request — bounds Redis `EXPIRE`
writes to roughly once per 5 days of continuous use per session instead of
once per API call, while still keeping any actively-used session alive
indefinitely. A fixed (non-sliding) expiry was rejected: it would log out
a daily active user exactly as readily as an abandoned session, when the
thing actually worth expiring is inactivity, not elapsed time.

Cookie (`app/auth/session.py`'s `set_session_cookie`/`clear_session_cookie`,
not called by any route yet): name `session_id`, `httpOnly` (never
readable by client-side JS — closes the main XSS session-theft path),
`SameSite=Lax` (sent on top-level navigation, including the OAuth-callback
redirect, but not cross-site subrequests — CSRF protection sufficient for
a cookie-only session with no state-changing GET routes), `Secure`
controlled by the `COOKIE_SECURE` env var, **default `false`**. Not
hardcoded `true`: local dev's `backend`/`frontend` still run over plain
`http://` (see URLs & Redirects), and a browser refuses to ever send a
`Secure` cookie back to a plain-`http://` origin — `false` stays the
correct local-dev default. Production (`mymble.be`, real HTTPS since
S7-04) sets `COOKIE_SECURE=true` in the ECS task definition.
Chromium-family browsers do special-case
`http://localhost` as a "potentially trustworthy" origin for some
secure-context APIs, but that exemption isn't reliably specified to also
cover the cookie `Secure` attribute across every browser/version — an
explicit env flag (same dev/prod split pattern as `FRONTEND_ORIGIN`) was
chosen over relying on an implicit browser quirk for a security-relevant
attribute. **Sprint 7's real production HTTPS is expected to set
`COOKIE_SECURE=true`.**

`app/auth/dependency.py`'s `get_current_user` (FastAPI dependency): reads
the `session_id` cookie, resolves it via `get_session`, loads the `User`
row, raises `401` if the cookie is missing, the session is expired/
invalid, or the session's `user_id` no longer has a matching row. First
used by S6-04's `POST /api/auth/set-password` (an auth-settings action on
the caller's own account); S6-05 is its first use on an actual feature
route (below).

**Google OAuth sign-in (S6-03).** `app/google_oauth.py` — plain `requests`
calls against Google's documented endpoints (authorize URL, token
exchange, `openidconnect.googleapis.com/v1/userinfo`), not a dedicated
SDK; this app only ever needs those three calls. `routers/user_auth.py`
(`/api/auth` prefix — disjoint sub-paths from `routers/auth.py`'s
`/api/auth/enable-banking/*`, no collision):

- `GET /api/auth/google/login` — generates a random `state`
  (`secrets.token_urlsafe(24)`), stores it in a short-lived (`10 min`)
  `oauth_state` cookie, redirects to Google's consent screen. The state
  round-trip is this flow's CSRF protection: the callback only proceeds if
  the `state` query param Google echoes back matches this cookie.
- `GET /api/auth/google/callback` — rejects on a missing/mismatched
  `state` or a Google-side failure (redirects to `/login?error=
  google_sign_in_failed`, no session created — never a raw 500, including
  when `GOOGLE_CLIENT_ID` itself isn't configured yet). On success:
  resolves the user by `google_id`. If none, and an account with that
  email already exists (no `google_id` linked yet), this is a **conflict**,
  not a silent link (`/login?error=google_email_already_registered`) —
  see the Invariants entry below for why. If no account exists by
  `google_id` or `email` at all, creates a new `google_id`-only row.
  Then `create_session` + `set_session_cookie`, redirect to
  `FRONTEND_ORIGIN`.
- `GET /api/auth/google/link` (S6-07 finding 1) — the *only* route that
  may ever attach a `google_id` to an existing account. Requires
  `get_current_user` (must already be authenticated, via password —
  the one method that doesn't already involve Google) and sets an
  additional `oauth_link_user_id` cookie alongside `oauth_state`, naming
  which account is linking. `google_callback` only takes the linking
  branch when this cookie is present; it rejects (redirects to
  `/settings?error=google_link_failed`, nothing changed) if the Google
  identity already belongs to a different account, or if the linking
  account already has a different `google_id` attached. Frontend trigger:
  `SettingsPage`'s `AccountSection`, a plain `<a>` to this route (real
  navigation through Google's consent screen, same reasoning as
  `LoginPage`'s Google button).
- `POST /api/auth/logout` — destroys the session, clears the cookie. Not
  gated behind `get_current_user` (a no-op on an already-invalid session
  is fine — nothing to protect by requiring one first).

**CORS + credentials.** `main.py`'s `CORSMiddleware` gained
`allow_credentials=True` as of S6-03 — the session cookie only reaches a
cross-origin `fetch` (frontend `:5173` -> backend `:8000` in local dev) if
both the server (`allow_credentials`) and the client
(`lib/api.ts`'s `request()`/`syncTransactions`/`streamChat`, all now pass
`credentials: "include"`) opt in. Safe alongside `allow_origins`'s single
explicit origin (never `"*"`, per CLAUDE.md) — browsers refuse to honor
`allow_credentials` with a wildcard origin anyway.

**Email/password sign-in (S6-04).** Same `routers/user_auth.py` file as
Google's flow:

- `POST /api/auth/register` — `{email, password}`. Rejects an
  already-registered email with a specific `400` (unlike login below —
  register's own existence already implies "an account can be created,"
  so refusing a duplicate here reveals nothing an enumeration attempt
  couldn't already infer). Password validated by
  `app/auth/password.validate_password_strength`: **8–128 characters,
  no complexity rules** — matches NIST 800-63B's modern guidance that
  mandatory uppercase/digit/symbol rules push people toward predictable
  substitutions without meaningfully raising the real search space, and
  closes a gap S6-01 flagged: bcrypt silently truncates at 72 bytes, so
  the 128 ceiling means an implausibly long input is rejected outright
  instead of silently hashed down to its first 72 bytes. Creates the
  user, a session, sets the cookie.
- `POST /api/auth/login` — `{email, password}`. **Always returns the
  identical `401 "Invalid email or password."`** for a wrong password, a
  nonexistent email, and a Google-only account with no password set —
  the response never tells a caller which case they hit (a
  user-enumeration leak otherwise). Also runs a real `bcrypt` verify
  against a fixed dummy hash (generated once at import time, never
  logged) when no matching user exists, rather than short-circuiting —
  otherwise "email doesn't exist" would consistently return faster than
  "email exists, wrong password," which is exactly the timing signal an
  enumeration attempt measures for. Not a complete timing defense (DB
  query time and network jitter still leak some signal) — closes the
  single largest, cheapest-to-exploit gap, not every gap.
- `POST /api/auth/set-password` — `{password}`, requires
  `get_current_user`. The path a Google-only account (including the
  S6-02 bootstrap row, whose `password_hash` is a locked, never-revealed
  placeholder) uses to add password sign-in as a second method, while
  already authenticated via Google — no reset-token flow was built for
  this (S6-01 didn't scope one), so this reuses the session the account
  already has instead.
- Rate limiting (`rate_limit.py`): `LOGIN_RATE_LIMIT`/`REGISTER_RATE_LIMIT`,
  `5/minute` each — deliberately IP-keyed, not user-keyed, unlike the
  future direction planned for chat/sync/analysis: the caller has no
  session at the exact moment they're hitting either endpoint.
- **Out of scope, by design, per DECISIONS ALREADY MADE:** email
  verification and email-based password reset — no transactional email
  infrastructure exists yet. `/login`'s "Forgot password?" is a plain
  inline note ("not available yet — contact support"), not a route to a
  dead end.

`/login` (`frontend/src/pages/LoginPage.tsx`) — a layout route outside
`AppShell` (`App.tsx`), since it's the one route reachable before a
session exists. The Google button is a plain `<a href>` to
`GET /api/auth/google/login`, not a `fetch` — signing in is a real
top-level browser navigation through Google's own consent screen, which a
CORS-bound `fetch` can't follow the way a real navigation does. Also has
an email/password form (S6-04) below a divider. `/register`
(`RegisterPage.tsx`) is the same shape without the Google button.

**Auth middleware rollout — S6-05 partial, S6-06 full sweep.** S6-05
protected `GET /api/categories`/`GET /api/budgets` as a first real test
(proving the login -> protected-route -> logout loop) and shipped
`GET /api/auth/me` + the frontend guard. S6-06 protected and scoped every
remaining endpoint, closing S5-01's IDOR findings for real.

**The full public-route list — everything else requires
`get_current_user` (or, for the three Enable Banking endpoints,
`require_enable_banking_owner`, which itself requires `get_current_user`
first):**

| Route | Why public |
|---|---|
| `GET /health` | Liveness/DB check, used by nothing user-facing |
| `GET /api/auth/google/login` | Starts the sign-in flow — no session to check yet |
| `GET /api/auth/google/callback` | Google redirects here mid sign-in — same reason |
| `POST /api/auth/register` | Creates the session this endpoint's caller doesn't have yet |
| `POST /api/auth/login` | Same reason |
| `POST /api/auth/logout` | A no-op on an already-invalid session is fine — nothing to protect by requiring one first |

Two scoping shapes, per S6-06's own split:

- **List/create endpoints (query filtered by `user_id`):** every
  `crud.py` read/write function now takes `user_id` and filters/writes by
  it — `transactions` (`list_transactions_paginated`, `search_transactions`,
  sync's `upsert_transactions`), `categories` (all four routes, including
  `POST`'s duplicate-name check and `PATCH`/reset, both fixed from the
  `db.get(Category, name)` `InvalidRequestError` S6-02 left tracked —
  composite-key lookup by `(user_id, name)` doubles as the scoping fix),
  `budgets` (`POST`/`PATCH`/`DELETE`, closing S6-02's `CURRENT_USER_ID`
  gap for good), `insights` (list + compare, via `comparison_service`),
  `statistics`, `settings` (`get_all_settings`/`upsert_setting`, composite
  `(user_id, key)`), `chat_service.build_context` (the `CURRENT_USER_ID
  = None` hardcoding S5-01 named explicitly is gone), and
  `analysis_service`'s categorize/insights/color-assignment chain.
  `agents/registry.get_provider`'s `user_id` param is no longer optional
  — every call site now has a real authenticated user.
- **By-ID lookup endpoints (explicit ownership check, 404 not 403 on
  mismatch — never confirm another user's resource exists):**
  `GET /api/jobs/{job_id}` (`job_store`'s status dict now carries
  `"user_id"`, stamped by every `job_store.set_job` call in
  `tasks/analysis.py`; the router compares it against the caller) and
  `PATCH /api/transactions/{id}` (`crud.update_transaction`'s lookup is
  now `WHERE id = ... AND user_id = ...` together, so a transaction
  belonging to someone else reads identically to one that doesn't exist).

**Sync is threaded end to end.** `POST /api/transactions/sync` requires
`require_enable_banking_owner` (below), passes `current_user.id` to
`sync_lock` (already user-aware since S5-05) and to the Celery task
(`run_sync_job.delay(job_id, date_from, date_to, str(user_id))` — Celery
serializes to JSON, so the UUID travels as a string and is parsed back in
`tasks/analysis.py`). Every stage of `_run()` (fetch, store, categorize,
generate insights) now writes/reads with that same `user_id`.

**Enable Banking connection restricted to one account (S6-06).** The
single `eb_session.json` connection is still, physically, one bank
connection — per-user bank session *storage* is Sprint 7's job (needs
the public deployment context to do properly). Until then,
`app/auth/dependency.py`'s `require_enable_banking_owner` (composed on
top of `get_current_user`) gates `POST /api/transactions/sync` and all
three `/api/auth/enable-banking/*` endpoints: only the account named by
the `ENABLE_BANKING_OWNER_EMAIL` env var may use them, `403` for
everyone else. Not a `404`-shaped IDOR check — this is a real, named
permission boundary on a feature every authenticated user can see
exists, not a by-ID lookup hiding whether a resource exists.

`GET /api/auth/me` — the frontend's route guard's one page-independent
way to ask "does a valid session exist," rather than inferring it from
whichever page-specific query happens to fire first. `AppShell`
(`App.tsx`, the layout route wrapping every route except `/login`/
`/register`) calls it once on mount via `useCurrentUser` (`retry: false`;
any error, not just `401`, is treated as "no valid session") and
redirects to `/login` on failure. `Sidebar.tsx`'s user menu (avatar
initial, truncated email, logout button) `logout()`s by clearing the
entire React Query cache (`queryClient.clear()`, not just the
current-user query) before a full-page redirect to `/login`, so no stale
cached data from this session survives into whatever session comes next
in the same browser.

## External Dependencies & Their Guarantees

**Enable Banking** — rely on: `external_id` (`entry_reference`) is stable
across reconnects (unlike `account_id` — see below), and immutable within
one account. Do **not** rely on: `account_id` — it changes on every
reconnect (burned S4-01: keying the old unique constraint on
`(account_id, external_id)` caused 78 duplicate rows on reconnect; fixed
by migration `827da7c749b8`). `account_id` is still stored but is
first-seen-only and never overwritten on conflict. **Also do not rely on**
`external_id` being globally unique — Enable Banking's own FAQ docs
(S6-02 Step 0, validated 2026-08-20): *"the `entry_reference` value is not
globally unique, and the same entry references may occur for transactions
belonging to completely different accounts."* `transactions`' unique
constraint is `(user_id, external_id)`, not `external_id` alone, as of
S6-02 — see Database Tables. The vendor's real scope is per-account, not
per-user; a Sprint 7 watch-item in `docs/multi_user_migration_plan.md`
flags that a user connecting more than one account (multi-bank, Sprint 7)
could still collide under this constraint alone.

**AI providers** — resolved via `agents/registry.py`, switching in
Settings changes behavior everywhere at once. `get_provider()` caches one
instance per provider name at module level (S4-09 Item 3) instead of
re-authenticating an SDK client on every call; `routers/settings.py`
drops the whole cache after any successful `PATCH /api/settings` (not
just an `llm_provider` switch — editing a key under the same provider
name must also force a fresh instance). Gemini alias:
`gemini-flash-latest` (`gemini-2.0-flash` was live-confirmed deprecated,
404). Claude alias: `claude-haiku-4-5-20251001`. Provider API keys are
**not** read from `.env` by the running app — only
`scripts/smoke_test_providers.py` does that. The app reads them from the
`settings` table, Fernet-encrypted at rest, masked on every read except
the one internal decrypt used by the provider registry.
`settings_service.get_decrypted_api_key` maps provider name to settings
field explicitly (`API_KEY_FIELD_BY_PROVIDER`) rather than assuming
`f"{provider}_api_key"` — that assumption silently broke Claude specifically
(the field is `anthropic_api_key`, named after the vendor, not
`claude_api_key`) from S2-04 until a real key finally existed to expose it
at S5-06. Both providers also implement `stream_complete()` (S4-06, chat) —
both are now live-verified (Gemini 2026-08-16, Claude 2026-08-18, see
docs/verification_debt.md's CLOSED section for both).

**mkcert certificate**: RETIRED (S7-04). `backend/certs/localhost.pem`/
`localhost-key.pem` are deleted along with the local catcher server that
used them — real production HTTPS on `mymble.be`, proven working via a
live Enable Banking reconnect, closed the condition this item used to
be waiting on.

## Invariants

- **A Google sign-in must never implicitly attach to an existing
  account just because the emails match (S6-07 finding 1, real
  account-takeover path, closed 2026-08-21).** Before this fix,
  `google_callback` treated "an account with this email exists, no
  `google_id` linked yet" as an unconditional linking case. Since this
  app has no email verification (a standing, deliberate Sprint 6 gap —
  see DECISIONS ALREADY MADE), an attacker could register a password
  account under a victim's real email first; the victim's own,
  legitimate Google sign-in would then silently attach to the
  attacker-controlled row, leaving the attacker with standing password
  access to whatever the victim did under that account afterward. Fixed:
  that case is now a conflict (`google_email_already_registered`), never
  a link. **The only route allowed to attach a `google_id` to an
  existing account is `GET /api/auth/google/link`, and only while the
  caller is already authenticated as that account** (see Auth section
  above) — never as a side effect of any sign-in attempt, regardless of
  email match. `tests/test_google_oauth.py`'s
  `test_google_sign_in_on_an_email_with_an_existing_password_account_is_a_conflict_not_a_silent_link`
  is the regression test for the actual adversarial case (attacker
  registers first); do not weaken or remove the email-conflict check in
  `google_callback` to "fix" a UX complaint without re-reading this
  entry first.
- **Manual edits outrank AI categorization.** Enforced server-side (see
  Database Tables above) — not just a frontend convention.
- **Colors come only from the `categories` table.** No component stores
  or hardcodes a per-transaction color; the donut chart and category
  pills read the same source, and validation is centralized in `colors.py`.
- **`transactions.category` must exist in `categories.name` (S5-02, enforced by FK).**
  A category can no longer be renamed by updating `categories.name` in place
  without every referencing transaction following automatically — the FK's
  `ON UPDATE CASCADE` makes that happen at the database level, not by
  convention. The categorization agent's write path
  (`analysis_service.categorize_transactions`) filters LLM output against
  known category names before writing, so an unknown/hallucinated category
  name is skipped and logged (counted in that sync's `failed`), not a hard
  failure of the whole batch. `PATCH /api/transactions/{id}` already
  validated its `category` field against known categories before this FK
  existed (S3-05) — the FK is a second, database-level guarantee, not a
  replacement for that check.
- **Insight history is not retained (S4-04, decided).** `insights` is
  delete-and-replace per date range on every successful sync
  (`crud.replace_insights`) — "history" means whatever the latest sync
  generated, nothing more. This is safe because no feature depends on it
  for correctness: the period-comparison feature (S4-08) computes its
  numbers live from `transactions`, and only shows stored insights as
  supplementary context labeled `generated_at`. If a future sprint needs
  true insight history, that's a new `generation_number` column and a
  "latest per range" query — a clean addition, not a fix to a bug.
- **Job state is Redis-only.** No `jobs` table exists in any migration;
  sync progress never touches Postgres.
- **One sync job at a time per user, enforced server-side (S5-05, real as
  of S6-06).** `sync_lock.py`, Redis key `sync_lock:{user_id}` —
  `routers/transactions.py`'s `sync_transactions` now passes
  `current_user.id` (the key derivation was already written to take one
  at S5-05; this is the one-line change that was waiting on real auth).
  `SET NX EX` on
  acquire (atomic — no check-then-set race between two concurrent
  requests); release is an atomic Lua compare-and-delete (`sync_lock.py`'s
  `_RELEASE_SCRIPT`) so a job never deletes a *different* job's lock. TTL
  11 minutes — deliberately longer than the frontend's 10-minute give-up
  timeout, so a crashed worker's lock cannot deadlock sync permanently;
  it expires on its own even though nothing ever calls `release()` for a
  hard-killed worker. This is a separate mechanism from the 2-minute
  heartbeat-staleness check above — a worker crash is typically reported
  to the user (via a "failed" job status) well before the lock itself
  expires, meaning a fast retry can still 409 for up to the remainder of
  that 11 minutes. The OAuth callback port (3001) lock is unrelated — it
  guards a second concurrent *reconnect*, a different flow.
- **CLAUDE.md's date-range validation (`date_from <= date_to`, ≤365 days)
  is enforced on all five date-range endpoints (S5-07).** `date_range.py`
  is the one source of truth (`validate_date_range` /
  `require_valid_date_range` for query-param endpoints /
  `validate_date_range_body` for `POST /api/transactions/sync`'s body) —
  extracted from `GET /api/insights/compare`'s original S4-08
  implementation, which was the only endpoint that had this until now.
  `GET /api/statistics`, `GET /api/transactions`, `GET /api/insights`, and
  `POST /api/transactions/sync` all now 400 with the same message shape
  (`"date_from/date_to: ..."`) on a backwards or >365-day range. Found
  missing by the S4-10 sprint-close audit; closed by S5-07. `POST
  /api/analysis/categorize` (optional dates) and `POST
  /api/analysis/insights` (required dates) were **not** included — outside
  this ticket's named scope, flagged as a related gap for a PM decision,
  not fixed unprompted.
- **Rate limiting on cost/third-party-hitting endpoints (S5-07).**
  `rate_limit.py`, `slowapi`, still keyed on remote address even after
  S6-06 — flagged, not fixed: every cost-incurring route (`chat`, `sync`,
  `analysis`) now genuinely resolves a real `current_user`, so switching
  to `user_id`-keyed is no longer blocked on auth existing, only on the
  `slowapi` integration work itself (`key_func` only receives the raw
  `Request`; deriving `user_id` there means either duplicating
  `get_current_user`'s session lookup outside it, or a custom
  `key_func` that reads the same cookie). Out of S6-06's named scope
  (full query scoping and ownership checks, not rate-limit keying) —
  worth a small follow-up ticket. `/login`/`/register` (S6-04) should
  very likely stay IP-keyed regardless — user identity is exactly what
  those endpoints don't have yet when a brute-force attempt hits them.
  In-memory storage — fine
  while `backend` is one uvicorn process; move to Redis (already in this
  stack) if it ever runs with more than one worker. `POST /api/chat`: 20
  requests/minute. `POST /api/transactions/sync`, `POST
  /api/analysis/categorize`, `POST /api/analysis/insights`: 10/minute
  each. Generous for real single-user use — the point is a ceiling before
  Sprint 6 exposes this publicly, not throttling normal use. A 429 uses
  the same `{"message": ...}` error shape as every other handled
  exception in `main.py`.
- **CORS never accepts a wildcard origin.** `main.py`'s `CORSMiddleware`
  has exactly one configuration path — `allow_origins=[frontend_origin]`,
  always a single explicit origin read from `FRONTEND_ORIGIN`, never `"*"`
  and never a hardcoded list (verified: no other CORS configuration exists
  anywhere in the codebase). `docker-compose.yml` currently hardcodes
  `FRONTEND_ORIGIN: http://localhost:${FRONTEND_PORT:-5173}` for the
  `backend` service — a dev-only value. **Sprint 6 must set
  `FRONTEND_ORIGIN` to the real production frontend URL** (e.g.
  `https://app.example.com`), not derived from `FRONTEND_PORT` at all;
  there is no production compose file or override yet, so this is a real
  gap to close before any public deployment, not just a value to swap.
- **`settings_service.VALID_PROVIDERS` is derived from
  `API_KEY_FIELD_BY_PROVIDER` (S5-07), not a second hand-kept set.** The
  two used to be independent literals — S5-06 found this let
  `patch_setting()` accept an `llm_provider` value that
  `get_decrypted_api_key()` then `KeyError`'d on, an unhandled 500. Adding
  a provider now only ever means editing `API_KEY_FIELD_BY_PROVIDER`.
- **Chat and category-name inputs are length-capped (S5-07).**
  `ChatRequest.message`/`ChatMessage.content` (4000 chars),
  `ChatRequest.history` (50 turns), `CreateCategoryRequest.name` (100
  chars — `categories.name` is an unbounded `Text` primary key with no
  DB-level bound), `GET /api/transactions/search`'s `q` (200 chars). Chat
  message emptiness is checked in the router (a clear 400), not via a
  Pydantic `min_length`, so that common case doesn't turn into a generic
  422 the way the length caps above deliberately do — hitting a cap is
  meant to be rare. `PatchTransactionRequest.description`/`subcategory`
  remain unconstrained — flagged, not fixed (what's a reasonable
  transaction-description length is a product call, not an obvious one).
- **No transaction amounts/descriptions reach `backend`/`celery_worker`
  logs at any level (S5-07 audit, every `logger.*` call site checked).**
  Confirmed safe: all `logger.info`/`.warning`/`.exception` calls in
  `app/` log only ids, counts, provider/category names, or exception
  messages — none embed a real amount or description. One pre-existing,
  unrelated finding, now resolved: `kbc_analyzer/backend/kbc_analyzer/
  analysis.py` (the legacy CLI/Telegram-bot module, untouched by the web
  app) hardcoded real IBANs and the account holder's real name directly
  in its Gemini system prompt — not a logging issue, a real
  PII/financial-identifier exposure in committed source. Moved to
  environment variables and a precautionary full git history rewrite was
  performed and verified. See `docs/security_excursion_2026-08.md` for
  the full record.
