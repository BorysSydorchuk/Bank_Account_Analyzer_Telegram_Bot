Status: confirmed
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
TICKET S4-09 — Infrastructure & Light Items Bundle
================================================================

Work through in order. Items 1–5 are the original bundle;
6–7 accumulated during the sprint.

ITEM 1 — Non-root user in Dockerfile:
  RUN addgroup --system appgroup && \
      adduser --system --ingroup appgroup appuser
  USER appuser
  Verify: no SecurityWarning in celery_worker logs.
  Watch for: file permissions on eb_session.json, the
  mkcert certs, and any volume-mounted paths the worker
  writes — root-owned files from previous runs are the
  classic failure here.

ITEM 2 — Vite/Docker stale-reload fix:
  vite.config.ts → server.watch = { usePolling: true,
  interval: 1000 }
  Verify: a visible frontend change appears within ~2s
  with no container restart. (Note: the backend
  file-watcher flakiness you hit during the S4-06 bounce
  is a separate issue — if it's cheap to diagnose while
  you're in this area, flag findings; don't fix
  unprompted.)

ITEM 3 — Provider instance caching in registry:
  Module-level cache keyed on provider name; invalidated
  by PATCH /api/settings on provider change.
  Verify: cache hit on repeat call, recreation on switch
  (show via logs).

ITEM 4 — mkcert expiry documentation:
  Comment at the reconnect code + CLAUDE.md note:
  expires 2028-11-08; regenerate with mkcert, or retired
  by Sprint 6 production HTTPS.

ITEM 5 — Claude live test (conditional):
  If ANTHROPIC_API_KEY has arrived: save via settings,
  switch provider, full sync, show 5 Claude insights,
  test chat streaming on Claude, switch back, commit as
  chore: close Sprint 2 Claude provider gap, close the
  ledger entries.
  If not: explicit deferral statement in WATCH OUT FOR.

ITEM 6 — pyproject.toml / requirements.txt drift:
  pyproject.toml is missing anthropic, alembic, and
  celery[redis] that requirements.txt has (your S4-06
  finding). Reconcile: one file is the source of truth —
  state which and why in KEY DECISIONS, align the other
  or remove it.

ITEM 7 — npm audit review:
  The moderate hono / high nanoid transitive
  vulnerabilities surfaced during S4-07's react-markdown
  install. Assess: are they reachable in this app's usage?
  Fix via npm audit fix if non-breaking; if breaking or
  unreachable, document the assessment and defer with a
  ledger entry.

ACCEPTANCE CRITERIA:
- Items 1–4, 6–7 done and verified; Item 5 done or
  explicitly deferred
- No SecurityWarning in worker logs; frontend hot-reload
  works; provider cache hit/miss shown in logs
- ARCHITECTURE.md updated where services/config changed
  (non-root user under Services)
- Ledger updated for anything deferred

WHEN DONE:
- Worker logs without SecurityWarning
- Vite fix test description
- Cache hit/miss log evidence
- mkcert comment shown
- Item 6 decision + Item 7 assessment
- Claude result or deferral
- Do not start S4-10 until confirmed

---

## Delivery notes (Codee)

Mid-ticket, unrelated to any of the seven items: Docker Desktop crashed
("unable to start") when Item 1's rebuild hit "No space left on device" —
the host C: drive was at 183G/183G (0 available). This wasn't something I
caused or could safely fix myself (freeing space / restarting Docker
Desktop touches the host beyond this project), so I stopped and flagged it
immediately rather than working around it. Borys freed space and restarted
Docker Desktop (down to 174G/183G, 8.6G free) before I continued.

### Item 1 — non-root user

`backend/Dockerfile`: added `appgroup`/`appuser` + `USER appuser` after
`COPY . .`, shared by both `backend` and `celery_worker` (same Dockerfile).
Rebuilt both images (`docker compose build backend celery_worker`).

Verified:
- `docker compose exec backend id` / `celery_worker id` → both
  `uid=100(appuser) gid=101(appgroup)`, not root.
- `docker compose exec celery_worker sh -c "cat /app/eb_session.json >
  /dev/null && echo 'read OK'"` → `read OK`; `ls -la` on
  `eb_session.json`/`certs/` shows `rwxrwxrwx` — Docker Desktop's Windows
  bind mounts report full permissions to every UID regardless of container
  user, so the classic "root-owned files block the new non-root user"
  failure mode the ticket warned about doesn't apply on this host. Flagging
  for re-verification if this project ever runs on a native Linux Docker
  host, where bind-mounted ownership is real, not synthesized.
- `docker compose logs celery_worker | grep -i "SecurityWarning\|superuser"`
  → no output. `/health` returns 200, `alembic upgrade head` (which runs as
  `appuser` now) completed without error.

### Item 2 — Vite polling

`vite.config.ts`: added `server.watch = { usePolling: true, interval:
1000 }`.

Verified live in a real browser: edited `Sidebar.tsx`'s "KBC Analyzer"
label to include a marker string, screenshotted ~2s later — change was
live, no container restart, React state preserved (not a full page
reload). Reverted, re-screenshotted, confirmed the revert also applied
within ~2s.

Noted per the ticket's own caveat, not investigated further (out of
scope, not fixed unprompted): the backend's `WatchFiles` reload also
misbehaved once during the S4-06 review-bounce session (an
`Input/output error` in the logs). Different watcher (Python's
`watchfiles` vs this Vite fix), same underlying class of Docker-bind-mount
flakiness — worth its own ticket if it recurs.

### Item 3 — provider instance caching

