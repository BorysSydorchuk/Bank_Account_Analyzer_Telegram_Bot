import { useState } from "react"
import { format, parseISO } from "date-fns"
import { CalendarIcon, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { DATE_RANGE_PRESETS } from "@/lib/dateRangePresets"
import type { useDashboard } from "@/hooks/useDashboard"

function toDate(iso: string): Date {
  return parseISO(iso)
}

// Takes useDashboard's return value as props rather than calling the hook
// itself — the hook owns a mount-time auto-sync effect, so a second instance
// here would fire a second, duplicate POST /sync on every page load.
type SyncControlsProps = ReturnType<typeof useDashboard>

export function SyncControls({ dateFrom, dateTo, updateRange, selectPreset, syncNow, isSyncing }: SyncControlsProps) {
  const [fromOpen, setFromOpen] = useState(false)
  const [toOpen, setToOpen] = useState(false)

  const fromDate = toDate(dateFrom)
  const toDateValue = toDate(dateTo)

  function handleFromSelect(date: Date | undefined) {
    if (!date) return
    const nextFrom = format(date, "yyyy-MM-dd")
    // Enforced here too (not just via `disabled` below): if "from" ever ended
    // up after "to", pull "to" up to match rather than allow an invalid range.
    const nextTo = date > toDateValue ? nextFrom : dateTo
    updateRange(nextFrom, nextTo)
    setFromOpen(false)
  }

  function handleToSelect(date: Date | undefined) {
    if (!date) return
    const nextTo = format(date, "yyyy-MM-dd")
    const nextFrom = date < fromDate ? nextTo : dateFrom
    updateRange(nextFrom, nextTo)
    setToOpen(false)
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        {DATE_RANGE_PRESETS.map((preset) => (
          <Button
            key={preset.label}
            variant="outline"
            size="sm"
            onClick={() => selectPreset(preset)}
            disabled={isSyncing}
          >
            {preset.label}
          </Button>
        ))}
      </div>

      <Popover open={fromOpen} onOpenChange={setFromOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1.5" disabled={isSyncing}>
            <CalendarIcon className="size-3.5" />
            {format(fromDate, "MMM d, yyyy")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0">
          <Calendar
            mode="single"
            selected={fromDate}
            onSelect={handleFromSelect}
            defaultMonth={fromDate}
            // "from" cannot be after "to" — enforced in the UI by disabling
            // the dates, not just by validating after the fact.
            disabled={{ after: toDateValue }}
          />
        </PopoverContent>
      </Popover>

      <span className="text-sm text-text-secondary">–</span>

      <Popover open={toOpen} onOpenChange={setToOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1.5" disabled={isSyncing}>
            <CalendarIcon className="size-3.5" />
            {format(toDateValue, "MMM d, yyyy")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0">
          <Calendar
            mode="single"
            selected={toDateValue}
            onSelect={handleToSelect}
            defaultMonth={toDateValue}
            disabled={{ before: fromDate }}
          />
        </PopoverContent>
      </Popover>

      <Button className="gap-1.5" onClick={syncNow} disabled={isSyncing}>
        {isSyncing && <Loader2 className="size-4 animate-spin" />}
        Sync &amp; Analyze
      </Button>
    </div>
  )
}
