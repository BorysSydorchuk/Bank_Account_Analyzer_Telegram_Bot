import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError, getEnableBankingStatus, reauthorizeEnableBanking } from "@/lib/api"

export type ReconnectPhase = "idle" | "waiting" | "success" | "error"

const POLL_INTERVAL_MS = 2000
const MAX_WAIT_MS = 5 * 60 * 1000

// The reconnect flow itself — shared between the dashboard's SessionBanner
// and the Settings page's Bank Connection section, which the ticket
// explicitly calls "the same flow," not a lookalike. Each caller renders its
// own markup around this; only the state machine and mutations live here.
//
// S3-07 Item 2: the redirect is now caught automatically by a local HTTPS
// server running in the celery_worker process (see
// backend/app/eb_callback_server.py), which completes the re-authorization
// itself — this hook just polls GET /api/auth/enable-banking/status until it
// flips to "active", instead of the old flow where the user had to
// copy-paste the redirect URL back in.
export function useEnableBankingReconnect() {
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<ReconnectPhase>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const reauthorizeMutation = useMutation({
    mutationFn: reauthorizeEnableBanking,
    onSuccess: (result) => {
      window.open(result.auth_url, "_blank", "noopener,noreferrer")
      setPhase("waiting")
    },
    onError: (error: unknown) => {
      setErrorMessage(error instanceof ApiError ? error.message : "Couldn't start reconnection. Try again.")
    },
  })

  const statusQuery = useQuery({
    queryKey: ["enableBankingStatus"],
    queryFn: getEnableBankingStatus,
    refetchInterval: phase === "waiting" ? POLL_INTERVAL_MS : false,
    refetchIntervalInBackground: true,
    // S7-09: same reasoning as useEnableBankingStatus.ts — a 403 here
    // (unverified email) is never transient, and this hook shares that
    // hook's exact queryKey, so both observers need the same retry
    // setting to avoid one silently overriding the other's.
    retry: false,
  })

  useEffect(() => {
    if (phase !== "waiting") return
    if (statusQuery.data?.status === "active") {
      setPhase("success")
      queryClient.invalidateQueries({ queryKey: ["enableBankingStatus"] })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusQuery.data])

  // Dedicated timer, not a data-change effect — same lesson as S3-04's job
  // polling: React Query reuses the same `data` reference across polls when
  // the response is byte-identical, so an effect keyed only on `data` would
  // never re-fire to notice a timeout had elapsed while status stayed "expired".
  useEffect(() => {
    if (phase !== "waiting") return
    const timer = setTimeout(() => {
      setPhase("error")
      setErrorMessage("Didn't detect a completed authorization in time. Click Reconnect to try again.")
    }, MAX_WAIT_MS)
    return () => clearTimeout(timer)
  }, [phase])

  function start() {
    setErrorMessage(null)
    reauthorizeMutation.mutate()
  }

  function cancel() {
    setPhase("idle")
    setErrorMessage(null)
  }

  return { phase, errorMessage, start, cancel, isStarting: reauthorizeMutation.isPending }
}
