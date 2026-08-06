import { useEffect, useState } from "react"

import type { SyncResponse } from "@/lib/types"

interface SyncStatusProps {
  isSyncing: boolean
  lastSyncResult: SyncResponse | null
  // The currently configured provider (from Settings) — known before this
  // sync's own response comes back, which is the only way to label the
  // "Categorizing with..." stage while it's still in flight.
  provider: string | null
}

function providerLabel(provider: string | null) {
  if (!provider) return "your provider"
  return provider.charAt(0).toUpperCase() + provider.slice(1)
}

// The backend runs fetch → categorize → insights as one atomic request
// (S2-05/S2-06), so there's no real per-stage signal to observe from here.
// These three labels are a timed approximation of that fixed, known pipeline
// order — not live telemetry — and always resolve to a real, unfabricated
// summary (SyncResponse's own counts) the moment the response actually
// arrives, however long that took.
export function SyncStatus({ isSyncing, lastSyncResult, provider }: SyncStatusProps) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    if (!isSyncing) {
      setStage(0)
      return
    }
    const timers = [setTimeout(() => setStage(1), 2500), setTimeout(() => setStage(2), 5500)]
    return () => timers.forEach(clearTimeout)
  }, [isSyncing])

  if (isSyncing) {
    const stages = ["Fetching transactions...", `Categorizing with ${providerLabel(provider)}...`, "Generating insights..."]
    return <p className="text-xs text-text-secondary">{stages[stage]}</p>
  }

  if (lastSyncResult) {
    const { fetched, insights } = lastSyncResult
    return (
      <p className="text-xs text-text-secondary">
        Done — {fetched} transaction{fetched === 1 ? "" : "s"}, {insights.length} insight
        {insights.length === 1 ? "" : "s"}
      </p>
    )
  }

  return null
}
