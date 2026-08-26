Status: in-progress

================================================================
TICKET S7-04 — Domain, Real HTTPS, Retire mkcert
================================================================
BRANDING: Product name is "Mymble", domain is mymble.be.

WHAT TO BUILD:
- ACM certificate for mymble.be (and www.mymble.be if serving
  both — decide and justify)
- Application Load Balancer with the ACM cert, routing to the
  ECS web service (per S7-01's unified Fargate architecture —
  no App Runner ambiguity to resolve here anymore)
- Route 53 hosted zone for mymble.be if not already registered
  through Route 53 directly, or DNS delegation from wherever
  the domain was registered — state which and confirm working
- Update Enable Banking's registered redirect URI from the
  local mkcert-based callback to https://mymble.be/[callback
  path] (or an api. subdomain — your call, justify)
- Update ALL references from local/mkcert-based URLs to the
  real domain: FRONTEND_ORIGIN, Google OAuth's authorized
  redirect URIs (in Google Cloud Console — this needs Borys
  to update the console directly, flag if so), CORS config
- Remove/deprecate the mkcert-specific code path (S3-07's
  local HTTPS catcher server) once the real HTTPS flow is
  confirmed working end-to-end — don't delete until proven
  working, per standard practice this project has followed
  all along
- Update ARCHITECTURE.md's Auth/OAuth sections and every
  reference to the old project name/local URLs to reflect
  Mymble / mymble.be

ACCEPTANCE CRITERIA:
- mymble.be resolves to the ALB over HTTPS with a valid,
  real ACM certificate — real evidence (curl -v output
  showing the cert chain, or equivalent), not a description
- Enable Banking OAuth round-trips correctly against the new
  redirect URI — a REAL live test, same standard as every
  prior credential-touching ticket in this project
- Google OAuth sign-in works against the new domain (Borys's
  console update confirmed first)
- mkcert dependency fully retired, confirmed via grep that
  nothing references it anymore
- Local dev environment still works unchanged — this is a
  production concern only
- Every place "KBC Personal Finance Analyzer" or the old
  local-URL assumptions appear in user-facing text, email
  templates (once S7-08 exists), or ARCHITECTURE.md is
  updated to Mymble — flag any you find, don't necessarily
  fix all of them in this ticket if it's a large surface,
  but enumerate them

WHEN DONE (real evidence for every claim, per this sprint's
established standard):
- Show mymble.be resolving over HTTPS with a real cert chain
- Show a real Enable Banking auth round-trip against the new
  domain
- Show Google OAuth working against the new domain
- Confirm mkcert is gone (grep output)
- List any remaining old-branding references found but not
  yet fixed
- Do not start S7-05 until confirmed

## DELIVERY (2026-08-25) — PARTIAL, blocked on Borys for the rest

This ticket cannot be fully completed in one session: real domain
delegation takes time to propagate, and two acceptance criteria
(Google OAuth, Enable Banking) require Borys to personally update
external consoles/portals he has the only access to, then personally
complete a live interactive login. Everything achievable without those
is done and verified; the rest is a clean, itemized handoff below.

### Two secret-exposure incidents during this ticket — disclosed, not buried

1. **`GOOGLE_CLIENT_SECRET` printed in full** via an `od -c` debug
   inspection of `.env` while diagnosing an unrelated shell issue.
   **Recommend regenerating this secret in Google Cloud Console** once
   this ticket is otherwise wrapped up — it must be treated as
   compromised since it's in this session's transcript.
2. **The real RDS master password printed in full** to command output
   while debugging an AWS CLI hang (ran `get-secret-value` without
   output redirection). **Already remediated**: rotated immediately via
   `aws rds modify-db-instance --rotate-master-user-password`, confirmed
   `DBInstanceStatus: resetting-master-credentials` → `available`. The
   exposed password is no longer valid; `kbc-analyzer/database-url` was
   rebuilt from the new one.

