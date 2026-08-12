import type {
  AmountFilter,
  Budget,
  CachedInsightsResponse,
  Category,
  EnableBankingStatusResponse,
  JobStatus,
  PatchSettingsResponse,
  PatchTransactionRequest,
  ReauthorizeResponse,
  SettingsResponse,
  StatisticsResponse,
  SyncResponse,
  TestConnectionResponse,
  TransactionItem,
  TransactionsListResponse,
} from "./types"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// Carries the API's own {"message": "..."} body (see backend/app/main.py's
// exception handlers) so the UI can show the real reason, not a generic one.
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    // main.py's custom exception handlers return {"message": ...}; a plain
    // `raise HTTPException(status_code, detail=...)` (used directly in most
    // routers) gets Starlette's own default body, {"detail": ...} — both
    // conventions exist in this API, so both need checking here.
    throw new ApiError(res.status, body?.message ?? body?.detail ?? `Request failed with status ${res.status}`)
  }
  // 204 No Content (e.g. DELETE /api/budgets/{category}) has no body to parse.
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export function syncTransactions(dateFrom: string, dateTo: string) {
  return request<SyncResponse>("/api/transactions/sync", {
    method: "POST",
    body: JSON.stringify({ date_from: dateFrom, date_to: dateTo }),
  })
}

export function getStatistics(dateFrom: string, dateTo: string) {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
  return request<StatisticsResponse>(`/api/statistics?${params.toString()}`)
}

export function getEnableBankingStatus() {
  return request<EnableBankingStatusResponse>("/api/auth/enable-banking/status")
}

export function reauthorizeEnableBanking() {
  return request<ReauthorizeResponse>("/api/auth/enable-banking/reauthorize", { method: "POST" })
}

export function completeEnableBankingCallback(code: string, state: string | null) {
  return request<EnableBankingStatusResponse>("/api/auth/enable-banking/callback", {
    method: "POST",
    body: JSON.stringify({ code, state }),
  })
}

export function getSettings() {
  return request<SettingsResponse>("/api/settings")
}

export function patchSettings(key: string, value: string) {
  return request<PatchSettingsResponse>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify({ key, value }),
  })
}

export function testProviderConnection(provider: "gemini" | "claude", apiKey: string) {
  return request<TestConnectionResponse>("/api/settings/test-connection", {
    method: "POST",
    body: JSON.stringify({ provider, api_key: apiKey }),
  })
}

export function getTransactionsList(
  dateFrom: string,
  dateTo: string,
  page: number,
  limit: number,
  categories: string[],
  amountType: AmountFilter
) {
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
    page: String(page),
    limit: String(limit),
    amount_type: amountType,
  })
  for (const category of categories) params.append("category", category)
  return request<TransactionsListResponse>(`/api/transactions?${params.toString()}`)
}

export function searchTransactions(q: string, limit: number) {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return request<TransactionsListResponse>(`/api/transactions/search?${params.toString()}`)
}

export function getCategories() {
  return request<Category[]>("/api/categories")
}

export function patchCategoryColor(name: string, color: string) {
  return request<Category>(`/api/categories/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body: JSON.stringify({ color }),
  })
}

export function createCategory(name: string, color: string) {
  return request<Category>("/api/categories", {
    method: "POST",
    body: JSON.stringify({ name, color }),
  })
}

export function resetCategoryColor(name: string) {
  return request<Category>(`/api/categories/${encodeURIComponent(name)}/reset`, {
    method: "POST",
  })
}

export function getInsights(dateFrom: string, dateTo: string) {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
  return request<CachedInsightsResponse>(`/api/insights?${params.toString()}`)
}

export function getJob(jobId: string) {
  return request<JobStatus>(`/api/jobs/${jobId}`)
}

export function patchTransaction(id: string, updates: PatchTransactionRequest) {
  return request<TransactionItem>(`/api/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  })
}

export function getBudgets() {
  return request<Budget[]>("/api/budgets")
}

export function createBudget(category: string, amount: number) {
  return request<Budget>("/api/budgets", {
    method: "POST",
    body: JSON.stringify({ category, amount }),
  })
}

export function patchBudgetAmount(category: string, amount: number) {
  return request<Budget>(`/api/budgets/${encodeURIComponent(category)}`, {
    method: "PATCH",
    body: JSON.stringify({ amount }),
  })
}

export function deleteBudget(category: string) {
  return request<void>(`/api/budgets/${encodeURIComponent(category)}`, { method: "DELETE" })
}
