import { useQuery } from "@tanstack/react-query"

import { getInsights } from "@/lib/api"
import { insightsKey } from "@/lib/queryKeys"
import type { InsightsCacheEntry } from "@/lib/types"

// S3-07 Item 3: insights now persist server-side, so this fetches on mount
// like any normal query instead of the old enabled:false/cache-only pattern
// — a sync's completion (useDashboard) still writes fresh results straight
// into this same cache key via setQueryData, so a completed sync updates the
// panel immediately without waiting for a refetch.
export function useInsights(dateFrom: string, dateTo: string) {
  return useQuery<InsightsCacheEntry>({
    queryKey: insightsKey(dateFrom, dateTo),
    queryFn: async () => {
      const cached = await getInsights(dateFrom, dateTo)
      return {
        insights: cached.insights,
        provider: cached.provider,
        generatedAt: cached.generated_at,
        errorMessage: null,
      }
    },
  })
}
