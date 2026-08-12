import { useQuery } from "@tanstack/react-query"

import { getBudgets } from "@/lib/api"

export const budgetsKey = ["budgets"] as const

// Auto-fetching, like useCategories — budgets change rarely (only via this
// hook's own mutations), so a plain query with no manual refetch wiring is
// enough for both the Settings section and the dashboard widget to share.
export function useBudgets() {
  return useQuery({
    queryKey: budgetsKey,
    queryFn: getBudgets,
  })
}
