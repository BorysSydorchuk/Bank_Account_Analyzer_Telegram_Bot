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
