import { useQuery } from "@tanstack/react-query"

import { getStatistics } from "@/lib/api"
import { statisticsKey } from "@/lib/queryKeys"
import type { StatisticsResponse } from "@/lib/types"

// Statistics for chart/summary components (S1-06, S1-07, S1-08). Fetches on
// mount like any normal query — a completed sync (useDashboard) still writes
// fresh results straight into this same cache key via setQueryData, so a
// sync updates these components immediately without waiting for a refetch.
//
// S3-08: this used to be `enabled: false` (cache-only — it only ever showed
// whatever a sync had already written), which was fine before S3-07 added
// real insight persistence. Once useInsights (Item 3) started fetching real
// history from the DB on mount, this hook fell out of step with it: loading
// the dashboard with no date range in the URL — e.g. a plain refresh — skips
// useDashboard's auto-sync entirely, so this always stayed empty and showed
// "No data for this period" side-by-side with an AI Insights panel correctly
// showing real numbers for that identical range.
export function useStatistics(dateFrom: string, dateTo: string) {
  return useQuery<StatisticsResponse>({
    queryKey: statisticsKey(dateFrom, dateTo),
    queryFn: () => getStatistics(dateFrom, dateTo),
  })
}
