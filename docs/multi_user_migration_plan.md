# Multi-User Migration Plan

Produced by S5-01 (Sprint 5 schema/singleton audit). This is the primary
input to Sprint 6 ("Multi-User & Deployment") — every claim below was
verified directly against the running schema and the current codebase on
2026-08-17, not recalled from memory or prior tickets. Verification method
is stated at the end of each section.

No code changes were made producing this document — S5-01 is audit only,
per its own acceptance criteria.

---

## Tables

| Table | Has `user_id` today? | Needs `user_id`? | Migration step |
|---|---|---|---|
| `transactions` | No | **Yes** | Add nullable `user_id UUID`, backfill every existing row to the bootstrap user (see Ordering), then `ALTER COLUMN user_id SET NOT NULL` in a follow-up migration once backfill is verified. |
| `categories` | No | **Decision needed** — see below | If per-user: same nullable→backfill→NOT NULL sequence as `transactions`. If shared/global: no schema change, document the decision in ARCHITECTURE.md Invariants instead. |
| `settings` | No | **Decision needed** — see below | If per-user: restructure from a flat `key TEXT PRIMARY KEY` table to either `user_id` added to a composite key `(user_id, key)`, or a dedicated `user_settings` table. CLAUDE.md currently says *"do not extend it with per-user values"* — that instruction is scoped to pre-Sprint-6 tickets, not a permanent rule; Sprint 6 is exactly the ticket that instruction defers to. |
| `budgets` | **Yes** (nullable, S4-05) | Already has the column | Backfill existing `NULL` rows to the bootstrap user, then `ALTER COLUMN user_id SET NOT NULL`. No new column needed — this table was already built multi-user-ready. |
| `insights` | No | **Yes** | Same nullable→backfill→NOT NULL sequence as `transactions`. Insights are generated from a specific user's transactions over a specific range; without `user_id` two users syncing overlapping date ranges would silently overwrite each other's insight rows (the `(date_from, date_to)` index has no user dimension today). |

**Backfill strategy (all tables):** every existing row belongs to Borys —
concretely, the single user account created by his first Google OAuth
login in Sprint 6. This means the `users` table and Borys's own row must
exist *before* any of these backfills run (see Ordering).

**The categories/settings decision, argued:**
Categories are currently a shared reference table (`name TEXT PRIMARY
KEY`) — every user would see the identical category list and colors if
left as-is. Settings holds the LLM provider choice and each provider's
API key — currently one deployment-wide choice. I recommend **both become
per-user** in Sprint 6: category colors are a personal preference (S3-06
already lets Borys override AI colors — that's meaningless as a *shared*
override once a second user exists), and API keys are literally
individual — a second user would need to bring their own Gemini/Claude
key, not spend Borys's quota. The alternative (keep both global/shared) is
simpler to migrate but means every user sees one person's category
customizations and one person's provider bill — I don't think that holds
up as the product's actual intent, but this is a product call, not a
purely technical one, and Borys/PM should confirm it explicitly before
Sprint 6 executes it.

