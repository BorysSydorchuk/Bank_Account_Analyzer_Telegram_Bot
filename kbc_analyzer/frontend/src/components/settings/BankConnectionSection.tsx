import { CheckCircle2, ExternalLink, OctagonAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useEnableBankingReconnect } from "@/hooks/useEnableBankingReconnect"
import { useEnableBankingStatus } from "@/hooks/useEnableBankingStatus"

export function BankConnectionSection() {
  const { data } = useEnableBankingStatus()
  const { phase, pastedUrl, setPastedUrl, errorMessage, start, verify, cancel, isStarting } =
    useEnableBankingReconnect()

  const isActive = data?.status === "active"
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
            {!data ? (
              <span className="text-text-secondary">Checking connection…</span>
            ) : phase === "success" || isActive ? (
              <>
                <CheckCircle2 className="size-4 text-success" />
                <span className="text-text-primary">
                  {phase === "success"
                    ? "Reconnected — connection is active."
                    : expiresAtLabel
                      ? `Active — expires ${expiresAtLabel}.`
                      : "Active."}
                </span>
              </>
            ) : (
              <>
                <OctagonAlert className="size-4 text-danger" />
                <span className="text-text-primary">Expired — sync won't work until reconnected.</span>
              </>
            )}
          </div>
          {phase === "idle" && (
            <Button size="sm" variant="outline" onClick={start} disabled={isStarting}>
              {isStarting ? "Starting…" : "Reconnect"}
            </Button>
          )}
        </div>

        {(phase === "awaiting-paste" || phase === "verifying" || phase === "error") && (
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              <ExternalLink className="size-3.5 shrink-0" />
              The KBC authorization page opened in a new tab. After you approve access, that tab
              will show an address starting with{" "}
              <code className="rounded bg-black/5 px-1">https://localhost/callback?code=…</code> — copy that
              full address and paste it here.
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={pastedUrl}
                onChange={(e) => setPastedUrl(e.target.value)}
                placeholder="https://localhost/callback?code=...&state=..."
                className="h-8 flex-1 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
              <Button size="sm" onClick={verify} disabled={!pastedUrl || phase === "verifying"}>
                {phase === "verifying" ? "Verifying…" : "I've authorized"}
              </Button>
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
