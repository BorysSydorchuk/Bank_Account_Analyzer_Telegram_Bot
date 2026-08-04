import { useEffect, useMemo, useRef } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, getStatistics, syncTransactions } from "@/lib/api"
import { getThisMonthRange, type DateRangePreset } from "@/lib/dateRangePresets"
import { statisticsKey } from "@/lib/queryKeys"
import { useDateRangeParam } from "./useDateRangeParam"

interface SyncArgs {
  dateFrom: string
  dateTo: string
}

// The one place that knows how to run "sync then fetch statistics." Called by
// preset buttons (auto-sync), the Sync & Analyze button (current selection),
// and once on mount if the URL already carried a range (refresh behavior).
export function useDashboard() {
  const { dateFrom: urlFrom, dateTo: urlTo, setRange } = useDateRangeParam()
  const queryClient = useQueryClient()
  const hasAutoSynced = useRef(false)

  // Display always shows a sensible range, even on a first-ever visit with no
  // URL params — but that fallback must NOT itself count as "a range was in
  // the URL," or the mount effect below would auto-sync on every fresh visit.
  const defaultRange = useMemo(() => getThisMonthRange(), [])
  const dateFrom = urlFrom ?? defaultRange.dateFrom
  const dateTo = urlTo ?? defaultRange.dateTo

  const syncMutation = useMutation({
    // Named so read-only components (e.g. SummaryCards) can observe pending/
    // error state via useMutationState instead of calling useDashboard()
    // themselves, which would duplicate the auto-sync effect below.
    mutationKey: ["syncStatistics"],
    mutationFn: async ({ dateFrom, dateTo }: SyncArgs) => {
      await syncTransactions(dateFrom, dateTo)
      return getStatistics(dateFrom, dateTo)
    },
    onSuccess: (data, variables) => {
      queryClient.setQueryData(statisticsKey(variables.dateFrom, variables.dateTo), data)
    },
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Something went wrong. Please try again.")
    },
  })

  useEffect(() => {
    if (!urlFrom || !urlTo) return
    // Deferred one tick so StrictMode's dev-only double-invoke of this effect
    // (setup → cleanup → setup) settles before the mutation actually fires —
    // the guard is checked when the timer runs, not when it's scheduled, so
    // exactly one of the two scheduled timers ends up doing anything.
    const timer = setTimeout(() => {
      if (!hasAutoSynced.current) {
        hasAutoSynced.current = true
        syncMutation.mutate({ dateFrom: urlFrom, dateTo: urlTo })
      }
    }, 0)
    return () => clearTimeout(timer)
    // Deliberately run once on mount only — re-running on every dateFrom/dateTo
    // change would re-sync on every manual date pick, not just page load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updateRange(nextFrom: string, nextTo: string) {
    setRange(nextFrom, nextTo)
  }

  function selectPreset(preset: DateRangePreset) {
    const next = preset.range()
    setRange(next.dateFrom, next.dateTo)
    syncMutation.mutate(next)
  }

  function syncNow() {
    syncMutation.mutate({ dateFrom, dateTo })
  }

  return {
    dateFrom,
    dateTo,
    updateRange,
    selectPreset,
    syncNow,
    isSyncing: syncMutation.isPending,
  }
}
