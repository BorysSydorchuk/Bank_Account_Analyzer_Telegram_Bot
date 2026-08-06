import { useQuery } from "@tanstack/react-query"

import { getTransactionsList } from "@/lib/api"
import type { AmountFilter, TransactionsListResponse } from "@/lib/types"

// Unlike useStatistics/useInsights, this one fetches on its own — the
// Transactions page has no "sync" concept of its own, it just reads whatever
// is already in Postgres (synced from the Dashboard). Cheap, so a normal
// auto-refetching query per filter/page change is the right shape here.
export function useTransactionsList(
  dateFrom: string,
  dateTo: string,
  page: number,
  limit: number,
  categories: string[],
  amountType: AmountFilter
) {
  return useQuery<TransactionsListResponse>({
    queryKey: ["transactionsList", dateFrom, dateTo, page, limit, categories, amountType],
    queryFn: () => getTransactionsList(dateFrom, dateTo, page, limit, categories, amountType),
  })
}
