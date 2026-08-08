import type {
  AmountFilter,
  Category,
  EnableBankingStatusResponse,
  JobStatus,
  PatchSettingsResponse,
  ReauthorizeResponse,
  SettingsResponse,
  StatisticsResponse,
  SyncResponse,
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
    throw new ApiError(res.status, body?.message ?? `Request failed with status ${res.status}`)
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

export function getCategories() {
  return request<Category[]>("/api/categories")
}

export function getJob(jobId: string) {
  return request<JobStatus>(`/api/jobs/${jobId}`)
}
