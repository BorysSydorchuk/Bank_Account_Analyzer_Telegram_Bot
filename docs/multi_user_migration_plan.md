# Multi-User Migration Plan

Produced by S5-01 (Sprint 5 schema/singleton audit). This is the primary
input to Sprint 6 ("Multi-User & Deployment") — every claim below was
verified directly against the running schema and the current codebase on
2026-08-17, not recalled from memory or prior tickets. Verification method
is stated at the end of each section.

No code changes were made producing this document — S5-01 is audit only,
per its own acceptance criteria.

**Re-verified 2026-08-19 (S5-08 sprint close)** against everything S5-02,
S5-05, and S5-07 changed after this plan was originally written. Three
real gaps found and closed below (marked **[S5-08]**): S5-02's new
`transactions.category` foreign key wasn't accounted for against the
already-DECIDED `categories` primary-key change; `sync_lock.py` (S5-05)
and `rate_limit.py` (S5-07) are both new module-level state this plan
never catalogued. Everything else re-checked line-by-line against current
`app/models.py`, `app/routers/*.py`, and `app/crud.py` — no other drift
found; the rest of this document is unchanged from S5-01.

---

## Tables

| Table | Has `user_id` today? | Needs `user_id`? | Migration step |
|---|---|---|---|
| `transactions` | No | **Yes** | Add nullable `user_id UUID`, backfill every existing row to the bootstrap user (see Ordering), then `ALTER COLUMN user_id SET NOT NULL` in a follow-up migration once backfill is verified. |
| `categories` | No | **Yes — DECIDED** (PM ruling, 2026-08-17) | Same nullable→backfill→NOT NULL sequence as `transactions`. Primary key becomes `(user_id, name)`. |
| `settings` | No | **Yes — DECIDED** (PM ruling, 2026-08-17) | **This is a schema change, not just a scoping addition** — unlike `transactions`/`categories`/`insights`, there's no nullable-column-then-backfill path available, because `settings` isn't row-per-entity today, it's a flat global key-value store (`key TEXT PRIMARY KEY`). Going per-user means either widening the primary key to `(user_id, key)` and duplicating the existing global rows once per user at migration time, or splitting into a proper `user_settings` table entirely. Either way this is a structural redesign of the table's shape, not an `ALTER TABLE ... ADD COLUMN`. |
| `budgets` | **Yes** (nullable, S4-05) | Already has the column | Backfill existing `NULL` rows to the bootstrap user, then `ALTER COLUMN user_id SET NOT NULL`. No new column needed — this table was already built multi-user-ready. |
| `insights` | No | **Yes** | Same nullable→backfill→NOT NULL sequence as `transactions`. Insights are generated from a specific user's transactions over a specific range; without `user_id` two users syncing overlapping date ranges would silently overwrite each other's insight rows (the `(date_from, date_to)` index has no user dimension today). |

**Backfill strategy (all tables):** every existing row belongs to Borys —
concretely, the single user account created by his first Google OAuth
login in Sprint 6. This means the `users` table and Borys's own row must
exist *before* any of these backfills run (see Ordering).

**The categories/settings decision — DECIDED (PM ruling, 2026-08-17):
both go per-user.** Originally raised here as a recommendation pending
Borys/PM confirmation (see git history for the original framing); now
resolved. Settings in particular: a shared API key means one user's key
funds every other user's LLM calls — that's a billing hole, not a design
choice, and it directly collides with Sprint 8's usage-limits work (a
per-user limit is meaningless against a key nobody but the first user
actually owns). Categories go per-user for the reason already argued
here: a personal color override (S3-06) is meaningless as a *shared*
override once a second user exists. Both are now firm inputs to Sprint
6's migration, not open questions — see the Tables row above for
settings' schema-shape consequence specifically.

