Status: delivered
Source: issued directly in Claude Code session, 2026-08-18

---

================================================================
TICKET S5-07 — Security Pass
================================================================

PRIORITY WITHIN TICKET: Item 1 first — it is a live
violation of a non-optional CLAUDE.md rule in shipped code.

WHAT TO BUILD:

  ITEM 1 — Date-range validation on all endpoints:
  CLAUDE.md mandates: "Validate date ranges on the backend.
  date_from must be before date_to. Maximum range: 365
  days. Return 400 with a clear message if violated."
  Verified in S4-10 review: only GET /api/insights/compare
  enforces this. GET /api/statistics, GET /api/transactions,
  GET /api/insights, and POST /api/transactions/sync all
  return 200 for backwards and >365-day ranges.
  Fix: extract the existing validation from the compare
  endpoint into a shared dependency or validator, apply it
  to all five. Same error shape everywhere.

  ITEM 2 — Input validation audit:
  Every endpoint taking user input: confirm Pydantic
  models constrain what they should (string lengths,
  numeric ranges, enum values where applicable). Report
  anything unconstrained. Fix what is clearly wrong; flag
  anything requiring a product decision.
  While here: also check settings_service.py's
  VALID_PROVIDERS vs API_KEY_FIELD_BY_PROVIDER — the
  KeyError robustness gap flagged in S5-06's review.
  Collapse them into one source of truth (a single dict
  or enum that both derive from) so a future provider
  added to one can't silently miss the other.

  ITEM 3 — Rate limiting:
  Add basic rate limiting, prioritizing the endpoints that
  cost money or hit third parties: POST /api/chat, POST
  /api/transactions/sync, POST /api/analysis/*.
  Suggest slowapi or an equivalent lightweight approach.
  Limits should be generous for a single user but present
  — the point is a ceiling before Sprint 6 exposes this
  publicly, not throttling normal use. State the limits
  chosen and why.

  ITEM 4 — CORS production configuration:
  Current CORS accepts FRONTEND_ORIGIN. Verify it is not
  wildcard in any configuration path, and that the
  production deployment in Sprint 6 will have a correct
  value. Document what Sprint 6 must set.

  ITEM 5 — Secrets handling review:
  Audit against CLAUDE.md's rules: no secrets in code or
  comments, nothing sensitive at INFO log level (the
  logging fix in S4-09 enabled INFO — re-audit every
  logger call now that they actually emit), .gitignore
  covers .env, eb_session.json, dedup logs, certs, and
  any test artifacts. Confirm no financial data appears
  in logs at any level that runs in production.
  While here: apply the new verification_debt.md
  Conventions rule (shape-and-schema evidence only, no
  real amounts/merchants) as a general check — confirm
  no OTHER committed file besides the two already-flagged
  ledger entries carries real financial data. If any do,
  flag them the same way (documented exception), don't
  silently edit.

ACCEPTANCE CRITERIA:
- All five date-range endpoints return 400 for backwards
  and >365-day ranges, with a consistent message shape
- Input validation findings reported; clear issues fixed
- VALID_PROVIDERS / API_KEY_FIELD_BY_PROVIDER collapsed
  to one source of truth
- Rate limiting active on the named endpoints, limits
  documented and justified
- CORS verified non-wildcard; Sprint 6 requirements
  documented
- Secrets audit complete, with the INFO-level log audit
  explicitly covered, and a repo-wide real-data check done
- Tests for the date-range validation across all five
  endpoints (coordinate with Tester — flag to them, don't
  build the tests yourself if S5-04's suite structure
  isn't yours to extend directly; check current convention
  established this sprint)

WHEN DONE:
- Show 400 responses from all five endpoints
- Report the input validation, provider-mapping, and
  secrets audit findings
- State the rate limits and the reasoning
- Explain: why is the INFO-level log audit specifically
  necessary now when it wasn't before?
- Do not start S5-08 until confirmed

## WHEN DONE — answered (2026-08-18, all live against the real stack):

**Item 1 — 400 responses from all five endpoints**, extracted into
`date_range.py` (one source of truth: `validate_date_range` /
`require_valid_date_range` for the three GET endpoints /
`validate_date_range_body` for the POST body case), `GET
/api/insights/compare` refactored to delegate to the same function rather
than its own duplicate:
- `GET /api/statistics?date_from=2026-08-18&date_to=2026-08-01` → 400
  `{"detail":"date_from/date_to: date_from must be before or equal to date_to."}`
- `GET /api/transactions?date_from=2026-08-18&date_to=2026-08-01` → same
  400, same message shape
- `GET /api/insights?date_from=2026-08-18&date_to=2026-08-01` → same
- `POST /api/transactions/sync` with `{"date_from":"2026-08-18","date_to":"2026-08-01"}`
  → same 400 — confirmed live it fires *before* `sync_lock.acquire()` is
  ever called (`GET sync_lock:global` stayed empty after the rejected
  request)
- `GET /api/statistics?date_from=2025-01-01&date_to=2026-06-01` (>365
  days) → 400 `{"detail":"date_from/date_to: range cannot exceed 365 days."}`
- Regression-checked: valid ranges on all four, plus `GET
  /api/insights/compare` itself, still return 200 with correct data after
  the refactor.

**Item 2 — input validation audit:**
- Fixed: `ChatRequest.message`/`ChatMessage.content` capped at 4000
  chars, `ChatRequest.history` capped at 50 turns (every chat call is a
  real, billed LLM call — these bound *how much* each call can cost,
  complementing Item 3's cap on *how often*). Empty/whitespace-only
  message rejected with a router-level 400, not a Pydantic `min_length`
  (keeps that common case a clear 400 instead of a generic 422).
  `CreateCategoryRequest.name` capped at 100 chars (`categories.name` is
  an unbounded `Text` primary key). `GET /api/transactions/search`'s `q`
  capped at 200 chars (was previously `min_length=1` only).
- Fixed: `settings_service.VALID_PROVIDERS`/`API_KEY_FIELD_BY_PROVIDER`
  collapsed — `VALID_PROVIDERS = set(API_KEY_FIELD_BY_PROVIDER)`, so a
  provider added to one can't silently miss the other (the S5-06-flagged
  `KeyError` gap). `get_decrypted_api_key` also made defensive (`.get()`
  + a named `InvalidSettingError` instead of a bare `KeyError`) even
  though that path is now structurally unreachable.
- Flagged, not fixed (product decisions, not clear bugs):
  `PatchTransactionRequest.description`/`subcategory` remain
  unconstrained — no obviously-correct length cap for a transaction
  description. `POST /api/analysis/categorize` (optional dates) and
  `POST /api/analysis/insights` (required dates) have no date-range
  validation at all and were outside this ticket's named "five" — same
  gap as Item 1 in spirit, PM's call whether to extend it there too.
  `CallbackRequest.code`/`state` and `PatchSettingsRequest.value` (the
  API-key case) remain unconstrained — external-service-validated or
  intentionally opaque-secret fields, capping them risks rejecting
  legitimate values for an unclear benefit.
- Everything else reviewed: budget amount positivity (`create_budget`/
  `patch_budget`) already checked at the router level before reaching the
  DB's own `CHECK` constraint — no gap. Category/provider `Literal` fields
  already fully constrained. `PatchCategoryRequest`/`CreateCategoryRequest`
  color already validated by `colors.describe_validation_failure()`.

**Item 3 — rate limiting**, `slowapi`, `rate_limit.py`:
- `POST /api/chat`: **20/minute**. `POST /api/transactions/sync`, `POST
  /api/analysis/categorize`, `POST /api/analysis/insights`: **10/minute**
  each.
- Reasoning: every one of these is a real, billed LLM call (chat, sync's
  categorization+insights, and the two standalone analysis endpoints), or
  in sync's case also a real Enable Banking call. 20/min for chat is
  generous for genuinely fast back-and-forth typing; 10/min for the
  others reflects that a real user triggers these occasionally per
  session, not rapidly. All four are a real ceiling against a runaway
  client/retry loop or (post-Sprint 6) casual abuse — not a limit normal
  use would ever brush against.
- Live-verified mechanically (fast-failing empty-message chat requests,
  since the real endpoints are too slow to reliably pack many into one
  rate-limit window): 20 requests got their normal 400 (empty message),
  request 21 and 22 got `429 {"message":"Rate limit exceeded (20 per 1
  minute). Please try again shortly."}` — exact limit enforced, correct
  shared error shape.
- In-memory storage (documented in `rate_limit.py` and ARCHITECTURE.md):
  fine while `backend` is one process; Sprint 6 should key on `user_id`
  instead of remote address once real auth exists, and consider Redis
  storage if `backend` ever runs multi-worker.

**Item 4 — CORS**, live-verified: an `OPTIONS` preflight from
`http://localhost:5173` (the real configured `FRONTEND_ORIGIN`) gets
`access-control-allow-origin: http://localhost:5173` back; the identical
request from `http://evil.example.com` gets no
`access-control-allow-origin` header at all (`400`, correctly rejected).
Confirmed by reading: exactly one CORS configuration path in the whole
codebase (`main.py`'s `CORSMiddleware`), always
`allow_origins=[frontend_origin]`, never a wildcard or a hardcoded list.
Sprint 6 requirement documented in ARCHITECTURE.md: `docker-compose.yml`
currently hardcodes `FRONTEND_ORIGIN: http://localhost:${FRONTEND_PORT:-5173}`
for the `backend` service (dev-only) — Sprint 6 must set it to the real
production frontend URL; there's no production compose file yet, so this
is a real gap, not just a value swap.

**Item 5 — secrets handling review:**
- `.gitignore` covers `.env`, `*.pem`, `eb_session.json`,
  `kbc_auth.json`, `kbc_requisition.json`, `kbc_transactions.db`, the
  dedup log — confirmed none of these are actually tracked (`git ls-files`
  came back empty for all of them). `kbc_analyzer/.env.example` contains
  only placeholder values (`AIza...`, `sk-ant-...`, `change_me`) — no real
  secrets. `git log --all -S` pickaxe search for a real-looking Anthropic
  key pattern found only that same placeholder string, from S2-04's
  commit adding `.env.example` — no real key was ever committed.
- Every `logger.*` call site in `app/` read individually: all safe — ids,
  counts, provider/category names, or exception messages only, never a
  transaction amount or description. No stray `print()` statements
  bypassing the logging framework.
- **Repo-wide real-financial-data check (the new verification_debt.md
  Conventions rule, applied generally per this ticket's instruction):**
  found four more files beyond the two already-flagged ledger entries —
  `docs/tickets/S4-06-ai-chat-backend.md`, `S4-08-period-comparison.md`,
  `S4-10-sprint-4-polish-verification-debt-e2e.md`, and this sprint's own
  `S5-06-verification-debt-burn-down.md` — all carrying real amounts
  (and S5-06 real merchant names) from live-verification write-ups
  predating the rule. Each flagged in place with the same one-line
  "known exception, not retroactively scrubbed" note used in
  `verification_debt.md`, not edited otherwise. Test fixtures
  (`tests/fixtures/factories.py` and friends using "Delhaize Ixelles" as
  a synthetic description) are **not** a violation — realistic-looking
  fabricated test data is normal practice, not real user data.
- **One separate, more serious finding — not a logging issue, flagged
  rather than touched:** `kbc_analyzer/backend/kbc_analyzer/analysis.py`
  (the legacy CLI/Telegram-bot module, untouched by the web app rebuild)
  hardcodes four real IBANs and the account holder's real full name
  directly in its Gemini system prompt (`SYSTEM_PROMPT`, lines ~54-57),
  plus a real counterparty business name. This is committed source code,
  not documentation — a materially different and more sensitive exposure
  than the ledger/ticket amounts above (a real bank account identifier,
  not a spending total). Not edited, per this ticket's own "flag, don't
  silently edit" instruction — this needs Borys's explicit call on
  whether/how to address it (a normal commit only fixes it going forward,
  not in git history), surfaced prominently in this ticket's chat summary
  rather than buried in this file.

**Item 2's test-coordination flag (not built here):** date-range
regression tests for all five endpoints — one backwards-range and one
>365-day test per endpoint, asserting the exact `{"detail": "date_from/date_to: ..."}`
shape — are Tester-agent scope (S5-04's suite structure), matching this
sprint's established convention (S5-05 flagged its own test needs the
same way, in its ticket file's WHEN DONE, rather than building them).
