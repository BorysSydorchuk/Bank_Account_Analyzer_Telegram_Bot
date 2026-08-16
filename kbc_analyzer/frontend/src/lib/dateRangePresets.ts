import { endOfMonth, format, startOfMonth, subDays, subMonths } from "date-fns"

export interface DateRange {
  dateFrom: string
  dateTo: string
}

export interface DateRangePreset {
  label: string
  range: () => DateRange
}

const iso = (d: Date) => format(d, "yyyy-MM-dd")

export function getThisMonthRange(): DateRange {
  return { dateFrom: iso(startOfMonth(new Date())), dateTo: iso(new Date()) }
}

// S4-08's Compare Periods default for Period A — the full prior calendar
// month, not "30 days ago to today" (getThisMonthRange's own convention:
// this-month always runs to today, so last-month should run to its own
// month-end, not truncate at today's day-of-month).
export function getLastMonthRange(): DateRange {
  const lastMonth = subMonths(new Date(), 1)
  return { dateFrom: iso(startOfMonth(lastMonth)), dateTo: iso(endOfMonth(lastMonth)) }
}

export const DATE_RANGE_PRESETS: DateRangePreset[] = [
  {
    label: "Last 7 days",
    range: () => ({ dateFrom: iso(subDays(new Date(), 6)), dateTo: iso(new Date()) }),
  },
  {
    label: "Last 30 days",
    range: () => ({ dateFrom: iso(subDays(new Date(), 29)), dateTo: iso(new Date()) }),
  },
  {
    label: "Last 3 months",
    range: () => ({ dateFrom: iso(subMonths(new Date(), 3)), dateTo: iso(new Date()) }),
  },
  {
    label: "This month",
    range: getThisMonthRange,
  },
]
