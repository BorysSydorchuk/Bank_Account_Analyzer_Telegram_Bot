"""Database read/write helpers for transactions — the Postgres-backed replacement for
kbc_analyzer.cache for anything reachable through the API.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .agents.categorization import CATEGORIES
from .colors import BACKUP_PALETTE
from .models import AppSetting, BetaInvite, Budget, Category, Insight, Setting, Subscription, Transaction, User


def get_user_by_google_id(db: Session, google_id: str) -> User | None:
    """The user a Google sign-in resolves to on a returning visit, or None
    on a Google identity never seen before (routers/user_auth.py then
    falls back to get_user_by_email for the account-linking case)."""
    return db.execute(select(User).where(User.google_id == google_id)).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Looks up a user by email — used by the Google sign-in flow to
    detect the account-linking case (a password-registered account
    signing in via Google for the first time), and by S6-04's
    register/login endpoints to check whether an email is already taken."""
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_unused_beta_invite_by_email(db: Session, email: str) -> BetaInvite | None:
    """S8-06. Looks up an unused invite by email, lowercased on the way in
    so this table doesn't inherit users.email's case-sensitivity gap
    (flagged separately, docs/verification_debt.md). Both registration
    paths (password and Google) call this before creating a new account —
    an already-used invite (used_at is not None) never matches again, so
    one invite grants exactly one account."""
    return db.execute(
        select(BetaInvite).where(BetaInvite.email == email.lower(), BetaInvite.used_at.is_(None))
    ).scalar_one_or_none()


def create_beta_invite(db: Session, email: str) -> BetaInvite:
    """S8-06. The one write backend/ops/grant_beta_invite.py performs — Borys's
    entire operating surface for granting beta access. Raises on a
    duplicate email via the table's own unique constraint rather than
    checking first, so a second grant attempt for the same address fails
    loudly instead of silently creating a second row."""
    invite = BetaInvite(email=email.lower())
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def mark_beta_invite_used(db: Session, invite: BetaInvite, user: User) -> BetaInvite:
    """S8-06. Called once, immediately after the account an invite gates
    is actually created — never before, so a registration that fails
    partway through (e.g. password-strength rejection) never burns the
    invite."""
    invite.used_at = func.now()
    invite.used_by_user_id = user.id
    db.commit()
    db.refresh(invite)
    return invite


def create_user_from_google(db: Session, google_id: str, email: str, display_name: str | None) -> User:
    """A brand-new account created by a first Google sign-in — no
    password_hash, google_id-only (satisfies users_has_auth_method).
    email_verified=True (S7-09): Google's own OAuth flow already proves
    ownership of this email address, so there's nothing this app's own
    verification email would add — sending one anyway would just be
    friction with no security benefit."""
    user = User(google_id=google_id, email=email, display_name=display_name, email_verified=True)
    db.add(user)
    db.flush()  # populates user.id (server-generated) without ending the transaction
    seed_default_categories(db, user.id)
    db.commit()
    db.refresh(user)
    return user


class GoogleIdConflictError(Exception):
    """link_google_id (S7-09, Sprint 6 Security Auditor Finding A) refused
    to attach google_id — either the target account already has a
    different one, or this google_id already belongs to someone else."""


def link_google_id(db: Session, user: User, google_id: str) -> User:
    """Attaches a Google identity to an existing (password-registered)
    account. As of S6-07 finding 1, the only caller is the explicit,
    authenticated GET /api/auth/google/link flow — never a bare Google
    sign-in callback matching on email alone, which was the account-
    takeover path that finding closed.

    S7-09 (Sprint 6 Security Auditor Finding A): these two checks used to
    live only in routers/user_auth.py's google_callback, which happened
    to be this function's only caller — nothing stopped a future second
    caller from skipping them and silently overwriting a google_id or
    stealing one already claimed elsewhere. Enforced here now, so the
    invariant holds regardless of who calls this.
    """
    if user.google_id is not None and user.google_id != google_id:
        raise GoogleIdConflictError(
            f"User {user.id} already has a different google_id linked; refusing to overwrite it."
        )
    already_linked_elsewhere = get_user_by_google_id(db, google_id)
    if already_linked_elsewhere is not None and already_linked_elsewhere.id != user.id:
        raise GoogleIdConflictError(f"google_id {google_id!r} is already linked to a different account.")

    user.google_id = google_id
    db.commit()
    db.refresh(user)
    return user


