import { useState } from "react"
import { format, parseISO } from "date-fns"
import { ChevronDown, ChevronUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { DateRangePicker } from "@/components/shared/DateRangePicker"
import { useCompareInsights } from "@/hooks/useCompareInsights"
import { formatAmount } from "@/lib/format"
import { getLastMonthRange, getThisMonthRange, type DateRange, type DateRangePreset } from "@/lib/dateRangePresets"
import type { ComparisonResponse, PeriodComparison } from "@/lib/types"
import { cn } from "@/lib/utils"

// Collapsed on every page load (S4-08) — deliberately plain useState, no
// persistence, so a refresh always starts from "collapsed" regardless of
// what the user left it as.
export function ComparePeriodsSection() {
  const [expanded, setExpanded] = useState(false)
  const [periodA, setPeriodA] = useState<DateRange>(getLastMonthRange)
  const [periodB, setPeriodB] = useState<DateRange>(getThisMonthRange)
  const compare = useCompareInsights()

  function runCompare() {
    compare.mutate({
      periodAFrom: periodA.dateFrom,
      periodATo: periodA.dateTo,
      periodBFrom: periodB.dateFrom,
      periodBTo: periodB.dateTo,
    })
  }

  return (
    <Card className="mt-6">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full cursor-pointer items-center justify-between px-6 py-4 text-left"
      >
        <span className="text-base font-semibold text-text-primary">Compare two periods</span>
        {expanded ? (
          <ChevronUp className="size-4 text-text-secondary" />
        ) : (
          <ChevronDown className="size-4 text-text-secondary" />
        )}
      </button>

      {expanded && (
        <CardContent className="flex flex-col gap-4 pt-0">
          <div className="flex flex-wrap items-end gap-4">
            <PeriodPicker
              label="Period A"
              range={periodA}
              onPresetSelect={(preset) => setPeriodA(preset.range())}
              onManualChange={(dateFrom, dateTo) => setPeriodA({ dateFrom, dateTo })}
            />
            <PeriodPicker
              label="Period B"
              range={periodB}
              onPresetSelect={(preset) => setPeriodB(preset.range())}
              onManualChange={(dateFrom, dateTo) => setPeriodB({ dateFrom, dateTo })}
            />
            <Button onClick={runCompare} disabled={compare.isPending}>
              {compare.isPending ? "Comparing..." : "Compare"}
            </Button>
          </div>

          {compare.data && <ComparisonResults data={compare.data} />}
        </CardContent>
      )}
    </Card>
  )
}

function PeriodPicker({
  label,
  range,
  onPresetSelect,
  onManualChange,
}: {
  label: string
  range: DateRange
  onPresetSelect: (preset: DateRangePreset) => void
  onManualChange: (dateFrom: string, dateTo: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-text-secondary">{label}</span>
      <DateRangePicker
        dateFrom={range.dateFrom}
        dateTo={range.dateTo}
        onPresetSelect={onPresetSelect}
        onManualChange={onManualChange}
      />
    </div>
  )
}

function ChangeIndicator({ change, changePct }: { change: number; changePct: number | null }) {
  if (change === 0) {
    return <span className="text-sm text-text-secondary">No change</span>
  }
  // Spending increase is the "bad" direction (red), decrease is "good"
  // (green) — matches the budget status colors used everywhere else.
  const isIncrease = change > 0
  return (
    <span className={cn("text-sm font-semibold", isIncrease ? "text-danger" : "text-success")}>
      {isIncrease ? "▲" : "▼"} {formatAmount(Math.abs(change))}
      {changePct !== null && ` (${isIncrease ? "+" : ""}${changePct}%)`}
    </span>
  )
}

function ComparisonResults({ data }: { data: ComparisonResponse }) {
  const { period_a, period_b, delta } = data
  const hasInsights = period_a.insights.length > 0 || period_b.insights.length > 0

  return (
    <div className="flex flex-col gap-4 border-t border-border pt-4">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <div className="text-center">
          <p className="text-xs text-text-secondary">{period_a.date_range}</p>
          <p className="text-xl font-semibold text-text-primary">{formatAmount(period_a.total_spent)}</p>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <ChangeIndicator change={delta.total_spent_change} changePct={delta.total_spent_change_pct} />
          <span className="text-[11px] text-text-secondary">vs previous period</span>
        </div>
        <div className="text-center">
          <p className="text-xs text-text-secondary">{period_b.date_range}</p>
          <p className="text-xl font-semibold text-text-primary">{formatAmount(period_b.total_spent)}</p>
        </div>
      </div>

      {hasInsights && (
        <div className="grid grid-cols-2 gap-4">
          <InsightsColumn period={period_a} />
          <InsightsColumn period={period_b} />
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-secondary">
            <th className="py-1.5 font-medium">Category</th>
            <th className="py-1.5 text-right font-medium">Period A</th>
            <th className="py-1.5 text-right font-medium">Period B</th>
            <th className="py-1.5 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {delta.category_changes.map((change) => (
            <tr key={change.category} className="border-b border-border last:border-0">
              <td className="py-1.5 text-text-primary">{change.category}</td>
              <td className="py-1.5 text-right text-text-secondary">{formatAmount(change.period_a)}</td>
              <td className="py-1.5 text-right text-text-secondary">{formatAmount(change.period_b)}</td>
              <td className="py-1.5 text-right">
                <ChangeIndicator change={change.change} changePct={change.change_pct} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InsightsColumn({ period }: { period: PeriodComparison }) {
  if (period.insights.length === 0) {
    return <p className="text-xs text-text-secondary">No insights stored for {period.date_range}.</p>
  }
  return (
    <div className="flex flex-col gap-1.5">
      {period.insights_generated_at && (
        <p className="text-[11px] text-text-secondary">
          Generated {format(parseISO(period.insights_generated_at), "d MMM yyyy")}
        </p>
      )}
      {period.insights.map((insight, i) => (
        <div key={i} className="rounded-md border border-border bg-card p-2 text-xs">
          <p className="font-semibold text-text-primary">{insight.title}</p>
          <p className="text-text-secondary">{insight.body}</p>
        </div>
      ))}
    </div>
  )
}
