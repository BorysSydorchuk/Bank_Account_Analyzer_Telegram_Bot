import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, ExternalLink, OctagonAlert, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"
import { ApiError, completeEnableBankingCallback, reauthorizeEnableBanking } from "@/lib/api"
import { cn } from "@/lib/utils"

// Bump this to test the warning banner without waiting for a real session to
// near expiry (per S2-02's WHEN DONE ask) — 90 triggers it against almost any
// real session; put back to 7 before shipping.
const WARNING_THRESHOLD_DAYS = 7

type ReconnectPhase = "idle" | "awaiting-paste" | "verifying" | "error" | "success"

export function SessionBanner() {
  const { data } = useEnableBankingStatus()
  const queryClient = useQueryClient()

  const [dismissed, setDismissed] = useState(false)
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

  if (dismissed || !data) return null

  const expiresAtMs = data.expires_at ? new Date(data.expires_at).getTime() : null
  const warningThresholdMs = WARNING_THRESHOLD_DAYS * 24 * 60 * 60 * 1000

  const isExpired = data.status === "expired"
  // Compares raw milliseconds rather than rounding to whole days — rounding (e.g. Math.ceil)
  // pushes a real 7.7-days-remaining session to "8 days," silently missing the 7-day banner.
  const isNearingExpiry = !isExpired && expiresAtMs !== null && expiresAtMs - Date.now() <= warningThresholdMs

  if (phase === "idle" && !isExpired && !isNearingExpiry) return null

  const variant = phase === "success" ? "success" : isExpired ? "danger" : "warning"

  function startReconnect() {
    setErrorMessage(null)
    reauthorizeMutation.mutate()
  }

  function verifyPastedUrl() {
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

  function cancelReconnect() {
    setPhase("idle")
    setPastedUrl("")
    setErrorMessage(null)
  }

  const expiresAtLabel = data.expires_at
    ? new Date(data.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null

  return (
    <div
      className={cn(
        "flex flex-col gap-3 border-b px-6 py-3",
        variant === "danger" && "border-danger/30 bg-danger/10",
        variant === "warning" && "border-warning/30 bg-warning/10",
        variant === "success" && "border-success/30 bg-success/10"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2.5">
          {variant === "danger" && <OctagonAlert className="mt-0.5 size-4 shrink-0 text-danger" />}
          {variant === "warning" && <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />}
          {variant === "success" && <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />}
          <p className="text-sm text-text-primary">
            {variant === "success" && "Bank connection reconnected — you're all set."}
            {variant === "danger" &&
              phase === "idle" &&
              "Bank connection expired. Reconnect to sync your transactions."}
            {variant === "warning" &&
              phase === "idle" &&
              `Your bank connection expires on ${expiresAtLabel}. Reconnect now to avoid interruption.`}
            {(phase === "awaiting-paste" || phase === "verifying" || phase === "error") &&
              "Complete the KBC authorization in the new tab, then paste the full redirect URL below."}
          </p>
        </div>

        {(phase === "idle" || phase === "success") && (
          <div className="flex shrink-0 items-center gap-2">
            {phase === "idle" && (
              <Button size="sm" onClick={startReconnect} disabled={reauthorizeMutation.isPending}>
                {reauthorizeMutation.isPending ? "Starting…" : "Reconnect"}
              </Button>
            )}
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => setDismissed(true)}
              className="rounded p-1 text-text-secondary hover:bg-black/5"
            >
              <X className="size-4" />
            </button>
          </div>
        )}
      </div>

      {(phase === "awaiting-paste" || phase === "verifying" || phase === "error") && (
        <div className="ml-6.5 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <ExternalLink className="size-3.5" />
            The KBC authorization page opened in a new tab. After you approve access, that tab
            will show an address starting with <code className="rounded bg-black/5 px-1">https://localhost/callback?code=…</code>
            — copy that full address and paste it here.
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={pastedUrl}
              onChange={(e) => setPastedUrl(e.target.value)}
              placeholder="https://localhost/callback?code=...&state=..."
              className="h-8 flex-1 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
            <Button size="sm" onClick={verifyPastedUrl} disabled={!pastedUrl || phase === "verifying"}>
              {phase === "verifying" ? "Verifying…" : "I've authorized"}
            </Button>
            <Button size="sm" variant="outline" onClick={cancelReconnect}>
              Cancel
            </Button>
          </div>
          {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
        </div>
      )}

      {phase === "idle" && errorMessage && <p className="ml-6.5 text-xs text-danger">{errorMessage}</p>}
    </div>
  )
}
