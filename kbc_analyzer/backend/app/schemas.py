"""Pydantic request/response models for the transactions API."""
from datetime import date, datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    color: str
    is_custom: bool
    source: Literal["seed", "ai", "user"]
    # Present only once the AI has assigned this category a color at least
    # once — the frontend uses "is this null?" to decide whether "Reset to
    # AI" (S3-06) has anything to restore.
    ai_color: str | None = None


class PatchCategoryRequest(BaseModel):
    color: str


class CreateCategoryRequest(BaseModel):
    # S5-07: categories.name is a Text primary key with no DB-level length
    # bound — an unconstrained request field would let a client create an
    # arbitrarily large PK/index entry. 100 chars is generous for a
    # category name (the longest seed name, "Restaurants and Cafes", is 22).
    # No min_length here on purpose — the router's own "can't be empty"
    # check (after .strip()) already covers that case with a clear 400;
    # duplicating it as a Pydantic constraint would turn that same, common
    # user mistake into a generic 422 instead.
    name: str = Field(max_length=100)
    color: str


class SyncRequest(BaseModel):
    date_from: date
    date_to: date


class InsightItem(BaseModel):
    type: Literal["pattern", "anomaly", "saving", "rhythm", "category"]
    title: str
    body: str
    severity: Literal["info", "warning", "positive"]


class SyncResponse(BaseModel):
    # S4-02: the Enable Banking fetch itself moved into the Celery job along
    # with everything else (S3-04's categorization/insights) — this endpoint
    # now only ever creates the job and returns, so fetched/stored/
    # duplicates_skipped are no longer known synchronously. Those numbers are
    # surfaced instead through the job's own stage messages (see
    # tasks/analysis.py's "storing" stage) via GET /api/jobs/{job_id}.
    job_id: str
    status: Literal["processing"]


class JobProcessing(BaseModel):
    job_id: str
    status: Literal["processing"]
    stage: Literal["fetching", "storing", "categorizing", "generating_insights"]
    progress: int
    message: str


class JobComplete(BaseModel):
    job_id: str
    status: Literal["complete"]
    stage: Literal["done"]
    progress: int
    categorized: int
    insights: list[InsightItem]
    insights_provider: str | None = None
    insights_generated_at: datetime | None = None
    # Separate from a top-level job failure — categorization can succeed while
    # insight generation still fails independently (same split as the old
    # SyncResponse's error_message/insights_error_message pair).
    insights_error_message: str | None = None
    message: str


class JobFailed(BaseModel):
    job_id: str
    status: Literal["failed"]
    stage: str
    error: str


# Discriminated on `status` — GET /api/jobs/{job_id} returns whichever of the
# three shapes matches the job's current state in Redis.
JobStatusResponse = Annotated[Union[JobProcessing, JobComplete, JobFailed], Field(discriminator="status")]


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: str
    booking_date: date | None
    amount: float
    currency: str
    description: str | None
    category: str | None
    subcategory: str | None
    manually_edited: bool
    fetched_at: datetime


class PatchTransactionRequest(BaseModel):
    # All optional and no default sentinel needed beyond None — the router
    # reads body.model_dump(exclude_unset=True) to tell "field omitted" from
    # "field explicitly sent as null", since PATCH semantics (S3-05's own
    # example body sends "subcategory": null to clear it) depend on that
    # distinction.
    category: str | None = None
    subcategory: str | None = None
    description: str | None = None


class TransactionsListResponse(BaseModel):
    transactions: list[TransactionOut]
    total: int
    page: int
    pages: int


class BiggestExpense(BaseModel):
    description: str | None
    amount: float
    date: date


class Summary(BaseModel):
    total_spent: float
    total_received: float
    net: float
    transaction_count: int
    biggest_expense: BiggestExpense | None


class CategoryStat(BaseModel):
    category: str
    total: float
    count: int
    percentage: float
    # Populated from transactions.subcategory; empty until the LLM
    # categorization sprint backfills that column. Percentage here is each
    # subcategory's share of its *parent* category's total, not the grand total.
    subcategories: list["CategoryStat"] = []


class DayStat(BaseModel):
    date: date
    spent: float
    received: float


class WeekStat(BaseModel):
    week: str
    date_range: str
    spent: float
    received: float


class StatisticsResponse(BaseModel):
    summary: Summary
    by_category: list[CategoryStat]
    by_day: list[DayStat]
    by_week: list[WeekStat]


class EnableBankingStatus(BaseModel):
    # S7-07: "not_connected" (no session has ever existed for this user)
    # is distinct from "expired" (one existed, then lapsed) — the two
    # need different copy in the frontend ("Connect your bank" vs
    # "Reconnect").
    status: Literal["active", "expired", "not_connected"]
    expires_at: datetime | None


class ReauthorizeResponse(BaseModel):
    auth_url: str