*Verified via: `grep -n "^class \|__tablename__" app/models.py`, then a
full read of `app/models.py` for every column, constraint, and existing
`user_id` usage — not `\d+` against the live database, since the schema
in the models file is already the authoritative, migration-tracked
source (Alembic's `env.py` autogenerates against exactly this file).*

---

## Constraints

| Constraint | Today | Must become | Risk if unchanged |
|---|---|---|---|
| `transactions` — `UNIQUE (external_id)` | Global, added S4-01 specifically because `account_id` isn't stable across reconnects | `UNIQUE (user_id, external_id)` **— pending empirical validation, see below** | **This is the single highest-risk item in this entire plan.** Enable Banking's `external_id` is unique *per bank*, not globally across all Enable Banking customers — two different real users of this app, both connecting a KBC account, could plausibly receive an overlapping `external_id` from Enable Banking's numbering (unverified whether Enable Banking guarantees global uniqueness across all its client apps; the safe assumption is that it does not). Left as a bare global `UNIQUE`, the *second* user's sync would either silently upsert into the *first* user's transaction row (via the existing `ON CONFLICT (external_id) DO UPDATE` in `crud.upsert_transactions`) or reject the insert — either way, one user's transaction data leaks into or blocks the other's. This is a direct repeat of the S4-01 incident class, just keyed on `user_id` instead of `account_id`. |
| `categories` — `PRIMARY KEY (name)` | Global | `PRIMARY KEY (user_id, name)` **— DECIDED, categories go per-user** (PM ruling, 2026-08-17) | Confirmed change, not conditional: two users couldn't both have a category named "Groceries" without this. |
| `budgets` — `UNIQUE NULLS NOT DISTINCT (user_id, category, period)` | **Already correct** — built this way in S4-05 specifically anticipating multi-user | Add `NOT NULL` to `user_id` once backfilled; the constraint shape itself needs no change | None — this is the one table already done right. |
| `settings` — `PRIMARY KEY (key)` | Global | `PRIMARY KEY (user_id, key)` **— DECIDED, settings go per-user** (PM ruling, 2026-08-17) | Confirmed change, not conditional — see Tables above for why leaving this global is a billing hole, not a neutral default. |

**[S5-08] `categories(name)`'s foreign-key references — a gap this plan
didn't originally cover.** S5-02 (after this plan was written) added
`transactions.category FK → categories(name) ON UPDATE CASCADE ON DELETE
SET NULL`, alongside the pre-existing `budgets.category` FK with the same
target. Both currently reference `categories.name` as a single-column
key — which only works while `name` is `categories`' primary key. Once
`categories`' primary key becomes `(user_id, name)` (DECIDED above), a
single-column FK to `name` alone is no longer valid: Postgres requires a
foreign key to reference a unique constraint or primary key on the
*exact* column set it points at, and `name` alone won't be either
anymore. **Both FKs must become composite — `(user_id, category)` on the
referencing side, `(user_id, name)` on `categories`** — added to step 6
of the Ordering section below (constraint updates), same migration
window as `categories`' own primary-key change, since a FK update to a
table whose PK is mid-change has to land in the same step or the FK
would reference a stale shape for however long the gap lasted. Not
optional or deferrable: leaving these as single-column FKs after
`categories`' PK changes would either break the migration outright (FK
creation fails against a non-matching target) or, worse, silently keep
matching only on `name` — meaning `transactions.category`/`budgets.category`
could point at a *different user's* category row with the same name.

