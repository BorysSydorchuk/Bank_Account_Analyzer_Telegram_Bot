Status: in-progress
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
