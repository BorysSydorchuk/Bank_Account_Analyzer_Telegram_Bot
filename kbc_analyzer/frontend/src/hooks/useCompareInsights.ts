import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, compareInsights } from "@/lib/api"

interface CompareArgs {
  periodAFrom: string
  periodATo: string
  periodBFrom: string
  periodBTo: string
}

// A one-off, user-triggered fetch (the "Compare" button), not a cached
// value anything else in the app reads — a mutation fits better than a
// query with no stable cache key to speak of.
export function useCompareInsights() {
  return useMutation({
    mutationFn: ({ periodAFrom, periodATo, periodBFrom, periodBTo }: CompareArgs) =>
      compareInsights(periodAFrom, periodATo, periodBFrom, periodBTo),
    onError: (error: unknown) => {
      // Carries the backend's real validation message (e.g. "period_a:
      // range cannot exceed 365 days.") straight through.
      toast.error(error instanceof ApiError ? error.message : "Could not compare these periods.")
    },
  })
}