**`transactions.external_id` uniqueness — CLAUDE.md EXTERNAL SYSTEM
ASSUMPTIONS violation, flagged 2026-08-17 (PM):** the risk description
above rests on an assumption — that Enable Banking's `external_id`
(`entry_reference` in their API) is not guaranteed unique across their
whole customer base — that has never actually been validated against
vendor documentation or an empirical test. Per CLAUDE.md, an assumption
about an external system's uniqueness/identity guarantee must be
validated one of three ways before being built on: vendor documentation
stating it, an empirical test, or an explicit unvalidated-assumption
note with the failure mode if wrong. This entry was, until this
correction, only the third of those — stated as an assumption, not
resolved. **A pre-migration validation task is now step 0 of the
Ordering section below**, ahead of any schema work: check Enable
Banking's API documentation for `entry_reference`'s uniqueness scope. If
documented as globally unique, `UNIQUE (external_id)` alone remains
correct and no per-user change is needed on this specific constraint (the
`user_id` column addition still happens for scoping every other query,
independent of this). If the scope is undocumented or explicitly
per-bank/per-connection, the safe default is `UNIQUE (user_id,
external_id)`, and `crud.upsert_transactions`'s `ON CONFLICT` clause must
match on both columns, not `external_id` alone — this is the same class
of burn as S4-01, and the fix must not repeat S4-01's mistake of trusting
an unverified vendor guarantee a second time.

*Verified via: `grep -n "UniqueConstraint\|primary_key=True\|ForeignKey" app/models.py`
plus the migration files under `app/migrations/versions/` for the ones
declared there rather than in the ORM layer.*

---

## Endpoints

25 endpoints total across 10 routers. **Only the 4 budget endpoints scope
any query by `user_id` today** — every other endpoint in the application
returns or mutates data unconditionally across all rows, because there is
currently exactly one user and no auth layer to scope against.

| Router | Endpoints | Scoping change required |
|---|---|---|
| `transactions.py` | `POST /sync`, `GET ""`, `GET /search`, `PATCH /{id}` | All four need `user_id` threaded through: sync writes must tag new rows with the requesting user; the two GETs must filter by it; the PATCH additionally needs an ownership check, not just scoping — see "Separate workstream: authorization gaps" in Ordering. |
| `categories.py` | `GET ""`, `PATCH /{name}`, `POST ""`, `POST /{name}/reset` | All four need `user_id` scoping — categories are going per-user (DECIDED, see Tables). |
| `settings.py` | `GET ""`, `PATCH ""`, `POST /test-connection` | `GET`/`PATCH` need `user_id` scoping — settings are going per-user (DECIDED, see Tables). `test-connection` doesn't touch storage at all (it takes a key directly in the request body) — no change needed there regardless. |
| `budgets.py` | `GET ""`, `POST ""`, `PATCH /{category}`, `DELETE /{category}` | **Already done** — `crud.get_budget`, `list_budgets_with_status`, `create_budget`, `update_budget_amount`, `delete_budget` all take `user_id` today; only the router's `CURRENT_USER_ID = None` placeholder needs to become a real value from the auth session. |
| `insights.py` | `GET ""`, `GET /compare` | Both need `user_id` filtering added to `crud.list_insights` (currently filters only by `date_from`/`date_to`). |
| `analysis.py` | `POST /categorize`, `POST /insights` | Both operate on whatever `crud.get_uncategorized_transactions`/`list_transactions` return — needs `user_id` threaded the same way as the transactions endpoints. |
| `chat.py` | `POST ""` | `chat_service.build_context` reads transactions/budgets/insights directly — needs `user_id` threaded through the whole context-assembly chain, not just the top-level router. |
| `jobs.py` | `GET /{job_id}` | **Authorization gap, not just scoping** — see "Separate workstream: authorization gaps" in Ordering. `job_store.get_job` has no ownership concept at all — any caller who knows a `job_id` (a random UUID, so not practically guessable, but still) can read another user's job status, including embedded insight text. Needs an ownership check (the job payload must record who started it), not a query filter — jobs aren't queried by user, they're looked up by ID. |
| `auth.py` | `GET /status`, `POST /reauthorize`, `POST /callback` | All three currently talk to the single global `EnableBankingService`/`eb_session.json`. Needs the whole Enable Banking session layer to become per-user first (see Files on disk) — the endpoints themselves are thin wrappers and change trivially once that's done. |
| `statistics.py` | `GET ""` | Needs `user_id` filtering added to `crud.list_transactions`. |

