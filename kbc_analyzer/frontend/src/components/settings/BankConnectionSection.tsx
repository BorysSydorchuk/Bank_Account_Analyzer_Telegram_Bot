import { CheckCircle2, ExternalLink, Landmark, Loader2, MailWarning, OctagonAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useEnableBankingReconnect } from "@/hooks/useEnableBankingReconnect"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"

export function BankConnectionSection() {
  const { data, isError } = useEnableBankingStatus()
  const { phase, errorMessage, start, cancel, isStarting } = useEnableBankingReconnect()

  const isActive = data?.status === "active"
  // S7-07: never-connected is a distinct state from expired — same
  // underlying flow (start() below), different copy so a first-time
  // user sees "Connect," not a message implying something was lost.
  const isNotConnected = data?.status === "not_connected"
  const expiresAtLabel = data?.expires_at
    ? new Date(data.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Bank Connection</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            {isError ? (
              // S7-09: require_verified_email's 403 — without this
              // branch, !data below is permanently true for an
              // unverified account and this card is stuck on "Checking
              // connection…" forever. Same fix as SessionBanner.tsx.
              <>
                <MailWarning className="size-4 text-warning" />
                <span className="text-text-primary">Verify your email to connect a bank account.</span>
              </>
            ) : !data ? (
              <span className="text-text-secondary">Checking connection…</span>
            ) : phase === "success" || isActive ? (
              <>
                <CheckCircle2 className="size-4 text-success" />
                <span className="text-text-primary">
                  {phase === "success"
                    ? "Connected — connection is active."
                    : expiresAtLabel
                      ? `Active — expires ${expiresAtLabel}.`
                      : "Active."}
                </span>
              </>
            ) : isNotConnected ? (
              <>
                <Landmark className="size-4 text-text-secondary" />
                <span className="text-text-primary">No bank connected yet.</span>
              </>
            ) : (
              <>
                <OctagonAlert className="size-4 text-danger" />
                <span className="text-text-primary">Expired — sync won't work until reconnected.</span>
              </>
            )}
          </div>
          {phase === "idle" && !isError && (
            <Button size="sm" variant={isNotConnected ? "default" : "outline"} onClick={start} disabled={isStarting}>
              {isStarting ? "Starting…" : isNotConnected ? "Connect your bank" : "Reconnect"}
            </Button>
          )}
        </div>

        {(phase === "waiting" || phase === "error") && (
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              {phase === "waiting" ? (
                <Loader2 className="size-3.5 shrink-0 animate-spin" />
              ) : (
                <ExternalLink className="size-3.5 shrink-0" />
              )}
              {phase === "waiting"
                ? "Waiting for you to finish authorizing in the new tab…"
                : "The KBC authorization page opened in a new tab. Approve access there, then try again."}
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={cancel}>
                Cancel
              </Button>
            </div>
            {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
          </div>
        )}

        {phase === "idle" && errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
      </CardContent>
    </Card>
  )
}
