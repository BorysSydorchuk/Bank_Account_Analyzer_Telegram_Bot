import { CheckCircle2, ExternalLink, Landmark, Loader2, MailWarning, OctagonAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useEnableBankingReconnect } from "@/hooks/useEnableBankingReconnect"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"
import type { EnableBankingStatus } from "@/lib/types"

// S8-01: the bank picker. GET /api/auth/enable-banking/status already
// returns one entry per bank Mymble supports (app/institutions.py),
// including "not_connected" ones — so this component just renders that
// list, one row per entry. Adding a third bank later is exactly the data
// change the ticket asked for: one more line in institutions.py, nothing
// here changes.
export function BankConnectionSection() {
  const { data, isError } = useEnableBankingStatus()
  const { phase, errorMessage, activeInstitution, start, cancel, isStarting } = useEnableBankingReconnect()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Bank Connection</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isError ? (
          // S7-09: require_verified_email's 403 — without this branch,
          // !data below is permanently true for an unverified account and
          // this card is stuck on "Checking connection…" forever. Same fix
          // as SessionBanner.tsx.
          <div className="flex items-center gap-2 text-sm">
            <MailWarning className="size-4 text-warning" />
            <span className="text-text-primary">Verify your email to connect a bank account.</span>
          </div>
        ) : !data ? (
          <span className="text-sm text-text-secondary">Checking connection…</span>
        ) : (
          data.map((bankStatus) => (
            <BankRow
              key={bankStatus.institution}
              bankStatus={bankStatus}
              isThisRowActive={activeInstitution === bankStatus.institution}
              phase={activeInstitution === bankStatus.institution ? phase : "idle"}
              errorMessage={activeInstitution === bankStatus.institution ? errorMessage : null}
              isStarting={isStarting && activeInstitution === bankStatus.institution}
              onStart={() => start(bankStatus.institution)}
              onCancel={cancel}
            />
          ))
        )}
      </CardContent>
    </Card>
  )
}

interface BankRowProps {
  bankStatus: EnableBankingStatus
  isThisRowActive: boolean
  phase: "idle" | "waiting" | "success" | "error"
  errorMessage: string | null
  isStarting: boolean
  onStart: () => void
  onCancel: () => void
}

function BankRow({ bankStatus, phase, errorMessage, isStarting, onStart, onCancel }: BankRowProps) {
  const isActive = bankStatus.status === "active" || phase === "success"
  const isNotConnected = bankStatus.status === "not_connected" && phase !== "success"
  const expiresAtLabel = bankStatus.expires_at
    ? new Date(bankStatus.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          {phase === "success" || isActive ? (
            <>
              <CheckCircle2 className="size-4 text-success" />
              <span className="text-text-primary">
                <span className="font-medium">{bankStatus.institution}</span>
                {" — "}
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
              <span className="text-text-primary">
                <span className="font-medium">{bankStatus.institution}</span> — not connected.
              </span>
            </>
          ) : (
            <>
              <OctagonAlert className="size-4 text-danger" />
              <span className="text-text-primary">
                <span className="font-medium">{bankStatus.institution}</span> — expired, sync won't work until
                reconnected.
              </span>
            </>
          )}
        </div>
        {phase === "idle" && (
          <Button size="sm" variant={isNotConnected ? "default" : "outline"} onClick={onStart} disabled={isStarting}>
            {isStarting ? "Starting…" : isNotConnected ? "Connect" : "Reconnect"}
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
              : `The ${bankStatus.institution} authorization page opened in a new tab. Approve access there, then try again.`}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>
          {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
        </div>
      )}

      {phase === "idle" && errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
    </div>
  )
}
