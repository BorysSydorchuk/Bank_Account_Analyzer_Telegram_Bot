// Mirrors backend/app/schemas.py — kept hand-in-sync since there's no shared
// schema generation between the FastAPI and TypeScript sides yet.

export type InsightType = "pattern" | "anomaly" | "saving" | "rhythm" | "category"
export type InsightSeverity = "info" | "warning" | "positive"

export interface InsightItem {
  type: InsightType
  title: string
  body: string
  severity: InsightSeverity
}

export interface SyncResponse {
  // S3-04: sync is now just fetch + store — categorization and insight
  // generation moved to a background job, tracked via job_id against
  // GET /api/jobs/{job_id} instead of being returned here directly.
  fetched: number
  stored: number
  duplicates_skipped: number
  job_id: string
  status: "processing"
}

export interface JobProcessing {
  job_id: string
  status: "processing"
  stage: "categorizing" | "generating_insights"
  progress: number
  message: string
}

export interface JobComplete {
  job_id: string
  status: "complete"
  stage: "done"
  progress: number
  categorized: number
  // Never persisted server-side (S2-06) — generated fresh by the job.
  insights: InsightItem[]
  insights_provider: string | null
  insights_generated_at: string | null
  insights_error_message: string | null
  message: string
}

export interface JobFailed {
  job_id: string
  status: "failed"
  stage: string
  error: string
}

export type JobStatus = JobProcessing | JobComplete | JobFailed

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

// Client-side cache shape for insights — set only by useDashboard's sync
// mutation (from SyncResponse's insights fields), read only by useInsights.
export interface InsightsCacheEntry {
  insights: InsightItem[]
  provider: string | null
  generatedAt: string | null
  errorMessage: string | null
}

export type AmountFilter = "all" | "spent" | "received"

export interface TransactionItem {
  id: string
  account_id: string
  booking_date: string | null
  amount: number
  currency: string
  description: string | null
  category: string | null
  subcategory: string | null
  fetched_at: string
}

export interface TransactionsListResponse {
  transactions: TransactionItem[]
  total: number
  page: number
  pages: number
}

export type CategoryColorSource = "seed" | "ai" | "user"

export interface Category {
  name: string
  color: string
  is_custom: boolean
  source: CategoryColorSource
}
