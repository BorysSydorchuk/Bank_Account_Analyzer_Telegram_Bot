"""Pydantic request/response models for the transactions API."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncRequest(BaseModel):
    date_from: date
    date_to: date


class SyncResponse(BaseModel):
    fetched: int
    stored: int
    duplicates_skipped: int


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
