import { useState } from "react"
import { format, parseISO } from "date-fns"
import { CalendarIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { DATE_RANGE_PRESETS, type DateRangePreset } from "@/lib/dateRangePresets"

function toDate(iso: string): Date {
  return parseISO(iso)
}

interface DateRangePickerProps {
  dateFrom: string
  dateTo: string
  // Split in two (rather than one onChange) because callers care about the
  // difference: SyncControls auto-syncs on a preset click but not on a manual
  // calendar pick, while a plain listing page (S2-07) can treat both the same.
  onPresetSelect: (preset: DateRangePreset) => void
  onManualChange: (dateFrom: string, dateTo: string) => void
  disabled?: boolean
}

// Extracted from SyncControls (S1-05) so a second page (Transactions, S2-07)
// can reuse the exact same presets/calendar UI without depending on
// useDashboard's sync-mutation-specific selectPreset/updateRange.
export function DateRangePicker({ dateFrom, dateTo, onPresetSelect, onManualChange, disabled }: DateRangePickerProps) {
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
    onManualChange(nextFrom, nextTo)
    setFromOpen(false)
  }

  function handleToSelect(date: Date | undefined) {
    if (!date) return
    const nextTo = format(date, "yyyy-MM-dd")
    const nextFrom = date < fromDate ? nextTo : dateFrom
    onManualChange(nextFrom, nextTo)
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
            onClick={() => onPresetSelect(preset)}
            disabled={disabled}
          >
            {preset.label}
          </Button>
        ))}
      </div>

      <Popover open={fromOpen} onOpenChange={setFromOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1.5" disabled={disabled}>
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
          <Button variant="outline" size="sm" className="gap-1.5" disabled={disabled}>
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
    </div>
  )
}