def create_user_from_password(db: Session, email: str, password_hash: str) -> User:
    """A brand-new account created by /api/auth/register (S6-04) — no
    google_id, password_hash-only (satisfies users_has_auth_method).
    email_verified defaults to False (the column's server_default) —
    unlike a Google signup, nothing has proven this email address yet;
    S7-09's verification email is what closes that gap."""
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.flush()  # populates user.id (server-generated) without ending the transaction
    seed_default_categories(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def verify_user_email(db: Session, user: User) -> User:
    """Marks user's email verified — the one write
    POST /api/auth/verify-email (S7-09) performs after consuming a real
    token from auth/tokens.py. Idempotent: setting it True again on an
    already-verified account is harmless, so no existence/state check is
    needed here."""
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, password_hash: str) -> User:
    """Sets (or replaces) a user's password — /api/auth/set-password
    (S6-04), the authenticated path that gives a Google-only account a
    real, usable password for the first time. Not exposed to an
    unauthenticated caller by any route: routers/user_auth.py's
    set_password endpoint requires get_current_user first, so this always
    runs against the caller's own account, never an arbitrary one."""
    user.password_hash = password_hash
    db.commit()
    db.refresh(user)
    return user


def upsert_transactions(db: Session, user_id: UUID, account_id: str, txs: list[dict]) -> tuple[int, int]:
    """Upsert normalized transactions for one account, scoped to user_id
    (S6-06 — the ON CONFLICT clause was already shaped for this at S6-02;
    this is the ticket that actually threads a real value through it).

    Returns (stored, duplicates_skipped). Enable Banking's own transaction reference
    (entry_reference, exposed as `id` on the normalized dict) is the natural key —
    checked per-user by (user_id, external_id) (S6-02 Step 0: not globally unique),
    not scoped to account_id, since Enable Banking issues a new account_id on every
    reconnect but external_id stays the same for the same real transaction.
    account_id is still stored (first-seen value, never overwritten on conflict)
    but no longer part of how a duplicate is recognized.
    """
    if not txs:
        return 0, 0

    external_ids = [t["id"] for t in txs]
    existing = set(
        db.execute(
            select(Transaction.external_id).where(
                Transaction.user_id == user_id, Transaction.external_id.in_(external_ids)
            )
        ).scalars()
    )

    for t in txs:
        stmt = pg_insert(Transaction).values(
            user_id=user_id,
            account_id=account_id,
            external_id=t["id"],
            booking_date=date.fromisoformat(t["date"]) if t.get("date") else None,
            amount=Decimal(str(t["amount"])),
            description=t["description"],
            raw_data=t,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Transaction.user_id, Transaction.external_id],
            set_={
                "booking_date": stmt.excluded.booking_date,
                "amount": stmt.excluded.amount,
                "description": stmt.excluded.description,
                "raw_data": stmt.excluded.raw_data,
            },
        )
        db.execute(stmt)

    db.commit()

    duplicates_skipped = len(existing)
    stored = len(txs) - duplicates_skipped
    return stored, duplicates_skipped


def list_transactions(db: Session, user_id: UUID, date_from: date, date_to: date) -> list[Transaction]:
    return list(
        db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.booking_date >= date_from,
                Transaction.booking_date <= date_to,
            )
            .order_by(Transaction.booking_date)
        ).scalars()
    )


def get_recent_transactions(db: Session, user_id: UUID, limit: int) -> list[Transaction]:
    """Newest-first transactions, unbounded by any date range (S4-06) — used
    to ground the AI chat assistant's context in specific recent activity."""
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.booking_date.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def get_transaction_date_range(db: Session, user_id: UUID) -> tuple[date, date] | None:
    """Earliest and latest booking_date across this user's stored
    transactions, or None if nothing has been synced yet (S4-06 chat
    context)."""
    earliest, latest = db.execute(
        select(func.min(Transaction.booking_date), func.max(Transaction.booking_date)).where(
            Transaction.user_id == user_id
        )
    ).one()
    if earliest is None:
        return None
    return earliest, latest


