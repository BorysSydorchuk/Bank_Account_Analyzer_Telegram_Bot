import { useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, getJob, getStatistics, syncTransactions } from "@/lib/api"
import { getThisMonthRange, type DateRangePreset } from "@/lib/dateRangePresets"
import { insightsKey, statisticsKey } from "@/lib/queryKeys"
import type { InsightsCacheEntry } from "@/lib/types"
import { useDateRangeParam } from "./useDateRangeParam"

interface SyncArgs {
  dateFrom: string
  dateTo: string
}

interface ActiveJob {
  jobId: string
  dateFrom: string
  dateTo: string
  startedAt: number
}

const POLL_INTERVAL_MS = 2000
// S3-04's own cap on how long to keep polling. A job stuck this long almost
// certainly means the celery_worker died mid-task, not that it's simply
// slow — the frontend gives up and surfaces a timeout rather than polling
// forever with no way for the user to know anything is wrong.
const MAX_POLL_DURATION_MS = 10 * 60 * 1000

// The one place that knows how to run "sync then track its background job."
// Called by preset buttons (auto-sync), the Sync & Analyze button (current
// selection), and once on mount if the URL already carried a range (refresh
// behavior).
export function useDashboard() {
  const { dateFrom: urlFrom, dateTo: urlTo, setRange } = useDateRangeParam()
  const queryClient = useQueryClient()
  const hasAutoSynced = useRef(false)
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null)
  // Holds whatever the most recent real message was — a live "Categorizing
  // batch 2 of 5..." while a job is active, or the final "Done — N
  // transactions categorized, M insights generated" once it isn't. Replaces
  // S2-08's timed setTimeout guesses with the backend's own words.
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

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
    mutationFn: ({ dateFrom, dateTo }: SyncArgs) => syncTransactions(dateFrom, dateTo),
    onSuccess: (syncResult, variables) => {
      // S4-02: the job starts on the "fetching" stage now, not "categorizing"
      // — the Enable Banking fetch moved into the background job itself, so
      // this response comes back before any of that has happened yet. The
      // very next poll immediately replaces this with the job's own message.
      setStatusMessage("Fetching transactions from KBC...")
      setActiveJob({
        jobId: syncResult.job_id,
        dateFrom: variables.dateFrom,
        dateTo: variables.dateTo,
        startedAt: Date.now(),
      })
    },
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Something went wrong. Please try again.")
    },
  })

  // Polls GET /api/jobs/{job_id} every 2s while a job is active — the real
  // replacement for S2-08's timed fake progress labels. refetchInterval
  // returns false the moment the job leaves "processing", so this settles
  // into a plain one-shot query once the job resolves.
  const jobQuery = useQuery({
    queryKey: ["job", activeJob?.jobId],
    queryFn: () => getJob(activeJob!.jobId),
    enabled: !!activeJob,
    refetchInterval: (query) => (query.state.data?.status === "processing" ? POLL_INTERVAL_MS : false),
    // Without this, React Query silently skips interval-triggered refetches
    // whenever the tab isn't focused (window.focusManager) — a sync the user
    // started and then alt-tabbed away from would look stuck forever even
    // though the celery_worker kept working the whole time.
    refetchIntervalInBackground: true,
  })

  // A dedicated timer rather than checking elapsed time inside the polling
  // effect below: React Query's structural sharing keeps the exact same
  // `data` reference across polls when the response is byte-identical (a
  // dead celery_worker never advances past its first "processing" message),
  // so an effect keyed on `jobQuery.data` would never re-run to notice the
  // timeout had passed. A plain setTimeout has no such dependency.
  useEffect(() => {
    if (!activeJob) return
    const remaining = MAX_POLL_DURATION_MS - (Date.now() - activeJob.startedAt)
    const timer = setTimeout(() => {
      toast.error("Sync is taking longer than expected. It may still finish in the background — check back shortly.")
      setStatusMessage(null)
      setActiveJob(null)
    }, Math.max(remaining, 0))
    return () => clearTimeout(timer)
  }, [activeJob])

  useEffect(() => {
    if (!activeJob) return
    const job = jobQuery.data
    if (!job) return

    if (job.status === "processing") {
      setStatusMessage(job.message)
      return
    }

    if (job.status === "complete") {
      const insightsEntry: InsightsCacheEntry = {
        insights: job.insights,
        provider: job.insights_provider,
        generatedAt: job.insights_generated_at,
        errorMessage: job.insights_error_message,
      }
      queryClient.setQueryData(insightsKey(activeJob.dateFrom, activeJob.dateTo), insightsEntry)
      // Categorization changed transactions.category for potentially many
      // rows — statistics has to be re-fetched, not just re-read from cache.
      getStatistics(activeJob.dateFrom, activeJob.dateTo).then((statistics) => {
        queryClient.setQueryData(statisticsKey(activeJob.dateFrom, activeJob.dateTo), statistics)
      })
      setStatusMessage(job.message)
      setActiveJob(null)
    } else if (job.status === "failed") {
      toast.error(job.error)
      setStatusMessage(null)
      setActiveJob(null)
    }
    // Deliberately keyed only on the polled data changing — activeJob and
    // queryClient are stable for the lifetime of one job and re-running this
    // effect for their own sake would just re-process the same job result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobQuery.data])

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
    // True from the moment sync is requested until its background job
    // resolves (complete/failed) or times out — covers both the initial
    // fetch+store request and the categorization/insights job that follows it.
    isSyncing: syncMutation.isPending || !!activeJob,
    statusMessage,
  }
}
