import { useQuery } from "@tanstack/react-query"

import { getCategories } from "@/lib/api"

export const categoriesKey = ["categories"] as const

// A normal auto-fetching query (categories rarely change — only via S3-02's
// AI assignment or S3-06's user overrides) — safe to call from multiple
// components at once: React Query dedupes concurrent requests under the same
// key, so this isn't the "duplicate mutation" trap useDashboard has to guard
// against elsewhere.
export function useCategories() {
  return useQuery({
    queryKey: categoriesKey,
    queryFn: getCategories,
  })
}