def search_transactions(db: Session, user_id: UUID, query: str, limit: int) -> list[Transaction]:
    """Global search (S3-07 Item 4) — across every transaction this user has
    ever synced, not scoped to any date range or the current page. Distinct
    from the Transactions page's own date-scoped, paginated list above."""
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.description.ilike(f"%{query}%"))
        .order_by(Transaction.booking_date.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def list_transactions_paginated(
    db: Session,
    user_id: UUID,
    date_from: date,
    date_to: date,
    page: int,
    limit: int,
    categories: list[str] | None = None,
    amount_type: str = "all",
) -> tuple[list[Transaction], int]:
    """Newest-first, paginated — for the Transactions page (S2-07). Distinct from
    list_transactions() above, which stays unpaginated/chronological for
    statistics and insight generation, which need every row in date order.

    category/amount_type filters happen here (not client-side) so pagination
    stays correct — "page 2 of Groceries" has to mean the database's second
    page of Groceries rows, not the second page of everything with any
    non-Groceries rows stripped out afterwards.
    """
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.booking_date >= date_from,
        Transaction.booking_date <= date_to,
    )
    if categories:
        stmt = stmt.where(Transaction.category.in_(categories))
    if amount_type == "spent":
        stmt = stmt.where(Transaction.amount < 0)
    elif amount_type == "received":
        stmt = stmt.where(Transaction.amount > 0)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = list(
        db.execute(
            stmt.order_by(Transaction.booking_date.desc(), Transaction.id.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        ).scalars()
    )
    return rows, total


def get_uncategorized_transactions(
    db: Session, user_id: UUID, date_from: date | None = None, date_to: date | None = None
) -> list[Transaction]:
    # manually_edited excludes a row even if its category is null — a user
    # clearing a category by hand (S3-05) is still a decision, not something
    # for the next categorize run to silently fill back in.
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.category.is_(None),
        Transaction.manually_edited.is_(False),
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    return list(db.execute(stmt).scalars())


def count_categorized_transactions(
    db: Session, user_id: UUID, date_from: date | None = None, date_to: date | None = None
) -> int:
    stmt = (
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.user_id == user_id, Transaction.category.is_not(None))
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    return db.execute(stmt).scalar_one()


def update_transaction_categories(db: Session, user_id: UUID, updates: list[dict]) -> None:
    """updates: [{"id": "<uuid str>", "category": "...", "subcategory": "..."|None}].

    The WHERE clause re-checks category IS NULL AND manually_edited IS FALSE
    rather than trusting that the rows passed in are still eligible — never
    overwrites a category a manual edit (S3-05) or a concurrent categorize
    run already set. user_id is a defense-in-depth check, not the only
    guard — the ids passed in already came from get_uncategorized_transactions
    (S6-06), itself scoped to this same user_id, so this can't reach another
    user's row in practice; scoped again here anyway, since a WHERE clause
    that doesn't have to trust its caller's own scoping is worth the one
    extra condition.
    """
    for u in updates:
        db.execute(
            update(Transaction)
            .where(
                Transaction.id == u["id"],
                Transaction.user_id == user_id,
                Transaction.category.is_(None),
                Transaction.manually_edited.is_(False),
            )
            .values(category=u["category"], subcategory=u.get("subcategory"))
        )
    db.commit()


def update_transaction(db: Session, user_id: UUID, transaction_id: UUID, updates: dict) -> Transaction | None:
    """updates: a dict of already-validated column/value pairs (category,
    subcategory, description — whichever were actually present in the PATCH
    body). Always stamps manually_edited = True, even if none of the
    provided values differ from what's already stored — the point is
    recording that a human looked at this row, not just changing its data.

    S6-06 — the IDOR-shaped gap S5-01 named explicitly: a plain
    `db.get(Transaction, transaction_id)` would find (and let the caller
    edit) any user's transaction, since a surrogate UUID alone doesn't
    exclude anyone. Scoped by user_id here instead of a separate ownership
    check, so a transaction that exists but belongs to someone else reads
    identically to one that doesn't exist at all — routers/transactions.py
    turns None into 404, never 403, either way.
    """
    transaction = db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    ).scalar_one_or_none()
    if transaction is None:
        return None
    for field, value in updates.items():
        setattr(transaction, field, value)
    transaction.manually_edited = True
    db.commit()
    db.refresh(transaction)
    return transaction


