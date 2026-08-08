import { useQuery } from "@tanstack/react-query"

import { searchTransactions } from "@/lib/api"

// Global search (S3-07 Item 4) — across every synced transaction, not
// scoped to the Transactions page's current date range, category filter, or
// page. Only enabled once there's something to search for, so clearing the
// box doesn't fire a request for an empty query.
export function useTransactionSearch(query: string) {
  return useQuery({
    queryKey: ["transactionSearch", query],
    queryFn: () => searchTransactions(query, 20),
    enabled: query.trim().length > 0,
  })
}
