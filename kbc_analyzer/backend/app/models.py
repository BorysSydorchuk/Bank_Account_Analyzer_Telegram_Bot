"""SQLAlchemy models — schema for these lives in app/migrations/versions/ (Alembic)."""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    # Google-only and password-only accounts are both valid (S6-03/S6-04);
    # what's never valid is neither — a row with no way to ever authenticate
    # as it. Enforced here, not just in application code, so a bug in the
    # registration/OAuth-creation path can't silently write an unusable row.
    __table_args__ = (
        CheckConstraint(
            "password_hash IS NOT NULL OR google_id IS NOT NULL",
            name="users_has_auth_method",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text)
    google_id = Column(Text, unique=True)
    display_name = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    # Declared here too (not just in the migration) so `alembic revision
    # --autogenerate` diffs against the real constraints instead of proposing
    # to drop them, which happened once already (S2-03) before this was
    # added. external_id (S4-01) — Enable Banking's own transaction
    # reference is stable across reconnects, unlike account_id — but is not
    # globally unique (S6-02 Step 0, vendor-confirmed: see
    # docs/multi_user_migration_plan.md), hence scoped to (user_id,
    # external_id), not external_id alone, from Sprint 6 on. category's FK
    # is composite for the same reason as Budget.category below — see that
    # column's comment.
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_transactions_user_id_external_id"),
        ForeignKeyConstraint(
            ["user_id", "category"],
            ["categories.user_id", "categories.name"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # Sprint 6 (S6-02) — every row backfilled to the single bootstrap user at
    # migration time; NOT NULL from the start of this column's life (no
    # nullable-first period like Budget's original S4-05 addition, since
    # this migration backfills before adding the column's NOT NULL, all
    # within the same ticket — see the migration files for the exact
    # add-nullable -> backfill -> NOT NULL sequence actually run).
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id = Column(Text, nullable=False)
    external_id = Column(Text, nullable=False)
    booking_date = Column(Date)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, server_default="EUR")
    description = Column(Text)
    # No column-level ForeignKey here (unlike pre-S6-02) — category's FK is
    # composite (user_id, category) -> categories(user_id, name), declared
    # in __table_args__ above, since categories' primary key is now
    # composite too (Sprint 6: a category name is only unique per user).
    # subcategory has no FK — it's a free-text refinement, not itself a
    # first-class entity with a table.
    category = Column(Text)
    subcategory = Column(Text)
    # True once a human has set category/subcategory/description by hand
    # (S3-05) — the categorization agent's query excludes these rows even
    # when category is null again (a manual "clear" is still a decision, not
    # an absence of one), so a correction is never silently re-guessed.
    manually_edited = Column(Boolean, server_default="false")
    raw_data = Column(JSONB)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    # Simple key/value store — deliberately not one column per setting, so adding a
    # new setting later never needs a migration, just a new seeded row. Sprint 6
    # (S6-02): widened to a composite (user_id, key) primary key rather than a
    # separate user_settings table — a shared API key funds every other user's
    # LLM calls otherwise (a billing hole, PM ruling 2026-08-17), and widening
    # the existing key-value shape needed no redesign of encrypt-on-write
    # (crypto.py) — only the row identity changed, not what a row holds.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    # Sprint 6 (S6-02): composite (user_id, name) primary key, not name alone
    # — a personal color override (S3-06) is meaningless as a *shared*
    # override once a second user exists (PM ruling 2026-08-17). Categories
    # are still referenced by name within a user's own data (transactions.category
    # is a free-text column, matched via the composite FK on Transaction/Budget
    # above/below), so (user_id, name) is the natural key, not an invented
    # surrogate.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    name = Column(Text, primary_key=True)
    color = Column(Text, nullable=False)
    is_custom = Column(Boolean, server_default="false")
    # 'seed' (S3-01 static palette) | 'ai' (S3-02 color-assignment agent) |
    # 'user' (a manual override, S3-06). The AI color-assignment step only
    # ever touches rows still on 'seed' — 'ai' and 'user' rows are left alone.
    source = Column(Text, server_default="seed")
    # The last color the AI actually assigned, kept separately from `color` so
    # "Reset to AI" (S3-06) has something to restore to after a user override
    # — without this, overwriting `color` with a user's pick would lose the
    # AI's answer with no way back. Null for a category the AI never touched.
    ai_color = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Insight(Base):
    __tablename__ = "insights"
    # Declared here too (not just in the migration) for the same reason as
    # Transaction's UniqueConstraint — so autogenerate diffs against the real
    # index instead of proposing to drop it.
    __table_args__ = (Index("ix_insights_date_range", "date_from", "date_to"),)

    # Insights are cheap to regenerate (one LLM call) and only ever meaningful
    # for the exact date range they were generated against — a surrogate UUID,
    # not a natural key, since "date_from + date_to + type" isn't unique
    # across regenerations for the same range.
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # Sprint 6 (S6-02) — without this, two users syncing overlapping date
    # ranges would silently share insight rows (list_insights' query gains
    # the matching user_id filter in S6-06; this column alone doesn't
    # scope reads yet — see docs/multi_user_migration_plan.md's Endpoints
    # section). ix_insights_date_range is left as (date_from, date_to)
    # unchanged — widening it to include user_id is a query-scoping
    # concern for S6-06, not this ticket's schema work.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class EnableBankingSession(Base):
    __tablename__ = "enable_banking_sessions"

    # S7-06: replaces the single global eb_session.json file (never durable
    # across an ECS redeploy, never visible to the worker task at all —
    # see the S7-06 ticket file's premise check) with one row per user.
    # One connection per user, same real-world shape as before (a person
    # links one bank account to their Mymble account) — a composite key
    # for multiple simultaneous connections per user is a Sprint-later
    # concern (multi-bank), not this ticket's.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    # Fernet-encrypted (app/crypto.py, same pattern as Setting's API keys)
    # — this is bank-session credential material, not a value ever safe to
    # store in plaintext at rest.
    session_id_encrypted = Column(Text, nullable=False)
    # Fernet-encrypted JSON array of account UIDs — not itself as sensitive
    # as the session_id, but encrypted anyway for consistency: this whole
    # table is "Enable Banking session state," not a mix of secret and
    # non-secret columns a reader has to remember which is which.
    account_uids_encrypted = Column(Text, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Budget(Base):
    __tablename__ = "budgets"
    # Declared here too (not just in the migration), same reason as
    # Transaction's UniqueConstraint (S2-03): so autogenerate diffs against
    # the real constraint instead of proposing to drop it. NULLS NOT DISTINCT
    # is kept even though user_id is NOT NULL from Sprint 6 on (see below) —
    # harmless once NULLs can't occur, and left as-is rather than swapped for
    # a plain UNIQUE to minimize unrelated changes in this migration.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", "period",
            name="uq_budgets_user_category_period",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("amount > 0", name="ck_budgets_amount_positive"),
        ForeignKeyConstraint(
            ["user_id", "category"],
            ["categories.user_id", "categories.name"],
            onupdate="CASCADE",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # NULL through Sprint 5 (this table was built multi-user-ready at S4-05,
    # ahead of the rest of the schema). Sprint 6 (S6-02) backfills every row
    # to the bootstrap user and tightens to NOT NULL, same as every other
    # table's user_id column.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # No column-level ForeignKey here (unlike pre-S6-02) — category's FK is
    # composite (user_id, category) -> categories(user_id, name), declared
    # in __table_args__ above, since categories' primary key is now
    # composite (see Category).
    category = Column(Text, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    period = Column(Text, nullable=False, server_default="monthly")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