*Verified via: `grep -n "^class \|__tablename__" app/models.py`, then a
full read of `app/models.py` for every column, constraint, and existing
`user_id` usage — not `\d+` against the live database, since the schema
in the models file is already the authoritative, migration-tracked
source (Alembic's `env.py` autogenerates against exactly this file).*

---

## Constraints

| Constraint | Today | Must become | Risk if unchanged |
|---|---|---|---|
| `transactions` — `UNIQUE (external_id)` | Global, added S4-01 specifically because `account_id` isn't stable across reconnects | `UNIQUE (user_id, external_id)` | **This is the single highest-risk item in this entire plan.** Enable Banking's `external_id` is unique *per bank*, not globally across all Enable Banking customers — two different real users of this app, both connecting a KBC account, could plausibly receive an overlapping `external_id` from Enable Banking's numbering (unverified whether Enable Banking guarantees global uniqueness across all its client apps; the safe assumption is that it does not). Left as a bare global `UNIQUE`, the *second* user's sync would either silently upsert into the *first* user's transaction row (via the existing `ON CONFLICT (external_id) DO UPDATE` in `crud.upsert_transactions`) or reject the insert — either way, one user's transaction data leaks into or blocks the other's. This is a direct repeat of the S4-01 incident class, just keyed on `user_id` instead of `account_id`. |
| `categories` — `PRIMARY KEY (name)` | Global | `PRIMARY KEY (user_id, name)` *if* categories go per-user (see Tables decision above) | If categories stay shared, no change needed. If they go per-user and this isn't updated, two users couldn't both have a category named "Groceries" — a near-certain collision on day one. |
| `budgets` — `UNIQUE NULLS NOT DISTINCT (user_id, category, period)` | **Already correct** — built this way in S4-05 specifically anticipating multi-user | Add `NOT NULL` to `user_id` once backfilled; the constraint shape itself needs no change | None — this is the one table already done right. |
| `settings` — `PRIMARY KEY (key)` | Global | `PRIMARY KEY (user_id, key)` *if* settings go per-user | If settings stay global, no change. If per-user and unchanged, one user's provider switch changes behavior for every user simultaneously — which is exactly today's (single-user-era) behavior, silently carried forward as a bug. |

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
| `transactions.py` | `POST /sync`, `GET ""`, `GET /search`, `PATCH /{id}` | All four need `user_id` threaded through: sync writes must tag new rows with the requesting user; the two GETs must filter by it; the PATCH must verify the target row belongs to the requester before editing (see IDOR note below). |
| `categories.py` | `GET ""`, `PATCH /{name}`, `POST ""`, `POST /{name}/reset` | Depends on the categories-per-user decision above. If per-user: all four need scoping. If shared: no change. |
| `settings.py` | `GET ""`, `PATCH ""`, `POST /test-connection` | Depends on the settings-per-user decision above. `test-connection` doesn't touch storage at all (it takes a key directly in the request body) — no change needed there regardless. |
| `budgets.py` | `GET ""`, `POST ""`, `PATCH /{category}`, `DELETE /{category}` | **Already done** — `crud.list_budgets_with_status`, `create_budget`, `update_budget_amount`, `delete_budget` all take `user_id` today; only the router's `CURRENT_USER_ID = None` placeholder needs to become a real value from the auth session. |
| `insights.py` | `GET ""`, `GET /compare` | Both need `user_id` filtering added to `crud.list_insights` (currently filters only by `date_from`/`date_to`). |
| `analysis.py` | `POST /categorize`, `POST /insights` | Both operate on whatever `crud.get_uncategorized_transactions`/`list_transactions` return — needs `user_id` threaded the same way as the transactions endpoints. |
| `chat.py` | `POST ""` | `chat_service.build_context` reads transactions/budgets/insights directly — needs `user_id` threaded through the whole context-assembly chain, not just the top-level router. |
| `jobs.py` | `GET /{job_id}` | **Authorization gap, not just scoping.** `job_store.get_job` has no ownership concept at all — any caller who knows a `job_id` (a random UUID, so not practically guessable, but still) can read another user's job status, including embedded insight text. Needs an ownership check, not just a filter (jobs aren't queried by user, they're looked up by ID — the fix is verifying the ID's owner matches the caller, which means the job payload must record who started it). |
| `auth.py` | `GET /status`, `POST /reauthorize`, `POST /callback` | All three currently talk to the single global `EnableBankingService`/`eb_session.json`. Needs the whole Enable Banking session layer to become per-user first (see Files on disk) — the endpoints themselves are thin wrappers and change trivially once that's done. |
| `statistics.py` | `GET ""` | Needs `user_id` filtering added to `crud.list_transactions`. |

