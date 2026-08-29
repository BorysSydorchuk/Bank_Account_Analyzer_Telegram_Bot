Status: delivered

================================================================
TICKET S9-02 — Subscription Schema & User-Tier Model
================================================================

WHAT TO BUILD:
- A subscriptions table (or equivalent): user_id, stripe
  customer/subscription IDs, current tier, status (active,
  canceled, past_due, etc.), relevant dates
- Every user defaults to "free" tier with no Stripe objects
  until they actually subscribe
- Nullable/optional fields for users who never touch billing —
  don't force a Stripe customer to exist for every user
  up front
- This table DOES need a real user_id (not the app_settings
  exception from S9-01 — that table was correctly global;
  this one is inherently per-user data, standard multi-user
  rules apply in full)

ACCEPTANCE CRITERIA:
- Schema exists, migration applies cleanly (real evidence,
  same rigor as every prior migration this project has done)
- A user with no subscription history reads correctly as
  "free" tier
- No existing user/data disrupted by this addition
- Any deferred/non-blocking finding discovered during this
  ticket gets its own standalone docs/verification_debt.md
  entry immediately, not folded into prose — per the pattern
  flagged four times now (S8-05, S8-06, S8-08, S9-01)

WHEN DONE:
- Real migration evidence
- Confirm existing users unaffected
- Do not start S9-03 until confirmed

================================================================
WHEN DONE (2026-08-29)
================================================================

**Real migration evidence:** `subscriptions` table added via new
migration `59a0e1c55d1a` (`down_revision = 'a2b6e91d4f37'`, S9-01's
`app_settings` migration — the current head). Applied for real, twice:

1. Against the disposable test database, as part of the full backend
   suite (`test_db_engine` runs the real Alembic chain, not
   `Base.metadata.create_all()`):

       INFO  [alembic.runtime.migration] Running upgrade a2b6e91d4f37 -> 59a0e1c55d1a, add subscriptions table
       ...
       157 passed, 1 warning in 18.89s   (153 pre-existing + 4 new)

2. Against the real local dev database (5 real beta users, 412 real
   transactions), by restarting the `backend` container — its `CMD`
   runs `alembic upgrade` on startup:

       backend-1  | INFO  [alembic.runtime.migration] Running upgrade a2b6e91d4f37 -> 59a0e1c55d1a, add subscriptions table

   Schema confirmed via `\d subscriptions` against that real database:
   `user_id` UUID PK + FK → `users(id)`; `stripe_customer_id` /
   `stripe_subscription_id` both nullable and UNIQUE; `tier` NOT NULL
   default `'free'`, `CHECK (tier IN ('free', 'paid'))`; `status`
   nullable, no CHECK (see KEY DECISIONS); `current_period_end` /
   `canceled_at` / `created_at` / `updated_at` all nullable timestamps.

**Confirm existing users unaffected:** dev-database row counts taken
immediately before and after the real migration ran:

       before: users=5, transactions=412, alembic_version=a2b6e91d4f37
       after:  users=5, transactions=412, alembic_version=59a0e1c55d1a, subscriptions=0

   Zero rows were force-inserted into `subscriptions` for any existing
   user — the migration is purely additive (`CREATE TABLE` only, no
   `ALTER` on any existing table). Live-code confirmation, run against
   the real dev database via the running `backend` container, iterating
   every one of the 5 real users through the actual `crud.get_user_tier`
   function (not a hypothetical):

       e8cb5276-... free
       d82c2816-... free
       28fd049a-... free
       de240750-... free
       efa02e31-... free

   Every existing user reads as `"free"` with no Stripe objects, exactly
   as specified.

KEY DECISIONS

- `user_id` is the table's primary key, not a surrogate `id` → mirrors
  `enable_banking_sessions` (S7-06): this row tracks one user's
  *current* subscription state, not an append-only event log, so
  "one row per user" is the natural shape. Alternative: a surrogate PK
  with `user_id` as a plain (indexed, non-unique) column, allowing
  multiple historical rows per user — rejected because nothing in this
  sprint's scope needs subscription *history*, only current state; S9-03
  updates this row in place on every webhook rather than inserting a
  new one.
- No row at all (rather than a seeded `tier='free'` row per user) is how
  a free user is represented → matches the ticket's explicit
  instruction not to force a Stripe customer to exist up front, and
  keeps the table's row count meaningful (a row's mere existence tells
  you "this user has touched billing at least once"). Alternative:
  insert a `tier='free'` row for every user at signup — rejected as
  needless writes for the common case (beta is currently 100% free
  users) and it would obscure "has this user ever interacted with
  billing at all," which the on-cancellation history (see next bullet)
  actually wants to preserve.
- `status` is a free-text column with no CHECK constraint, unlike
  `tier` → Stripe's own subscription status vocabulary (`active`,
  `canceled`, `past_due`, `trialing`, `unpaid`, `incomplete`,
  `incomplete_expired`, `paused`, and it has grown over time) is not
  something this app owns or controls. Alternative: a CHECK enumerating
  today's known Stripe statuses — rejected because it would need a
  schema migration the moment Stripe adds or this app needs a status
  not yet listed, for no real safety benefit (this column is never used
  for a SQL-level invariant, only read back verbatim by S9-03/S9-04).
  `tier` gets the opposite treatment deliberately: it's *this app's* own
  fixed vocabulary (Sprint 9 plan: "simple two-tier ... not multiple
  paid tiers"), so a CHECK there costs nothing and catches a real bug
  class (a typo'd tier value silently granting/denying access).

WATCH OUT FOR

- `crud.get_user_tier` is the only sanctioned read path for tier — it's
  not yet called from anywhere except this ticket's own tests. S9-04 is
  what wires it into real enforcement; until then, tier is unread and
  therefore has zero observable effect on the running app, same
  inertness guarantee S9-01's kill switch already has.
- `stripe_customer_id`/`stripe_subscription_id` are both UNIQUE but
  neither has been validated against a real Stripe webhook payload yet
  (no webhook exists until S9-03) — the assumption that these ids are
  stable and never reused is standard, well-documented Stripe behavior
  (unlike Enable Banking's `account_id`, which burned this project once
  already), but "well-documented" isn't the same as "empirically
  confirmed on this integration." Given its own standalone
  `docs/verification_debt.md` entry rather than left as a comment here.

HOW IT CONNECTS

This is pure schema — no route, no webhook, no UI reads or writes this
table yet. It gives S9-03 (Stripe Checkout & webhooks) a real place to
write subscription state to, and gives S9-04 (tier-based gating) a real
`crud.get_user_tier` call to check before applying `usage_limits.py`'s
caps. Nothing in the currently-running app calls either new function, so
today's beta users are unaffected — confirmed above, not assumed.

One standalone `docs/verification_debt.md` entry added: "subscriptions
.stripe_customer_id/stripe_subscription_id uniqueness — vendor-documented,
not yet empirically exercised" (OPEN, closes when S9-03 processes its
first real webhook event). Everything else in this ticket was checked
against a real running database, not deferred.

Ready for S9-03 whenever you confirm this one.

Do not start S9-03 until confirmed.
