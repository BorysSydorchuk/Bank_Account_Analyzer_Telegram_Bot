import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { ApiError, completeEnableBankingCallback, reauthorizeEnableBanking } from "@/lib/api"

export type ReconnectPhase = "idle" | "awaiting-paste" | "verifying" | "error" | "success"

// The reconnect flow itself (S2-02) — shared between the dashboard's SessionBanner
// and the Settings page's Bank Connection section (S2-03), which the ticket
// explicitly calls "the same flow," not a lookalike. Each caller renders its own
// markup around this; only the state machine and the two mutations live here.
export function useEnableBankingReconnect() {
  const queryClient = useQueryClient()

  const [phase, setPhase] = useState<ReconnectPhase>("idle")
  const [pastedUrl, setPastedUrl] = useState("")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const reauthorizeMutation = useMutation({
    mutationFn: reauthorizeEnableBanking,
    onSuccess: (result) => {
      window.open(result.auth_url, "_blank", "noopener,noreferrer")
      setPhase("awaiting-paste")
    },
    onError: (error: unknown) => {
      setErrorMessage(error instanceof ApiError ? error.message : "Couldn't start reconnection. Try again.")
    },
  })

  const callbackMutation = useMutation({
    mutationFn: ({ code, state }: { code: string; state: string | null }) =>
      completeEnableBankingCallback(code, state),
    onSuccess: () => {
      setPhase("success")
      queryClient.invalidateQueries({ queryKey: ["enableBankingStatus"] })
    },
    onError: (error: unknown) => {
      setPhase("error")
      setErrorMessage(error instanceof ApiError ? error.message : "Couldn't verify authorization. Try again.")
    },
  })

  function start() {
    setErrorMessage(null)
    reauthorizeMutation.mutate()
  }

  function verify() {
    let code: string | null = null
    let state: string | null = null
    try {
      const parsed = new URL(pastedUrl.trim())
      code = parsed.searchParams.get("code")
      state = parsed.searchParams.get("state")
    } catch {
      // not a valid URL — code stays null, handled below
    }
    if (!code) {
      setErrorMessage(
        "Couldn't find a code in that URL — make sure you copied the full address bar URL after authorizing."
      )
      return
    }
    setErrorMessage(null)
    setPhase("verifying")
    callbackMutation.mutate({ code, state })
  }

  function cancel() {
    setPhase("idle")
    setPastedUrl("")
    setErrorMessage(null)
  }

  return {
    phase,
    pastedUrl,
    setPastedUrl,
    errorMessage,
    start,
    verify,
    cancel,
    isStarting: reauthorizeMutation.isPending,
  }
}
