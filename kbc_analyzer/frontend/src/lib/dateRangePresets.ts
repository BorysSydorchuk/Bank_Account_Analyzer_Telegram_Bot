import { format, startOfMonth, subDays, subMonths } from "date-fns"

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
