// Mirrors backend/app/schemas.py — kept hand-in-sync since there's no shared
// schema generation between the FastAPI and TypeScript sides yet.

export interface SyncResponse {
  fetched: number
  stored: number
  duplicates_skipped: number
}

export interface BiggestExpense {
  description: string | null
  amount: number
  date: string
}

export interface StatisticsSummary {
  total_spent: number
  total_received: number
  net: number
  transaction_count: number
  biggest_expense: BiggestExpense | null
}

export interface CategoryStat {
  category: string
  total: number
  count: number
  percentage: number
  // Empty until the LLM categorization sprint backfills transactions.subcategory.
  // Percentage here is the subcategory's share of its *parent* category's total.
  subcategories: CategoryStat[]
}

export interface DayStat {
  date: string
  spent: number
  received: number
}

export interface WeekStat {
  week: string
  date_range: string
  spent: number
  received: number
}

export interface StatisticsResponse {
  summary: StatisticsSummary
  by_category: CategoryStat[]
  by_day: DayStat[]
  by_week: WeekStat[]
}

export interface EnableBankingStatusResponse {
  status: "active" | "expired"
  expires_at: string | null
}

export interface ReauthorizeResponse {
  auth_url: string
}

export type LlmProvider = "gemini" | "claude"

export interface SettingsResponse {
  llm_provider: LlmProvider
  // Masked ("••••••••") if a key is saved, "" if not — never the real key.
  gemini_api_key: string
  anthropic_api_key: string
}

export interface PatchSettingsResponse {
  key: string
  value: string
}
