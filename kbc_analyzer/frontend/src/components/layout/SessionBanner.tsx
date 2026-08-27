import { useState } from "react"
import { AlertTriangle, Landmark, MailWarning, OctagonAlert, X } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"
import { cn } from "@/lib/utils"

// Bump this to test the warning banner without waiting for a real session to
// near expiry (per S2-02's WHEN DONE ask) — 90 triggers it against almost any
// real session; put back to 7 before shipping.
const WARNING_THRESHOLD_DAYS = 7

// S8-01: a user can now have KBC and/or ING connected, so "reconnect" is no
// longer a single unambiguous action this banner can trigger inline — which
// bank needs attention is a picker decision, not a one-click one. This
// banner now only surfaces that *something* needs attention and routes to
// Settings' Bank Connection picker, rather than driving the reconnect flow
// itself (that flow now lives entirely in BankConnectionSection.tsx).
export function SessionBanner() {
  const { data, isError } = useEnableBankingStatus()
  const navigate = useNavigate()

  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  // S7-09: an unverified account 403s this exact request
  // (require_verified_email) — without this branch, the banner would
  // just silently disappear (the !data check below), leaving a
  // freshly-registered user with no visible explanation of why there's
  // no "Connect your bank" prompt at all. Real-world proof this needed
  // fixing, not a hypothetical: a fresh local registration surfaced it.
  if (isError) {
    return (
      <div className="flex items-start justify-between gap-4 border-b border-warning/30 bg-warning/10 px-6 py-3">
        <div className="flex items-start gap-2.5">
          <MailWarning className="mt-0.5 size-4 shrink-0 text-warning" />
          <p className="text-sm text-text-primary">
            Verify your email to connect a bank account — check your inbox for the link.
          </p>
        </div>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={() => setDismissed(true)}
          className="rounded p-1 text-text-secondary hover:bg-black/5"
        >
          <X className="size-4" />
        </button>
      </div>
    )
  }

  if (!data) return null

  const warningThresholdMs = WARNING_THRESHOLD_DAYS * 24 * 60 * 60 * 1000

  // S8-01: aggregate across every bank Mymble supports, not one status.
  // "Connect" (primary) only when literally nothing is connected —
  // otherwise any bank's expired/nearing-expiry state takes priority over
  // another still-connected bank staying quiet, since the point is to
  // surface whatever needs attention, not to hide it behind a healthy one.
  const anyExpired = data.some((s) => s.status === "expired")
  const nearingExpiry = data.find(
    (s) =>
      s.status === "active" &&
      s.expires_at !== null &&
      new Date(s.expires_at).getTime() - Date.now() <= warningThresholdMs
  )
  const allNotConnected = data.every((s) => s.status === "not_connected")

  if (!anyExpired && !nearingExpiry && !allNotConnected) return null

  const variant = anyExpired ? "danger" : nearingExpiry ? "warning" : "primary"

  const expiresAtLabel = nearingExpiry?.expires_at
    ? new Date(nearingExpiry.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null

  return (
    <div
      className={cn(
        "flex flex-col gap-3 border-b px-6 py-3",
        variant === "danger" && "border-danger/30 bg-danger/10",
        variant === "warning" && "border-warning/30 bg-warning/10",
        variant === "primary" && "border-primary/30 bg-primary/10"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2.5">
          {variant === "danger" && <OctagonAlert className="mt-0.5 size-4 shrink-0 text-danger" />}
          {variant === "warning" && <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />}
          {variant === "primary" && <Landmark className="mt-0.5 size-4 shrink-0 text-primary" />}
          <p className="text-sm text-text-primary">
            {variant === "danger" && "A bank connection expired. Reconnect to keep syncing your transactions."}
            {variant === "warning" &&
              `Your ${nearingExpiry?.institution} connection expires on ${expiresAtLabel}. Reconnect now to avoid interruption.`}
            {variant === "primary" && "Connect your bank to start syncing transactions."}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button size="sm" onClick={() => navigate("/settings")}>
            {allNotConnected ? "Connect" : "Manage in Settings"}
          </Button>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => setDismissed(true)}
            className="rounded p-1 text-text-secondary hover:bg-black/5"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