class CallbackRequest(BaseModel):
    code: str
    # Accepted (the redirect URL always carries it) but not currently validated —
    # matches start_auth()'s own comment: required by the PSD2 spec, not checked by us.
    state: str | None = None


class SettingsResponse(BaseModel):
    llm_provider: Literal["gemini", "claude"]
    # Masked, never the decrypted key — see settings_service.mask_key(). "" means unset.
    gemini_api_key: str
    anthropic_api_key: str


class PatchSettingsRequest(BaseModel):
    key: Literal["llm_provider", "gemini_api_key", "anthropic_api_key"]
    value: str


class PatchSettingsResponse(BaseModel):
    key: str
    value: str


class TestConnectionRequest(BaseModel):
    provider: Literal["gemini", "claude"]
    # The key currently typed in the form, not necessarily saved yet (S3-07
    # Item 1) — test and save are independent actions, so this can't just
    # read the stored key back out.
    api_key: str


class TestConnectionResponse(BaseModel):
    connected: bool
    error_message: str | None = None


class CategorizeRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None


class CategorizeResponse(BaseModel):
    categorized: int
    skipped_already_categorized: int
    failed: int
    provider: str
    error_message: str | None = None


class InsightsRequest(BaseModel):
    date_from: date
    date_to: date


class InsightsResponse(BaseModel):
    insights: list[InsightItem]
    provider: str
    generated_at: datetime
    error_message: str | None = None


class CachedInsightsResponse(BaseModel):
    """GET /api/insights (S3-07 Item 3) — unlike InsightsResponse (a fresh
    generation that always has a provider and timestamp), a date range with
    no sync yet has never had insights generated for it at all.
    """
    insights: list[InsightItem]
    provider: str | None = None
    generated_at: datetime | None = None


class PeriodComparison(BaseModel):
    """One side of GET /api/insights/compare's response (S4-08). total_spent
    and by_category are always computed live from transactions; insights
    are read from storage exactly as stored for this exact range (S4-04
    Option B) — empty if this range was never synced with insight
    generation, never generated here on the fly.
    """
    date_range: str
    total_spent: float
    by_category: list[CategoryStat]
    insights: list[InsightItem]
    # Every row in one batch shares the same timestamp (crud.replace_insights
    # writes them together), so one label per period is enough — None when
    # `insights` is empty, matching CachedInsightsResponse's convention.
    insights_generated_at: datetime | None = None


class CategoryChange(BaseModel):
    category: str
    period_a: float
    period_b: float
    change: float
    # None when period_a's total for this category was 0 — percentage
    # change from zero is undefined, not "infinite%" or silently 0%.
    change_pct: float | None


class ComparisonDelta(BaseModel):
    total_spent_change: float
    total_spent_change_pct: float | None
    # Sorted by absolute change descending (biggest movers first, either
    # direction) — not alphabetical, not by period_b total; a category swing
    # is what the comparison view exists to surface.
    category_changes: list[CategoryChange]


class ComparisonResponse(BaseModel):
    period_a: PeriodComparison
    period_b: PeriodComparison
    delta: ComparisonDelta


class BudgetOut(BaseModel):
    # Not from_attributes=True: this is assembled in crud.py by joining a
    # Budget row against this-calendar-month spending, not read straight off
    # the ORM model — spent_this_month/percentage_used/status don't exist as
    # columns.
    category: str
    amount: float
    period: str
    spent_this_month: float
    percentage_used: float
    status: Literal["on_track", "warning", "exceeded"]


class CreateBudgetRequest(BaseModel):
    category: str
    amount: float


class PatchBudgetRequest(BaseModel):
    amount: float


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    # S5-07: capped for the same cost reason as ChatRequest.message below —
    # this is echoed straight into the next request's prompt as history.
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    # history is entirely client-held (S4-06) — the backend is stateless
    # across turns and never persists a conversation.
    #
    # S5-07: message and history were both previously unconstrained — every
    # chat request is a real, billed LLM call (Item 3's rate limiting caps
    # *how often*; these caps bound *how much* each call can cost). No
    # min_length on message: the router checks for empty/whitespace-only
    # with its own clear 400, the same pattern as category name, rather
    # than letting Pydantic turn that common case into a generic 422.
    # history capped at 50 turns — generous for a real conversation, a real
    # bound against a client fabricating an enormous history to inflate
    # every subsequent call's token cost.
    message: str = Field(max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)


class RegisterRequest(BaseModel):
    # EmailStr rejects the common typo/garbage case (no "@", no domain)
    # before it ever reaches crud — password strength is validated
    # separately in the router (app/auth/password.validate_password_strength),
    # not here, so a weak password gets that function's specific message
    # rather than a generic Pydantic 422.
    email: EmailStr
    password: str = Field(max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class SetPasswordRequest(BaseModel):
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
