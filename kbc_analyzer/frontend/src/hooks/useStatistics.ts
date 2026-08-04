import { useQuery } from "@tanstack/react-query"

import { getStatistics } from "@/lib/api"
import { statisticsKey } from "@/lib/queryKeys"
import type { StatisticsResponse } from "@/lib/types"

// Read-only view onto the statistics cache for chart/summary components
// (S1-06, S1-07, S1-08). `enabled: false` means this hook never fires its own
// request — it only subscribes to and re-renders from whatever useDashboard's
// sync mutation already placed in the cache under the same query key.
export function useStatistics(dateFrom: string, dateTo: string) {
  return useQuery<StatisticsResponse>({
    queryKey: statisticsKey(dateFrom, dateTo),
    queryFn: () => getStatistics(dateFrom, dateTo),
    enabled: false,
  })
}