def list_categories(db: Session, user_id: UUID) -> list[Category]:
    """This user's categories, ordered by name. S6-07 finding 2 (S6-06
    review): user_id used to be optional (default None = unscoped) "for
    the rare internal caller that genuinely needs every user's rows" —
    an unscoped-by-default footgun sitting in a function every real route
    calls scoped. Required now; list_all_categories() below is the
    explicit, differently-named escape hatch for the one caller
    (scripts/smoke_test_color_validation.py) that actually needs every
    user's rows, so reaching for the unscoped behavior is a deliberate,
    visible choice at the call site, not a default anyone could reach by
    forgetting an argument.
    """
    return list(db.execute(select(Category).where(Category.user_id == user_id).order_by(Category.name)).scalars())


def list_all_categories(db: Session) -> list[Category]:
    """Every category, every user, unscoped — for internal/dev tooling
    only (scripts/smoke_test_color_validation.py), never a router. Not a
    default any live endpoint could accidentally fall back to."""
    return list(db.execute(select(Category).order_by(Category.name)).scalars())


def seed_default_categories(db: Session, user_id: UUID) -> None:
    """Adds user_id's initial `categories` rows to the session — does NOT
    commit. Callers (create_user_from_password/create_user_from_google)
    add these to the same session as the new User row and commit once,
    so a new account and its default categories are created atomically:
    either both land or neither does, never a user with no categories.

    S8-09: found post-S8-08 that nothing had ever done this for a
    multi-user account — the original fbde2dbcc78d migration seeded 7
    global rows once, before per-user categories (S6-02) existed, and
    every account created since then got zero. `agents.categorization
    .CATEGORIES` is the exact fixed list the categorization agent is
    told to classify into — reusing it here (not a separately
    maintained list) is what guarantees a fresh account's category
    table can actually accept what the LLM sends back. Colors come from
    colors.BACKUP_PALETTE, not the original migration's own hex values
    — those predate colors.validate_color() and fail it outright (found
    while building this fix); BACKUP_PALETTE's 8 entries were built
    specifically to pass validation, and 7 of them cover this list with
    one to spare.
    """
    for name, color in zip(CATEGORIES, BACKUP_PALETTE):
        db.add(Category(user_id=user_id, name=name, color=color, is_custom=False, source="seed"))


def list_seeded_category_names(db: Session, user_id: UUID) -> list[str]:
    """Category names still on their S3-01 seed color — the set eligible for
    S3-02's AI color assignment. 'ai' and 'user' rows are excluded."""
    return list(
        db.execute(
            select(Category.name).where(Category.user_id == user_id, Category.source == "seed")
        ).scalars()
    )


def get_categories_by_name(db: Session, user_id: UUID, names: list[str]) -> dict[str, Category]:
    """Existing rows for the given names (this user's only), keyed by name.
    Used by the AI color step to read a category's own seed color as its
    fallback if the LLM's color fails validation."""
    if not names:
        return {}
    rows = db.execute(
        select(Category).where(Category.user_id == user_id, Category.name.in_(names))
    ).scalars()
    return {row.name: row for row in rows}


def upsert_category_colors(db: Session, user_id: UUID, colors_by_name: dict[str, str], source: str) -> None:
    """The AI color-assignment path (S3-02) — always called with source='ai'.
    Never overwrites a row whose existing source is 'user' — user color
    choices are final. Also mirrors the color into ai_color, so a later user
    override (S3-06) has something concrete to "Reset to AI" back to."""
    for name, color in colors_by_name.items():
        stmt = pg_insert(Category).values(user_id=user_id, name=name, color=color, source=source, ai_color=color)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Category.user_id, Category.name],
            set_={"color": stmt.excluded.color, "source": stmt.excluded.source, "ai_color": stmt.excluded.ai_color},
            where=Category.source != "user",
        )
        db.execute(stmt)
    db.commit()