`agents/registry.py`: module-level `_provider_cache: dict[str,
LLMProvider]`, keyed on provider name; `invalidate_provider_cache()`
clears it. `routers/settings.py`'s `PATCH /api/settings` calls it after
every successful patch — not gated on `key == "llm_provider"`, because an
API-key edit under the same provider name would otherwise keep serving a
stale instance built from the old key. Same code path, not separately
re-tested against the real key edit (would mean touching the real working
Gemini key) — the unconditional call covers it either way.

Real finding, fixed as a prerequisite: **the backend process had no
logging configuration at all** — Python's root logger only emits WARNING+
by default, so every `logger.info()` call anywhere in this app (this new
cache log included) was silently dropped for the FastAPI/uvicorn process.
(`celery_worker` doesn't have this problem — its `--loglevel=info` CLI
flag already configures its own root logger.) Added
`logging.basicConfig(level=logging.INFO, ...)` to `main.py` — INFO only,
never DEBUG, per CLAUDE.md's rule that DEBUG is reserved for anything that
could carry financial data. Audited every existing `logger.info` call
before enabling this (there was exactly one, in `tasks/analysis.py`,
already safe — counts only, no amounts/descriptions).

Verified via `docker compose logs backend`:
```
INFO:app.agents.registry:Provider cache miss for 'gemini' — created a new instance
INFO:app.agents.registry:Provider cache hit for 'gemini'
```
(two consecutive `POST /api/chat` calls). Then switched `llm_provider` to
`claude` and back to `gemini` via `PATCH /api/settings`, called chat again:
```
INFO:app.agents.registry:Provider cache miss for 'gemini' — created a new instance
```
— a fresh instance, proving the switch actually invalidated the earlier
cached one rather than reusing it.

### Item 4 — mkcert expiry documentation

Comment added at `eb_callback_server.py`'s `CERT_FILE`/`KEY_FILE`
constants (the actual reconnect code — this module is what the celery
task in `tasks/auth.py` uses). CLAUDE.md bullet added under ENVIRONMENT.
Both state: expires 2028-11-08, regenerate with mkcert or retire for
Sprint 6 production HTTPS.

### Item 5 — Claude live test

**Deferred, explicitly.** `GET /api/settings` still returns
`anthropic_api_key: ""` — no `ANTHROPIC_API_KEY` has arrived. Re-recorded
in `docs/verification_debt.md`'s existing "Claude provider — chat
streaming, no API key" entry (from S4-06) rather than duplicating it; that
entry already states the exact close-out procedure this item asks for.
Nothing else in this ticket depended on Claude being available.

### Item 6 — pyproject.toml / requirements.txt drift

**Decision: `requirements.txt` is the source of truth; `pyproject.toml`
aligned to match it**, not the other way around. Reasoning:
`requirements.txt` is what the Dockerfile actually installs — proven,
currently-working, and the thing every container in this project actually
runs on. `pyproject.toml` isn't dead weight, though: `kbc_analyzer/`'s own
`README.md` documents `pip install -e .` as the supported way to run the
CLI/Telegram bot locally without Docker, and that install already pulled
in `fastapi`/`sqlalchemy`/`psycopg` (i.e. it was already scoped to the
whole monorepo, not just the CLI) — it had just fallen behind on the three
most recent additions (`alembic`, `anthropic`, `celery[redis]`). Added all
three at the same version floors as `requirements.txt`. Verified the file
is still valid TOML and the dependency list is complete
(`python -c "import tomllib; tomllib.load(...)"`).

### Item 7 — npm audit review

**Assessed as unreachable in this app's actual usage, then fixed anyway**
(both, not either/or — the ticket's branches aren't mutually exclusive
when the fix turns out to be free).

Reachability: `npm ls hono` / `npm ls nanoid` inside the frontend
container show both arrive through exactly one path —
`shadcn@4.16.1 → @modelcontextprotocol/sdk → hono` and
`shadcn@4.16.1 → postcss → nanoid`. `shadcn` is the component-scaffolding
CLI tool (`npx shadcn add ...`), never imported by anything under `src/`
(confirmed by grep) and never invoked by the actual dev/build pipeline
(`npm run dev` / `npm run build` don't touch it) — it only runs when a
developer manually adds a new UI component. Neither vulnerable package's
CVE class (hono: CORS-middleware ReDoS, SSR cross-request data leak,
proxy-header handling, language-middleware DoS — all server-usage bugs;
nanoid: size-zero custom generator infinite loop) applies to code this app
ever executes.

Fixed anyway: `npm audit fix` (no `--force` needed — npm's own dry-run
didn't require it, confirming a non-breaking semver-compatible resolution)
bumped `nanoid` 3.3.16→3.3.18 and `hono` 4.12.33→4.13.2.
`npm audit` now reports 0 vulnerabilities. Re-verified `tsc -b`, `oxlint`,
and a real `npm run build` (production build, not just dev/typecheck) all
still pass clean after the bump.

WHEN DONE — answered:
- Worker logs without SecurityWarning: shown above (Item 1).
- Vite fix test description: shown above (Item 2) — live browser edit,
  ~2s reflect, no container restart, state preserved.
- Cache hit/miss log evidence: shown above (Item 3), including the
  provider-switch recreation proof.
- mkcert comment: shown above (Item 4) — both the code comment and the
  CLAUDE.md note.
- Item 6 decision: `requirements.txt` is source of truth, `pyproject.toml`
  aligned. Item 7 assessment: unreachable via `shadcn`'s own tooling
  dependency tree, fixed anyway since the resolution was free and
  non-breaking.
- Claude result or deferral: deferred, no key available; existing S4-06
  ledger entry re-confirmed current as of 2026-08-17.