**Endpoints that "return all rows unconditionally" today, flagged
explicitly per the ticket's ask:** `GET /api/transactions`, `GET
/api/transactions/search`, `GET /api/statistics`, `GET /api/insights`,
`GET /api/insights/compare`, `GET /api/categories`, `GET /api/settings` —
every one of these currently has zero `WHERE` clause on any user
dimension, because `crud.py` has no concept of one to filter on outside
the five budget functions.

*Verified via: `grep -n "@router\.\(get\|post\|patch\|delete\|put\)"
app/routers/*.py` for the complete endpoint list (25 matches), then
`grep -n "^def " app/crud.py` to confirm exactly which crud functions
accept a `user_id` parameter today. **Correction (Reviewer/Borys,
2026-08-17): that grep first said 4 — it actually missed `get_budget`
(`crud.py:334`, called from `routers/budgets.py:42`) and undercounted
because `update_budget_amount`'s signature spans two lines
(`def update_budget_amount(` on one line, `user_id` on the next) — a
`^def ` pattern matched against a single line doesn't see parameters that
aren't on that line. The correct count is 5. Re-verified by reading every
line of `crud.py` rather than grepping `^def ` alone; any future
re-verification of this count should do the same, or grep across the
full function signature (e.g. with `-A2`) rather than the def line in
isolation.** Then a full
read of `transactions.py`, `categories.py`, and `job_store.py` to confirm
the IDOR-shaped gaps on `PATCH /api/transactions/{id}` and `GET
/api/jobs/{job_id}` specifically.*

---

## Singletons and module-level state

- **`agents/registry.py`'s `_provider_cache`** (module-level `dict[str,
  LLMProvider]`, added S4-09, already flagged in S4-09 review and
  recorded in `docs/verification_debt.md`'s Sprint 5 audit scope). Keyed
  on provider name only — once auth lands, the first user to trigger a
  Gemini/Claude call caches an instance built from *their* API key, and
  every subsequent user's request reuses it. Must become keyed on
  `(user_id, provider_name)`, or be moved out of module scope entirely
  into a per-request/per-session cache.
- **The `settings` table itself** is a global singleton by construction
  (flat key-value, no row-per-user concept) — covered under Tables/
  Constraints above; restated here because CLAUDE.md's MULTI-USER
  READINESS rule names it explicitly as "grandfathered... do not extend
  with per-user values" pre-Sprint-6.
- **Two `CURRENT_USER_ID = None` placeholders** already exist as
  intentional TODO markers: `routers/budgets.py:18` and
  `chat_service.py:27` (comment: `# TODO(Sprint 6): pass the
  authenticated user's id through`). These are the *known* seams — every
  function downstream of them already accepts `user_id` as a parameter,
  so Sprint 6 changes exactly one line at each site, not a function
  signature. This is the pattern every other table/endpoint above should
  be built to match.
- **[S5-08] `sync_lock.py`'s Redis key (S5-05) — already multi-user-ready,
  no migration work needed.** `sync_lock:{user_id or 'global'}` — the key
  derivation already takes `user_id` as a parameter (currently always
  called with `None`, hence `'global'`); Sprint 6 changes exactly one
  call site (the same `CURRENT_USER_ID` pattern `budgets`/`chat_service`
  already establish) to start passing a real value. Built this way
  deliberately at S5-05 time, anticipating this exact migration — the
  same "already done right" category as `budgets`.
- **[S5-08] `rate_limit.py`'s in-memory limiter (S5-07) — needs Sprint 6
  attention, not yet ready.** Keyed on remote address (`get_remote_address`),
  not `user_id` — there was no caller identity to key on when this was
  built (pre-auth, single-user). Once real users exist behind a shared
  reverse proxy or NAT, IP-keying would throttle unrelated users together
  under one shared limit instead of giving each their own. Must become
  keyed on the authenticated `user_id` at Sprint 6; also consider moving
  storage off in-memory onto Redis (already in this stack) if `backend`
  ever runs with more than one worker process, since in-memory state
  isn't shared across processes. Already flagged in ARCHITECTURE.md's
  Invariants at the point it was built; restated here since this document
  is the canonical singleton inventory Sprint 6 should work from.
- **`job_store.py`'s `_client`** (module-level Redis client) is a
  connection pool, not per-user state itself — fine to stay global. The
  keys it manages (`job:{job_id}`) are the actual gap, covered under
  Endpoints above (`GET /api/jobs/{job_id}`'s missing ownership check).
- **The Enable Banking OAuth callback catcher** (`eb_callback_server.py`,
  driven by `tasks/auth.py`'s `catch_enable_banking_callback`) is a
  single listener on port 3001, handling exactly one pending
  reconnect at a time — `CallbackPortBusyError` is raised, by design, if
  a second reconnect races the first. This is not just a data-scoping
  problem like the others; it's a genuine concurrency constraint. Once
  multiple users can each be mid-reconnect simultaneously, "one shared
  port, one pending callback at a time" cannot serve two of them at once.
  ARCHITECTURE.md already notes Sprint 6 retires this whole mechanism in
  favor of real public HTTPS — this item is the reason that retirement is
  a hard requirement, not an optional cleanup.
- **Nothing else found (S5-01 original scope), re-swept 2026-08-19
  [S5-08]** across everything S5-05/S5-07 added since — `sync_lock.py`
  and `rate_limit.py` above are the only two new module-level names those
  tickets introduced, both now catalogued. Searched every module-level
  assignment across `app/*.py`, `app/agents/**/*.py`, `app/tasks/*.py`,
  and `app/routers/*.py`; every other module-level name is either a pure
  constant (thresholds, model name strings, prompt templates), a
  `__all__` export list, or `db.py`'s `engine`/`SessionLocal` (a
  connection pool/session factory — the standard SQLAlchemy pattern, not
  per-user state; per-user scoping happens in the *queries* run through
  it, covered above).

*Verified via: `grep -rn "^[A-Za-z_][A-Za-z0-9_]* = " app/*.py
app/agents/*.py app/agents/providers/*.py app/tasks/*.py app/routers/
*.py`, manually reviewing every match; then full reads of
`job_store.py`, `eb_service.py`, and `tasks/auth.py` to confirm the
Redis-key and OAuth-callback findings against actual behavior, not just
the presence of module-level names.*

---

## Files on disk

- **`eb_session.json`** — a single Enable Banking OAuth session, read and
  written via a hardcoded module-level path (`kbc_analyzer/
  enablebanking.py`'s `SESSION_FILE = "eb_session.json"`), resolved
  relative to the process's working directory (`/app` inside both the
  `backend` and `celery_worker` containers). No per-user dimension
  anywhere in its read/write path. Sprint 6 needs per-user bank session
  storage — almost certainly a new table (e.g. `bank_sessions`, `user_id`
  + the OAuth token material, encrypted at rest the same way `settings`
  encrypts API keys today) rather than a file, since Sprint 6's public
  deployment target won't have a persistent local filesystem to keep a
  flat file on in the way a single developer's machine does. This isn't
  a "migrate the file" problem — it's a full redesign of where and how
  bank sessions live, which Sprint 6's "per-user OAuth" scope already
  anticipates.
- **`backend/certs/localhost.pem`/`localhost-key.pem`** (mkcert) and
  **`backend/private.pem`** (the app's Enable Banking registration key)
  are **not** per-user — they're deployment/app-level secrets (one mkcert
  pair for the local dev HTTPS callback, one registered app credential
  with Enable Banking shared by every user's consent flow). No change
  needed for multi-user specifically; both are already tracked separately
  in ARCHITECTURE.md as retiring/rotating on their own schedule
  (mkcert → real HTTPS at Sprint 6; the app credential doesn't change at
  all when the user count changes).

*Verified via: `grep -n "SESSION_FILE\|eb_session\.json" kbc_analyzer/
enablebanking.py` (the file path is a bare module-level string, not
templated on anything), and `grep -n "class EnableBankingService"` plus a
full read of `app/eb_service.py` confirming it reads app-level credentials
(`ENABLEBANKING_APP_ID`, `ENABLEBANKING_PRIVATE_KEY_PATH`) from
environment variables, not per-request state.*

---

## Ordering

Dependency-ordered sequence for Sprint 6 — schema and scoping work only.
The authorization-gap items (`GET /api/jobs/{job_id}`, `PATCH
/api/transactions/{id}`, `job_store`'s unscoped keys) are **not** in this
sequence — see "Separate workstream: authorization gaps" below for why.

0. **Validate `external_id`'s uniqueness scope against Enable Banking's
   API documentation, before any schema work on it** (PM ruling,
   2026-08-17 — see Constraints). Check whether `entry_reference` is
   documented as globally unique across their whole customer base, or
   only per-bank/per-connection. This determines whether step 7 below
   applies `UNIQUE (user_id, external_id)` (if undocumented or scoped) or
   confirms `UNIQUE (external_id)` alone remains correct (if documented
   as global). If vendor documentation doesn't resolve it either way, the
   safe default is the scoped constraint — do not carry an unvalidated
   assumption into Sprint 6 a second time.
1. **Create the `users` table** (Google OAuth identity — Sprint 6's own
   scope). Nothing below can proceed without this existing, since every
   subsequent step either adds a foreign key to it or backfills against a
   specific row in it.
2. **Bootstrap Borys's own user row** — either by having him complete the
   real Google OAuth login first (creating the row through the normal
   flow) and using that row's id for backfill, or by inserting a known
   bootstrap row directly in a migration if login must happen after
   backfill for ordering reasons. Either way, this must happen *before*
   step 4.
3. **Add nullable `user_id` columns** to `transactions`, `insights`,
   `categories`, and `settings` (all four — the per-user decision for the
   last two is made, see Tables). Nullable first, deliberately — this is
   the same pattern `budgets` already used in S4-05, and it means the
   column can exist and be backfilled without a single blocking migration
   that locks a live table while assigning every row at once. `settings`
   additionally needs its actual shape change here (widened primary key
   or split table — see Tables), not just a bolted-on column.
4. **Backfill every existing row** in every touched table to Borys's user
   id from step 2. Verify row counts before and after match exactly (no
   row should be silently dropped or duplicated by the backfill).
5. **Add `NOT NULL`** to each `user_id` column, in a separate migration
   from step 3, once step 4's backfill is verified complete. Running
   this before backfill finishes would fail outright (correctly) rather
   than silently corrupt data — but running it as part of the *same*
   migration as step 3 removes the verification window between "column
   added" and "column enforced," which is the whole point of splitting
   these two steps.
6. **Update constraints**: `transactions`'s `UNIQUE (external_id)` → the
   shape step 0 determined (the highest-risk item in this plan — see
   Constraints), and `categories`'s primary key to `(user_id, name)`
   (confirmed, not conditional). **[S5-08]** In the same migration,
   redefine `transactions.category` and `budgets.category`'s foreign
   keys as composite — `(user_id, category) → categories(user_id, name)`
   — since both currently reference `categories.name` alone and that
   stops being valid the moment `categories`' primary key changes shape
   (see Constraints). Must happen *after* step 5, not before —
   a `UNIQUE (user_id, external_id)` constraint is meaningless (and in
   Postgres, actually still permits full duplicates) while `user_id` can
   be `NULL` on every row.
7. **Thread `user_id` through every `crud.py` function** that doesn't
   already take it, following the exact pattern `budgets`'s five
   functions already establish. Mechanical but touches nearly every
   function in the file — the two `CURRENT_USER_ID = None` placeholders
   already mark where the router-level wiring point is.
8. **Wire routers to the real authenticated user** — replace both
   `CURRENT_USER_ID = None` placeholders and add the equivalent
   plumbing to every other router listed under Endpoints, once Sprint
   6's auth middleware exists to source a real value from.
9. **Fix `_provider_cache`** to key on `(user_id, provider_name)`.
10. **Redesign bank-session storage** off `eb_session.json` onto a
    per-user table, and **redesign the OAuth callback catcher** off its
    single-port/single-listener design — both are Sprint 6's "per-user
    bank sessions" and "public deployment with real HTTPS" scope
    already, listed here only to make the dependency explicit: nothing
    above technically blocks these two, but shipping multi-user without
    them means every user after the first still can't independently
    connect their own bank account.

**What breaks if this order is violated:** doing step 6 before step 5
(constraints before `NOT NULL`) produces a constraint that doesn't
actually protect anything, since `NULL <> NULL` in the columns it's
supposed to be distinguishing users by — the exact case S4-05 already
solved once for `budgets` with `NULLS NOT DISTINCT`, which only works
because `budgets.user_id` is *staying* nullable through Sprint 5; the
other tables are meant to end up `NOT NULL`, so they need the ordering
above instead of reusing that exact trick. Doing step 4 (backfill) before
step 2 (bootstrap user exists) has nothing to backfill *to* and either
fails or requires a throwaway placeholder id that then needs a second
backfill to correct. Doing step 8 (router wiring) before step 7 (crud
functions accept `user_id`) means the router has a real user id and
nowhere to pass it — the two have to land together or in that specific
order. Skipping step 0 and going straight to step 6 means guessing at
`external_id`'s real guarantee instead of checking it — exactly the
mistake step 0 exists to prevent.

---

### Separate workstream: authorization gaps (IDOR)

**Not part of the numbered sequence above, deliberately (PM ruling,
2026-08-17).** `GET /api/jobs/{job_id}`, `PATCH /api/transactions/{id}`,
and `job_store`'s unscoped `job:{job_id}` Redis keys all share a
different problem than everything above: those are queries that need a
`WHERE user_id = ...` added; these are single-resource lookups by ID that
need an *ownership check* added — confirming the caller is allowed to see
this specific job or transaction, not just filtering a list down to
theirs. Retrofitting authorization onto a by-ID lookup is a distinct kind
of work from adding a scoping clause to a list query, done at a different
layer (the router/dependency level, checking "does this id belong to this
caller" before returning anything) than the schema/crud threading above.

These three are **named targets for the Security Auditor agent**
(`AGENTS.md`'s roles table: activates in Sprint 6, before auth ships).
They don't block the schema migration sequence above and the schema
sequence doesn't block them — they can be picked up in parallel, but they
need their own review pass specifically for authorization logic, not
folded into the general crud/router threading work as if fixing them were
the same kind of change.

*Verified via: reasoning from the table/constraint/endpoint facts
established in the sections above, cross-checked against
`migrations/versions/c4a91d6e0f3b_add_budgets_table.py` — one correction
made while verifying: `budgets` created its nullable `user_id` column and
its `NULLS NOT DISTINCT` constraint together, in a single migration, not
in two separate steps. That's *not* a contradiction of the ordering
above; it's a different scenario. `budgets` was a brand-new table with no
existing rows to backfill, so there was nothing to protect against
between "column exists" and "constraint applies" — `NULLS NOT DISTINCT`
was the correct one-step answer for a table starting empty.
`transactions`/`insights` already hold real rows today, so they need the
nullable→backfill→`NOT NULL` split this plan specifies; `budgets` is the
precedent for the *target end state* (a working per-user unique
constraint), not for the migration sequencing to reach it.*