def set_category_color(db: Session, user_id: UUID, name: str, color: str) -> Category | None:
    """A user-initiated color change (PATCH /api/categories/{name}, S3-06).
    Unlike upsert_category_colors' AI path, this always applies — a user
    editing their own category again is not the same case as the AI trying
    to silently overwrite a user's existing choice. Leaves ai_color alone,
    so "Reset to AI" still has the original AI answer to go back to.

    S6-06: db.get() against a composite primary key takes the full key
    tuple — a bare `name` is what caused this to raise InvalidRequestError
    outright since S6-02's categories PK became (user_id, name) (tracked
    in that ticket's failing-test list). Fixed here, and doubles as the
    scoping fix: a name that exists but belongs to another user now reads
    identically to a name that doesn't exist, same 404 either way.
    """
    category = db.get(Category, (user_id, name))
    if category is None:
        return None
    category.color = color
    category.source = "user"
    db.commit()
    db.refresh(category)
    return category


def reset_category_to_ai(db: Session, user_id: UUID, name: str) -> Category | None:
    """Restores a category's AI-assigned color after a user override.
    Returns None if the category doesn't exist for this user, or if it has
    no ai_color to reset to (never AI-colored in the first place) — both
    cases the router treats as "nothing to reset." Same composite-key fix
    as set_category_color."""
    category = db.get(Category, (user_id, name))
    if category is None or category.ai_color is None:
        return None
    category.color = category.ai_color
    category.source = "ai"
    db.commit()
    db.refresh(category)
    return category


def create_category(db: Session, user_id: UUID, name: str, color: str) -> Category:
    """A brand-new, user-defined category (S3-06) — always is_custom=True,
    source='user'. No ai_color, since the AI never assigned one."""
    category = Category(user_id=user_id, name=name, color=color, is_custom=True, source="user")
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def replace_insights(
    db: Session,
    user_id: UUID,
    date_from: date,
    date_to: date,
    insights: list[dict],
    provider: str,
    generated_at: datetime,
) -> None:
    """Swaps out all insights for one date range in a single transaction —
    never accumulates history, since an insight is only ever meaningful as
    "the current read on this range" (S3-07 Item 3). Deleting first means a
    sync that produces zero insights (e.g. every category empty) correctly
    leaves the range with none, rather than stale ones from the last sync
    that did.

    This delete-and-replace behavior is a deliberate decision (S4-04), not
    an oversight: the period-comparison feature (S4-08) never depends on
    insight history to be correct, because its numeric core (totals,
    category deltas) is always computed live from `transactions`. Stored
    insights are shown only as supplementary context, labeled with
    `generated_at` so the UI is honest that a re-sync of one period doesn't
    regenerate the other. If a future sprint needs true insight history
    (e.g. "how did this month's read change across regenerations"), that's
    a new column (`generation_number`) and a "latest per range" query, not
    a change to this function's contract.
    """
    db.execute(
        delete(Insight).where(
            Insight.user_id == user_id, Insight.date_from == date_from, Insight.date_to == date_to
        )
    )
    for item in insights:
        db.add(
            Insight(
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
                type=item["type"],
                title=item["title"],
                body=item["body"],
                severity=item["severity"],
                provider=provider,
                generated_at=generated_at,
            )
        )
    db.commit()


def list_insights(db: Session, user_id: UUID, date_from: date, date_to: date) -> list[Insight]:
    return list(
        db.execute(
            select(Insight)
            .where(Insight.user_id == user_id, Insight.date_from == date_from, Insight.date_to == date_to)
            .order_by(Insight.generated_at)
        ).scalars()
    )


def get_budget(db: Session, user_id: UUID, category: str, period: str = "monthly") -> Budget | None:
    return db.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.category == category, Budget.period == period)
    ).scalar_one_or_none()


def create_budget(db: Session, user_id: UUID, category: str, amount: Decimal, period: str = "monthly") -> Budget:
    """A new monthly spending limit for one category (S4-05). Caller checks
    for an existing budget first — this always inserts."""
    budget = Budget(user_id=user_id, category=category, amount=amount, period=period)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def update_budget_amount(
    db: Session, user_id: UUID, category: str, amount: Decimal, period: str = "monthly"
) -> Budget | None:
    budget = get_budget(db, user_id, category, period)
    if budget is None:
        return None
    budget.amount = amount
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, user_id: UUID, category: str, period: str = "monthly") -> bool:
    budget = get_budget(db, user_id, category, period)
    if budget is None:
        return False
    db.delete(budget)
    db.commit()
    return True