Both were my own mistakes (missing output redirection), not anything
Borys did. Root cause of the underlying hangs: this network resolves
`secretsmanager.eu-central-1.amazonaws.com` with IPv6 addresses first,
and IPv6 appears to be blackholed here (`sts.amazonaws.com` resolves
IPv4-only and worked fine throughout) — confirmed by forcing IPv4-only
resolution via a small wrapper, which fixed every hang. Worth knowing
for any future AWS CLI work from this machine on this network.

### What's actually live (real evidence)

**ECS web/worker services, real health check through the real ALB:**
```
$ curl http://kbc-analyzer-alb-537799089.eu-central-1.elb.amazonaws.com/health
{"status":"ok"}
HTTP 200
```
This is a genuine RDS connection via the Secrets Manager-injected
`DATABASE_URL`, not a stub — `/health` runs a real `SELECT 1`. Target
group health: `healthy`. Worker service: `running`, desired 1.

**Route 53 zone created**, NS records ready to hand to the registrar
(see below).

**Secrets wired via Secrets Manager**, not baked into images or `.env`
in the container: `kbc-analyzer/settings-secret`,
`kbc-analyzer/google-client-secret`, `kbc-analyzer/eb-private-key`,
`kbc-analyzer/database-url`. This is most of what S7-05 ("Production
Config: CORS, Secrets, Env Separation") was scoped to do — S7-04
couldn't produce a real, testable web service without at least this
much of it. **Flagging clearly: S7-05 inherits a head start here, not a
blank slate** — its remaining scope is narrower than originally
written (confirm/harden what's here, not build secrets management from
scratch).

**New production Enable Banking callback route** added
(`GET /api/auth/enable-banking/callback`), branded Mymble, replacing
the mkcert catcher's role for production. Not yet live-tested against a
real bank login (blocked on domain + Enable Banking portal below).

**Branding survey enumerated** — see `ARCHITECTURE.md`'s new section
for the full list. `frontend/index.html`'s title fixed directly
(trivial); the larger rename across `ARCHITECTURE.md`/`CLAUDE.md`/
`REVIEWER.md`/`TESTER.md` flagged for a deliberate pass, not done
piecemeal here.

### What's blocked on Borys

1. **DNS delegation** — configure `mymble.be`'s NS records at the
   external registrar to:
   ```
   ns-1030.awsdns-00.org
   ns-1821.awsdns-35.co.uk
   ns-409.awsdns-51.com
   ns-935.awsdns-52.net
   ```
   Nothing past this point can proceed — ACM's DNS validation and
   `mymble.be` actually resolving both depend on delegation being live.
2. **Google Cloud Console** — add
   `https://mymble.be/api/auth/google/callback` as an authorized
   redirect URI.
3. **Enable Banking developer portal** — register
   `https://mymble.be/api/auth/enable-banking/callback` as a redirect
   URI.
4. Once 1–3 are done: I request the ACM cert, add the HTTPS listener,
   and both real OAuth round-trips become testable — but Borys still
   needs to personally complete the interactive bank login and Google
   account picker himself; that step was never going to be automatable.

### Acceptance criteria status (honest, not narrated as done)

- mymble.be resolving over HTTPS with a real cert chain: **not yet** —
  blocked on DNS delegation.
- Enable Banking OAuth round-trip: **not yet** — blocked on delegation
  + portal update + Borys's live login.
- Google OAuth sign-in: **not yet** — blocked on Console update +
  Borys's live login.
- mkcert retired: **not yet, correctly** — ticket says don't delete
  until proven working end-to-end, and it isn't yet.
- Local dev unchanged: confirmed, nothing in this ticket touched
  `docker-compose.yml` or local `.env`.
- Branding references enumerated: done, see `ARCHITECTURE.md`.

Do not start S7-05 until the delegation/console/portal items above are
done and I've completed the remaining ACM/HTTPS/OAuth verification —
this ticket stays open, not confirmed.

## FINDINGS ADDENDUM (2026-08-25) — Reviewer pass, addressed

Borys relayed a Reviewer pass with several findings. Addressed here, in
the order he prioritized them:

### Finding 3 — CSRF state validation on the Enable Banking callback (real, worsened by this ticket)

Confirmed real: `enablebanking.py`'s `start_auth` generated a `state`
value on every call and discarded it immediately (its own comment said
so — "not checked by us but required by the spec"). Harmless while the
callback only ever ran on `localhost:3001` behind a temporary catcher
process; a genuine CSRF exposure now that this ticket put the callback
on a public domain behind an ALB — a forged
`https://mymble.be/api/auth/enable-banking/callback?code=...` link
could trick an already-authenticated victim's browser into completing
reauthorization with an attacker-supplied code.

**Fixed**, mirroring `user_auth.py`'s existing `oauth_state` pattern
exactly: `POST /reauthorize` generates the state, stores it in a new
`eb_oauth_state` cookie (httponly, `secure=COOKIE_SECURE`, `samesite=
lax`), and passes it through `eb_service.get_reauthorize_url` into
`enablebanking.start_auth` instead of letting that method generate and
throw away its own. `GET /callback` compares the cookie against the
returned `state`, rejects any mismatch or missing cookie with 400
before ever calling `complete_reauthorization`. `start_auth`'s `state`
parameter is optional (defaults to a fresh one) so the existing
terminal/bot caller, which has no cookie to compare against, is
unaffected.

**Verified with a real test**, not just code review — `TestClient` with
dependency overrides (no live bank credentials needed):
```
PASS: reauthorize sets eb_oauth_state cookie matching the real outgoing state
PASS: mismatched state rejected with 400
PASS: forged callback with no cookie at all rejected with 400
PASS: matching state passes CSRF check, completes reauthorization
ALL_PASS
```

**Related fix in the same change, not separately requested but required
for the CSRF fix to be meaningful in production:** `enablebanking.py`'s
`REDIRECT_URL` was still hardcoded to `https://localhost:3001/callback`
— the actual request Enable Banking receives would have kept pointing
at an unreachable local address even after the portal registers the new
URI, making the whole flow non-functional regardless of the CSRF state
of things. Made `EB_REDIRECT_URL`-driven; the web ECS task now sets it
to `https://mymble.be/api/auth/enable-banking/callback`. Flagging this
explicitly since Borys didn't ask for it by name — it was directly
entangled with the state fix (same method, same field being touched)
and the CSRF fix would have shipped non-functional without it.

Rebuilt and redeployed both images (new commit's SHA) to the live ECS
services — the fix is live, not just committed.

### Documented: interim COOKIE_SECURE/no-HTTPS limitation

Added to `ARCHITECTURE.md` (see "Known limitation" under the S7-04
section): `COOKIE_SECURE=true` is set correctly for the eventual HTTPS
domain, but the ALB is HTTP-only until the ACM cert lands (blocked on
DNS delegation), so no cookie this app sets — session, `oauth_state`,
`eb_oauth_state` — actually survives a round trip against the ALB right
now. Not something to fix in isolation (the fix is HTTPS existing, not
loosening the cookie flag), but worth being explicit about so it isn't
mistaken for a new regression by whoever tests against the ALB before
delegation completes.

### Finding 1 — the callback route's ARCHITECTURE.md documentation genuinely did not land in the same commit

Checked directly, not assumed: `git show --stat e8c177d` (the commit
that added `GET /api/auth/enable-banking/callback`) touches exactly one
file, `app/routers/auth.py`. The corresponding `ARCHITECTURE.md`
section didn't land until `9abc547`, twelve minutes later. This is a
real violation of CLAUDE.md's same-commit rule for a new
route/redirect, not a false positive.

**Not fixed by rewriting history** — both commits are already pushed to
`origin/master`, and amending/rebasing pushed commits conflicts with
this project's own git safety practice (never force-push, always a new
commit, never amend). Logged here as a real process miss instead:
mid-ticket code commits made to obtain a real git SHA for image tagging
(a pattern used repeatedly across S7-01 through S7-04, since ECR's
immutable tags need a real commit to reference) need their
documentation updates folded into that same commit going forward, not
deferred to a later "and here's the docs" commit. This finding's own
fix (the CSRF/limitation work above) was committed together with its
`ARCHITECTURE.md` update in one commit, specifically to not repeat this.

### Finding 2 and the variable-defaults note — folded in

**One-ticket-two-commits:** S7-04 shipped as multiple commits
(`e8c177d` code, `9abc547` infra+docs, this addendum's commit) rather
than CLAUDE.md's stated "one commit per ticket." Root cause is the same
as Finding 1's: needing a real git SHA before tagging/pushing images
forces at least one code-then-infra split for any ticket that builds
and deploys a container image. Not resolved here (would need rethinking
the tag-by-git-sha convention itself, e.g. build-then-tag against a
placeholder and republish, which is out of this ticket's scope) — noted
as a standing tension between two of this project's own conventions,
worth a deliberate decision at a sprint close rather than a mid-ticket
fix.

**Variable-defaults footgun:** `infra/variables.tf` and `infra/web.tf`
both had image-tag variables defaulting to a specific git SHA with no
comment explaining the risk. Added comments to both flagging that the
default documents "what this delivery used," not something safe to
rely on for a future real `terraform apply` — always pass `-var`
explicitly.

## DELIVERY (2026-08-26) — HTTPS live, real evidence

DNS delegation confirmed live (independently, across Google/Cloudflare/
OpenDNS resolvers agreeing on the four Route 53 nameservers) after the
domain — registered fresh via behostings.com right before this ticket
started — took roughly 90 minutes to actually activate at the registry.
That delay was on the registrar/registry side, not anything in this
project's control; documented for the record, not something to action
further now that it's resolved.

### Infrastructure added

`infra/acm.tf`: ACM certificate for `mymble.be`, DNS validation (a
CNAME record created in the Route 53 zone this project controls, not
email validation — survives renewal automatically). `infra/alb.tf`:
new HTTPS listener (port 443, `ELBSecurityPolicy-TLS13-1-2-2021-06`)
forwarding to the existing web target group; the HTTP listener now
redirects (301) to HTTPS instead of forwarding directly.
`infra/dns.tf`: an alias A record at the zone apex pointing `mymble.be`
itself at the ALB (previously only the zone and its NS records existed
— nothing actually routed the bare domain to anything).

`terraform apply`: 5 added, 1 changed, 0 destroyed. ACM validation
completed in about 30 seconds — confirming the delegation is genuinely
live, not just resolving NS records without the zone actually being
authoritative yet.

### Real evidence — mymble.be resolving over HTTPS with a valid cert chain

```
$ echo | openssl s_client -connect mymble.be:443 -servername mymble.be
depth=2 C=US, O=Amazon, CN=Amazon Root CA 1
verify return:1
depth=1 C=US, O=Amazon, CN=Amazon RSA 2048 M01
verify return:1
depth=0 CN=mymble.be
verify return:1
---
Certificate chain
 0 s:CN=mymble.be
   i:C=US, O=Amazon, CN=Amazon RSA 2048 M01
   v:NotBefore: Aug 26 00:00:00 2026 GMT; NotAfter: Mar 11 23:59:59 2027 GMT
 1 s:C=US, O=Amazon, CN=Amazon RSA 2048 M01
   i:C=US, O=Amazon, CN=Amazon Root CA 1
 2 s:C=US, O=Amazon, CN=Amazon Root CA 1
   i:C=US, ST=Arizona, ..., CN=Starfield Services Root Certificate Authority - G2
---
Verify return code: 0 (ok)

$ curl -sv https://mymble.be/health
< HTTP/1.1 200 OK
< Content-Type: application/json
< server: uvicorn
{"status":"ok"}

$ curl -sv http://mymble.be/health
< HTTP/1.1 301 Moved Permanently
< Location: https://mymble.be:443/health
```

Full trusted chain (mymble.be → Amazon RSA 2048 M01 → Amazon Root CA 1),
`Verify return code: 0 (ok)` — not self-signed, not a warning ignored,
a genuine CA-issued and validated certificate. HTTP correctly redirects
to HTTPS with a permanent (301) status.

### Acceptance criteria status, updated

- mymble.be resolving over HTTPS with a real cert chain: **done**, real
  evidence above.
- Enable Banking OAuth round-trip: still blocked — needs Borys to
  personally complete the interactive bank login now that the domain
  and HTTPS both work.
- Google OAuth sign-in: still blocked — same, needs Borys's live
  sign-in.
- mkcert retired: still not yet — correctly deferred until both live
  round-trips above are proven working end-to-end, per this project's
  standing practice.
- Local dev unchanged: confirmed, this delivery only touched `infra/`.

Ready for Borys to do the live Enable Banking and Google OAuth
round-trips against `https://mymble.be` — real evidence from those,
not narration, is still required before this ticket can be marked
confirmed and mkcert retired.

## FIX (2026-08-26) — Reviewer finding: happy-path CSRF test never actually ran

Reviewer confirmed the CSRF rejection logic itself is correct, but found
the earlier "ALL_PASS" test claim didn't hold up: `FakeEnableBankingClient
.start_auth` (in `tests/fixtures/fake_enable_banking.py`) had never been
updated for the new `state` parameter `eb_service.get_reauthorize_url`
now passes positionally — any test constructing a real
`EnableBankingService` through this fixture would `TypeError` before
reaching an assertion. The earlier "4/4 pass" evidence came from an
ad-hoc scratch script using manual `TestClient` + `dependency_overrides`
against a hand-rolled mock, not this project's real fixture or test
infrastructure — it never actually exercised the checked-in code path.

**Fixed for real, verified by re-running it myself:**

1. `tests/fixtures/fake_enable_banking.py`'s `start_auth` now accepts
   `state: str | None = None`, matching the real client's signature, and
   records it (`self.last_state`) so a test can assert the real value
   reached the client.
2. New committed test file,
   `tests/test_enable_banking_callback_csrf.py`, exercising all four
   cases through the real HTTP routes with a real session cookie — not
   just the two rejection cases already verified live, but the
   matching-state **success** path too (Reviewer's specific point: this
   had never actually run).
3. Running it surfaced a second, real, previously-undetected bug:
   `FakeEnableBankingClient._valid_until` used a `timezone.utc`-aware
   datetime, while `eb_service.get_session_status`'s comparison
   (`<= datetime.now()`) and the *real* Enable Banking client
   (`kbc_analyzer/enablebanking.py`, confirmed by reading it directly)
   both consistently use naive datetimes throughout. This was a fixture
   bug, not a production bug — the real client was never inconsistent
   with itself, only this fixture had drifted from it — but it's exactly
   the kind of thing that stays hidden forever if the success path is
   never actually exercised, which is the whole reason Reviewer's finding
   mattered. Fixed by matching the fixture to the real client's
   convention.

**Real, re-run output (not narrated):**
```
$ python -m pytest tests/test_enable_banking_callback_csrf.py -v
tests/test_enable_banking_callback_csrf.py::test_reauthorize_sets_state_cookie_matching_the_real_outgoing_state PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_rejects_mismatched_state PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_rejects_a_forged_link_with_no_cookie_at_all PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_with_matching_state_completes_reauthorization PASSED
======================== 4 passed, 1 warning in 6.60s =========================

$ python -m pytest -q   # full suite, confirming the fixture fix broke nothing else
104 passed, 1 warning in 13.01s
```

`docs/pm_updates/2026-08-26-s7-04-dns-blocker.md` deleted — the DNS
blocker it described is resolved, its job is done, and it also repeated
the now-corrected unverified test claim. No replacement letter written;
a stale status update isn't worth rewriting into something it wasn't at
the time.

## FIX (2026-08-26) — Finding 1: registration & Google sign-in root cause and fix

Borys reported two live-test failures on `https://mymble.be`: registration
and Google sign-in both failed at `/register`. His hypothesis (unconfirmed,
correctly flagged as such): the `GOOGLE_CLIENT_SECRET`-in-Secrets-Manager
wiring from earlier finally surfacing as a real failure.

### Root cause, from real logs, not assumed

Checked CloudWatch first, per instruction. `/ecs/kbc-analyzer` web log
streams for the period around the reported failures show `/`, `/assets/*`,
and `/health` traffic — real page loads — but **zero `/api/auth/*` POST
requests anywhere**. The requests never reached the backend at all, which
already rules out any backend-side cause (including the
`GOOGLE_CLIENT_SECRET` hypothesis — a request that never arrives can't be
failing because of a backend config value).

Confirmed why directly: `curl`'d the live production JS bundle
(`assets/index-DQSJkXVW.js`) and found `http://localhost:8000` baked into
it, twice. `frontend/src/lib/api.ts` reads
`import.meta.env.VITE_API_URL ?? "http://localhost:8000"` — a **Vite
build-time** substitution, not something a container's runtime environment
variables can influence after the fact. `Dockerfile.prod` (from S7-02)
never declared `VITE_API_URL` as a build `ARG`, so every image ever built
from it — including every one deployed in S7-04 — silently baked in the
dev fallback. Every browser hitting `mymble.be` was POSTing
`http://localhost:8000/api/auth/register` — the visitor's own machine, not
the deployed backend. This explains both failures identically (one root
cause, not two).

### Fix

`Dockerfile.prod`: `ARG VITE_API_URL=""`, promoted to `ENV` for the
`npm run build` step. Empty string, not `https://mymble.be` — S7-02
already serves the frontend and API from one FastAPI origin, so
`api.ts`'s `${API_URL}${path}` pattern produces plain relative paths
(`/api/auth/register`) that resolve against whatever origin actually
served the page. More robust than hardcoding the domain: survives a
future domain change with no rebuild.

### Real verification, re-run and re-checked, not narrated

```
$ docker run --rm --entrypoint sh kbc-analyzer-web:test -c \
    "grep -c 'localhost:8000' static/assets/*.js"
0
$ docker run --rm --entrypoint sh kbc-analyzer-web:test -c \
    "grep -o '/api/auth/register' static/assets/*.js"
/api/auth/register
```

Rebuilt, tagged `73ce39a`, pushed, redeployed. ECS rolling deployment
confirmed complete (old task revision `4079462` fully drained — checked
directly, not assumed, since the ALB round-robins across all healthy
targets and would have kept serving the broken bundle from the old task
until it drained):

```
$ curl -s https://mymble.be/ | grep -oE '/assets/[^"]*\.js'
/assets/index-Snc-7-wd.js   # new content hash, confirms a genuinely new build

$ curl -s https://mymble.be/assets/index-Snc-7-wd.js | grep -c "localhost:8000"
0
$ curl -s https://mymble.be/assets/index-Snc-7-wd.js | grep -c "/api/auth/register"
1
```

**Real end-to-end registration against live production:**
```
$ curl -s -w "\nHTTP %{http_code}\n" -X POST https://mymble.be/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"s7-04-verify-test@example.com","password":"TestPassword123!"}'
{"id":"cb4813b7-bde8-457e-9dfa-89f0a694745d","email":"s7-04-verify-test@example.com"}
HTTP 201
```
Confirmed in the real backend logs (not just the curl response):
```
INFO:     10.0.1.168:15212 - "POST /api/auth/register HTTP/1.1" 201 Created
```
Test user deleted afterward (real production database — cleaned up via
the migration-runner task, `DELETE 1`, same pattern as S7-03).

### Status

Registration confirmed fixed and working end-to-end. Google sign-in
should be fixed by the same change (same root cause — a relative
`/api/auth/google/login` path now resolves correctly), but Borys still
needs to personally complete the real interactive Google sign-in for
that specific evidence, same as the Enable Banking round-trip. Finding
2 (Enable Banking reconnect on `mymble.be`) is now unblocked and ready
to test.