**Endpoints that "return all rows unconditionally" today, flagged
explicitly per the ticket's ask:** `GET /api/transactions`, `GET
/api/transactions/search`, `GET /api/statistics`, `GET /api/insights`,
`GET /api/insights/compare`, `GET /api/categories`, `GET /api/settings` —
every one of these currently has zero `WHERE` clause on any user
dimension, because `crud.py` has no concept of one to filter on outside
the four budget functions.

*Verified via: `grep -n "@router\.\(get\|post\|patch\|delete\|put\)"
app/routers/*.py` for the complete endpoint list (25 matches), then
`grep -n "^def " app/crud.py` to confirm exactly which crud functions
accept a `user_id` parameter today (4, all budget-related), then a full
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
- **Nothing else found.** Searched every module-level assignment across
  `app/*.py`, `app/agents/**/*.py`, `app/tasks/*.py`, and `app/routers/
  *.py`; every other module-level name is either a pure constant
  (thresholds, model name strings, prompt templates), a `__all__` export
  list, or `db.py`'s `engine`/`SessionLocal` (a connection pool/session
  factory — the standard SQLAlchemy pattern, not per-user state; per-user
  scoping happens in the *queries* run through it, covered above).

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

Dependency-ordered sequence for Sprint 6:

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
3. **Decide categories and settings: per-user or shared** (see Tables).
   This is a product decision, not a technical one — get it confirmed
   before writing the migrations, since it changes which of the two
   tables get touched in steps 4–6 at all.
4. **Add nullable `user_id` columns** to `transactions`, `insights`, and
   (if the decision says so) `categories`/`settings`. Nullable first,
   deliberately — this is the same pattern `budgets` already used in
   S4-05, and it means the column can exist and be backfilled without a
   single blocking migration that locks a live table while assigning
   every row at once.
5. **Backfill every existing row** in every touched table to Borys's user
   id from step 2. Verify row counts before and after match exactly (no
   row should be silently dropped or duplicated by the backfill).
6. **Add `NOT NULL`** to each `user_id` column, in a separate migration
   from step 4, once step 5's backfill is verified complete. Running
   this before backfill finishes would fail outright (correctly) rather
   than silently corrupt data — but running it as part of the *same*
   migration as step 4 removes the verification window between "column
   added" and "column enforced," which is the whole point of splitting
   these two steps.
7. **Update constraints**: `transactions`'s `UNIQUE (external_id)` →
   `UNIQUE (user_id, external_id)` (the highest-risk item in this plan —
   see Constraints), and `categories`'s primary key if it goes per-user.
   Must happen *after* step 6, not before — a `UNIQUE (user_id,
   external_id)` constraint is meaningless (and in Postgres, actually
   still permits full duplicates) while `user_id` can be `NULL` on
   every row.
8. **Thread `user_id` through every `crud.py` function** that doesn't
   already take it, following the exact pattern `budgets`'s four
   functions already establish. Mechanical but touches nearly every
   function in the file — the two `CURRENT_USER_ID = None` placeholders
   already mark where the router-level wiring point is.
9. **Wire routers to the real authenticated user** — replace both
   `CURRENT_USER_ID = None` placeholders and add the equivalent
   plumbing to every other router listed under Endpoints, once Sprint
   6's auth middleware exists to source a real value from.
10. **Fix the two IDOR-shaped gaps**: add an ownership check to `GET
    /api/jobs/{job_id}` (requires recording who started each job in its
    Redis payload) and to `PATCH /api/transactions/{id}` (requires the
    fetch-before-update to filter on `user_id`, not just the row's own
    primary key).
11. **Fix `_provider_cache`** to key on `(user_id, provider_name)`.
12. **Redesign bank-session storage** off `eb_session.json` onto a
    per-user table, and **redesign the OAuth callback catcher** off its
    single-port/single-listener design — both are Sprint 6's "per-user
    bank sessions" and "public deployment with real HTTPS" scope
    already, listed here only to make the dependency explicit: nothing
    above technically blocks these two, but shipping multi-user without
    them means every user after the first still can't independently
    connect their own bank account.

**What breaks if this order is violated:** doing step 7 before step 6
(constraints before `NOT NULL`) produces a constraint that doesn't
actually protect anything, since `NULL <> NULL` in the columns it's
supposed to be distinguishing users by — the exact case S4-05 already
solved once for `budgets` with `NULLS NOT DISTINCT`, which only works
because `budgets.user_id` is *staying* nullable through Sprint 5; the
other tables are meant to end up `NOT NULL`, so they need the ordering
above instead of reusing that exact trick. Doing step 5 (backfill) before
step 2 (bootstrap user exists) has nothing to backfill *to* and either
fails or requires a throwaway placeholder id that then needs a second
backfill to correct. Doing step 9 (router wiring) before step 8 (crud
functions accept `user_id`) means the router has a real user id and
nowhere to pass it — the two have to land together or in that specific
order.

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
