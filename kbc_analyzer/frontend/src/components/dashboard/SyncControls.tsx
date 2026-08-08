import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { DateRangePicker } from "@/components/shared/DateRangePicker"
import type { useDashboard } from "@/hooks/useDashboard"
import { SyncStatus } from "./SyncStatus"

// Takes useDashboard's return value as props rather than calling the hook
// itself — the hook owns a mount-time auto-sync effect, so a second instance
// here would fire a second, duplicate POST /sync on every page load.
type SyncControlsProps = ReturnType<typeof useDashboard>

export function SyncControls({
  dateFrom,
  dateTo,
  updateRange,
  selectPreset,
  syncNow,
  isSyncing,
  statusMessage,
}: SyncControlsProps) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <DateRangePicker
          dateFrom={dateFrom}
          dateTo={dateTo}
          onPresetSelect={selectPreset}
          onManualChange={updateRange}
          disabled={isSyncing}
        />

        <Button className="gap-1.5" onClick={syncNow} disabled={isSyncing}>
          {isSyncing && <Loader2 className="size-4 animate-spin" />}
          Sync &amp; Analyze
        </Button>
      </div>

      <SyncStatus statusMessage={statusMessage} />
    </div>
  )
}
