import { useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, OctagonAlert, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useEnableBankingReconnect } from "@/hooks/useEnableBankingReconnect"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"
import { cn } from "@/lib/utils"

// Bump this to test the warning banner without waiting for a real session to
// near expiry (per S2-02's WHEN DONE ask) — 90 triggers it against almost any
// real session; put back to 7 before shipping.
const WARNING_THRESHOLD_DAYS = 7

export function SessionBanner() {
  const { data } = useEnableBankingStatus()
  const { phase, errorMessage, start, cancel, isStarting } = useEnableBankingReconnect()

  const [dismissed, setDismissed] = useState(false)

  if (dismissed || !data) return null

  const expiresAtMs = data.expires_at ? new Date(data.expires_at).getTime() : null
  const warningThresholdMs = WARNING_THRESHOLD_DAYS * 24 * 60 * 60 * 1000

  const isExpired = data.status === "expired"
  // Compares raw milliseconds rather than rounding to whole days — rounding (e.g. Math.ceil)
  // pushes a real 7.7-days-remaining session to "8 days," silently missing the 7-day banner.
  const isNearingExpiry = !isExpired && expiresAtMs !== null && expiresAtMs - Date.now() <= warningThresholdMs

  if (phase === "idle" && !isExpired && !isNearingExpiry) return null

  const variant = phase === "success" ? "success" : isExpired ? "danger" : "warning"

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
            {phase === "waiting" && "Waiting for you to finish authorizing in the new tab…"}
            {phase === "error" && "Complete the KBC authorization in the new tab, then try again."}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {phase === "idle" && (
            <Button size="sm" onClick={start} disabled={isStarting}>
              {isStarting ? "Starting…" : "Reconnect"}
            </Button>
          )}
          {phase === "waiting" && <Loader2 className="size-4 animate-spin text-text-secondary" />}
          {(phase === "idle" || phase === "success") && (
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => setDismissed(true)}
              className="rounded p-1 text-text-secondary hover:bg-black/5"
            >
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      {phase === "error" && (
        <div className="ml-6.5 flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={cancel}>
            Dismiss
          </Button>
        </div>
      )}

      {(phase === "idle" || phase === "error") && errorMessage && (
        <p className="ml-6.5 text-xs text-danger">{errorMessage}</p>
      )}
    </div>
  )
}