def _spent_this_month_by_category(db: Session, user_id: UUID, categories: list[str]) -> dict[str, Decimal]:
    """Total spend (positive magnitude) per category, calendar-month-to-date,
    for this user only — unscoped here would silently blend every user's
    spending under a shared category name into everyone's budget "spent"
    figure. Same amount<0 / -amount sign convention as statistics.py, so a
    budget's "spent" figure always agrees with the rest of the dashboard."""
    if not categories:
        return {}
    today = date.today()
    month_start = today.replace(day=1)
    rows = db.execute(
        select(Transaction.category, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.category.in_(categories),
            Transaction.amount < 0,
            Transaction.booking_date >= month_start,
            Transaction.booking_date <= today,
        )
        .group_by(Transaction.category)
    ).all()
    return {category: -total for category, total in rows}


BUDGET_WARNING_THRESHOLD = 80.0


def list_budgets_with_status(db: Session, user_id: UUID) -> list[dict]:
    """Every budget for this user, joined against this-calendar-month spending.
    spent_this_month is always the calendar month of today (day 1 through
    today) regardless of a budget's own `period` value — 'monthly' is the
    only period this sprint supports, so today's calendar month is what
    "this month" already means everywhere else in the app (statistics.py's
    "This month" preset). A rolling 30-day window would drift out of sync
    with that and reset on no predictable date, which is harder to reason
    about for a limit a person is tracking against a bill cycle.
    """
    budgets = list(
        db.execute(select(Budget).where(Budget.user_id == user_id).order_by(Budget.category)).scalars()
    )
    if not budgets:
        return []

    spent_by_category = _spent_this_month_by_category(db, user_id, [b.category for b in budgets])

    result = []
    for budget in budgets:
        spent = spent_by_category.get(budget.category, Decimal("0"))
        percentage_used = float(spent / budget.amount * 100)
        if percentage_used > 100:
            status = "exceeded"
        elif percentage_used >= BUDGET_WARNING_THRESHOLD:
            status = "warning"
        else:
            status = "on_track"
        result.append(
            {
                "category": budget.category,
                "amount": float(budget.amount),
                "period": budget.period,
                "spent_this_month": float(spent),
                "percentage_used": round(percentage_used, 1),
                "status": status,
            }
        )
    return result


def get_all_settings(db: Session, user_id: UUID) -> dict[str, str]:
    rows = db.execute(select(Setting).where(Setting.user_id == user_id)).scalars()
    return {row.key: row.value for row in rows}


def upsert_setting(db: Session, user_id: UUID, key: str, value: str) -> None:
    stmt = pg_insert(Setting).values(user_id=user_id, key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Setting.user_id, Setting.key],
        set_={"value": stmt.excluded.value},
    )
    db.execute(stmt)
    db.commit()


def get_app_setting(db: Session, key: str, default: str) -> str:
    """Read one global (not per-user) app_settings value, or `default` if the row doesn't exist yet."""
    row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    return row.value if row is not None else default


def set_app_setting(db: Session, key: str, value: str) -> None:
    """Upsert one global app_settings row (e.g. flipping the S9-01 billing kill switch)."""
    stmt = pg_insert(AppSetting).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=[AppSetting.key],
        set_={"value": stmt.excluded.value},
    )
    db.execute(stmt)
    db.commit()


def get_subscription(db: Session, user_id: UUID) -> Subscription | None:
    """The user's subscription row, or None if they've never touched checkout
    (S9-02) — the normal state for every free user. Use get_user_tier for
    the free/paid decision itself; this is for callers that need the
    Stripe ids/status/dates too (S9-03's webhook handler, a future billing
    settings page)."""
    return db.execute(select(Subscription).where(Subscription.user_id == user_id)).scalar_one_or_none()


def get_user_tier(db: Session, user_id: UUID) -> str:
    """"free" or "paid". A user with no subscriptions row at all reads as
    "free" — Stripe objects are only ever created once a user actually
    starts checkout (S9-03), never up front."""
    subscription = get_subscription(db, user_id)
    return subscription.tier if subscription is not None else "free"
