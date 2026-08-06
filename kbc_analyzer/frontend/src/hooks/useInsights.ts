import { useQuery } from "@tanstack/react-query"

import { insightsKey } from "@/lib/queryKeys"
import type { InsightsCacheEntry } from "@/lib/types"

// Read-only view onto the insights cache, same enabled:false pattern as
// useStatistics — useDashboard's sync mutation is the only writer (insights
// are never persisted server-side, S2-06), so there's nothing for this hook
// to fetch on its own. queryFn is never called in practice; it exists only
// so a stray refetch()/invalidateQueries() doesn't crash instead of no-op.
export function useInsights(dateFrom: string, dateTo: string) {
  return useQuery<InsightsCacheEntry>({
    queryKey: insightsKey(dateFrom, dateTo),
    queryFn: () => {
      throw new Error("Insights are only ever populated by a sync — there is no standalone fetch.")
    },
    enabled: false,
  })
}
