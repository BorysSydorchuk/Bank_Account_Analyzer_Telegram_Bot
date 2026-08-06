import { useQuery } from "@tanstack/react-query"

import { getStatistics } from "@/lib/api"

// A real, independent fetch (not the dashboard's read-only statistics cache —
// the Transactions page can be visited with a different date range than the
// Dashboard last synced, so it can't rely on that cache being populated or
// current). Only used to know which categories exist for the filter dropdown
// and to color-match pills to the same set the donut chart would show.
export function useCategoryOptions(dateFrom: string, dateTo: string) {
  const { data } = useQuery({
    queryKey: ["categoryOptions", dateFrom, dateTo],
    queryFn: () => getStatistics(dateFrom, dateTo),
  })
  return data?.by_category.map((c) => c.category) ?? []
}
