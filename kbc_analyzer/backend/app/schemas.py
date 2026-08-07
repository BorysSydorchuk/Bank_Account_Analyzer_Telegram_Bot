"""Pydantic request/response models for the transactions API."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    color: str
    is_custom: bool


class SyncRequest(BaseModel):
    date_from: date
    date_to: date


class InsightItem(BaseModel):
    type: Literal["pattern", "anomaly", "saving", "rhythm", "category"]
    title: str
    body: str
    severity: Literal["info", "warning", "positive"]


class SyncResponse(BaseModel):
    fetched: int
    stored: int
    duplicates_skipped: int
    categorized: int
    categorization_provider: str | None = None
    # Present only when categorization couldn't run at all (e.g. no API key
    # configured yet) — sync itself still succeeds either way.
    error_message: str | None = None
    # Insights are never persisted (S2-06) — generated fresh on every sync and
    # handed back here; the frontend caches them client-side under the same
    # date range as the statistics they were generated from.
    insights: list[InsightItem] = []
    insights_generated_at: datetime | None = None
    # Separate from `error_message` above — categorization and insight
    # generation can fail independently of each other.
    insights_error_message: str | None = None


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
    fetched_at: datetime


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
    status: Literal["active", "expired"]
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
