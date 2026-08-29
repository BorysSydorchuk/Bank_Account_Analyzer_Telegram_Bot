// Mirrors backend/app/schemas.py — kept hand-in-sync since there's no shared
// schema generation between the FastAPI and TypeScript sides yet.

export type InsightType = "pattern" | "anomaly" | "saving" | "rhythm" | "category"
export type InsightSeverity = "info" | "warning" | "positive"

// S6-04, email_verified added S7-09
export interface UserOut {
  id: string
  email: string
  email_verified: boolean
}

export interface InsightItem {
  type: InsightType
  title: string
  body: string
  severity: InsightSeverity
}

export interface SyncResponse {
  // S4-02: the Enable Banking fetch itself moved into the background job
  // along with storing/categorizing/insights — this only ever creates the
  // job now, so fetched/stored/duplicates_skipped aren't known yet at
  // response time. Those numbers show up in the job's own stage messages
  // instead (see the "storing" stage), via GET /api/jobs/{job_id}.
  job_id: string
  status: "processing"
}

export interface JobProcessing {
  job_id: string
  status: "processing"
  stage: "fetching" | "storing" | "categorizing" | "generating_insights"
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

export interface EnableBankingStatus {
  // S8-01: which bank this status describes — GET /status now returns one
  // entry per bank Mymble supports, not a single overall status, since a
  // user can have zero, one, or two connections live at once.
  institution: string
  // S7-07: "not_connected" (no session has ever existed for this user) is
  // distinct from "expired" (one existed, then lapsed).
  status: "active" | "expired" | "not_connected"
  expires_at: string | null
}

// S8-01: GET /status now returns one entry per supported bank.
export type EnableBankingStatusResponse = EnableBankingStatus[]

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

export interface TestConnectionResponse {
  connected: boolean
  error_message: string | null
}

// Client-side cache shape for insights — set only by useDashboard's sync
// mutation (from SyncResponse's insights fields), read only by useInsights.
export interface InsightsCacheEntry {
  insights: InsightItem[]
  provider: string | null
  generatedAt: string | null
  errorMessage: string | null
}

export interface CachedInsightsResponse {
  insights: InsightItem[]
  provider: string | null
  generated_at: string | null
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
  manually_edited: boolean
  fetched_at: string
}

export interface PatchTransactionRequest {
  category?: string | null
  subcategory?: string | null
  description?: string
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
  // Present once the AI has assigned this category a color at least once —
  // "Reset to AI" (S3-06) only shows when this is non-null.
  ai_color: string | null
}

export type BudgetStatus = "on_track" | "warning" | "exceeded"

export interface Budget {
  category: string
  amount: number
  period: string
  // Always the calendar month of today (S4-05), never a rolling 30 days —
  // matches the "This month" preset used elsewhere in the app.
  spent_this_month: number
  percentage_used: number
  status: BudgetStatus
}

export type ChatRole = "user" | "assistant"

// The wire shape POST /api/chat expects for history (S4-06) — deliberately
// smaller than ChatMessage below, which also carries client-only UI state
// (id, timestamp, streaming status) that never gets sent to the backend.
export interface ChatHistoryEntry {
  role: ChatRole
  content: string
}

export interface ChatUsage {
  input: number
  output: number
}

// GET /api/insights/compare (S4-08) — statistics are always computed live
// from transactions; insights are read from storage exactly as stored for
// each exact range (the S4-04 decision), so `insights` here can be empty
// even for a period with real spending.
export interface PeriodComparison {
  date_range: string
  total_spent: number
  by_category: CategoryStat[]
  insights: InsightItem[]
  insights_generated_at: string | null
}

export interface CategoryChange {
  category: string
  period_a: number
  period_b: number
  change: number
  // null when period_a's total for this category was 0 — percentage change
  // from zero is undefined, not "infinite%" or silently 0%.
  change_pct: number | null
}

export interface ComparisonDelta {
  total_spent_change: number
  total_spent_change_pct: number | null
  // Sorted by absolute change descending (biggest movers first) — see
  // comparison_service.py.
  category_changes: CategoryChange[]
}

export interface ComparisonResponse {
  period_a: PeriodComparison
  period_b: PeriodComparison
  delta: ComparisonDelta
}

// S9-05 — Billing
export type SubscriptionTier = "free" | "paid"

export interface BillingStatus {
  billing_enabled: boolean
  tier: SubscriptionTier
  status: string | null
}

export interface CheckoutSessionResponse {
  checkout_url: string
}

export interface PortalSessionResponse {
  portal_url: string
}

