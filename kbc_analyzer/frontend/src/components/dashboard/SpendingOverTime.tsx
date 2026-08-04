import { useMemo, useState } from "react"
import { differenceInCalendarDays, format, isMonday, parseISO } from "date-fns"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useStatistics } from "@/hooks/useStatistics"
import { resolveCssVar } from "@/lib/cssVar"
import { formatAmount, formatAmountCompact } from "@/lib/format"
import type { DayStat, WeekStat } from "@/lib/types"

interface SpendingOverTimeProps {
  dateFrom: string
  dateTo: string
  isSyncing: boolean
}

// Above this many days, one tick per day would collide into an unreadable
// smear — fall back to week-start (Monday) ticks only.
const DAILY_TICK_DENSITY_THRESHOLD = 60

const CHART_HEIGHT = 280

type ChartView = "daily" | "weekly"

interface ChartColors {
  danger: string
  success: string
  border: string
  mutedForeground: string
  muted: string
}

export function SpendingOverTime({ dateFrom, dateTo, isSyncing }: SpendingOverTimeProps) {
  const { data } = useStatistics(dateFrom, dateTo)
  const byDay = data?.by_day ?? []
  const byWeek = data?.by_week ?? []

  const [view, setView] = useState<ChartView>("daily")

  // Resolved once to real hex/oklch values — Recharts renders these as SVG
  // presentation attributes, and a plain `var(--x)` string handed to Cell/
  // Bar/Area fill has already bitten this codebase once (S1-07's donut) when
  // the referenced token turned out not to be a real emitted CSS variable.
  // Resolving through getComputedStyle here sidesteps that class of bug.
  const colors: ChartColors = useMemo(
    () => ({
      danger: resolveCssVar("var(--danger)"),
      success: resolveCssVar("var(--success)"),
      border: resolveCssVar("var(--border)"),
      mutedForeground: resolveCssVar("var(--muted-foreground)"),
      muted: resolveCssVar("var(--muted)"),
    }),
    []
  )

  const rangeDays = differenceInCalendarDays(parseISO(dateTo), parseISO(dateFrom)) + 1
  const showEveryDailyTick = rangeDays <= DAILY_TICK_DENSITY_THRESHOLD
  const dailyTicks = showEveryDailyTick
    ? undefined
    : byDay.filter((d) => isMonday(parseISO(d.date))).map((d) => d.date)

  const isEmpty = !isSyncing && byDay.length === 0

  return (
    <Card className="mt-6">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold text-text-primary">Spending Over Time</CardTitle>
        <div className="flex items-center gap-1">
          <Button
            variant={view === "daily" ? "default" : "outline"}
            size="sm"
            onClick={() => setView("daily")}
          >
            Daily
          </Button>
          <Button
            variant={view === "weekly" ? "default" : "outline"}
            size="sm"
            onClick={() => setView("weekly")}
          >
            Weekly
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isSyncing ? (
          <Skeleton style={{ height: CHART_HEIGHT }} className="w-full" />
        ) : isEmpty ? (
          <div
            style={{ height: CHART_HEIGHT }}
            className="flex items-center justify-center text-sm text-text-secondary"
          >
            No spending data for this period.
          </div>
        ) : view === "daily" ? (
          <DailyChart data={byDay} ticks={dailyTicks} colors={colors} />
        ) : (
          <WeeklyChart data={byWeek} colors={colors} />
        )}
      </CardContent>
    </Card>
  )
}

function DailyChart({
  data,
  ticks,
  colors,
}: {
  data: DayStat[]
  ticks: string[] | undefined
  colors: ChartColors
}) {
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={colors.border} />
        <XAxis
          dataKey="date"
          ticks={ticks}
          interval={ticks ? undefined : 0}
          tickFormatter={(value: string) => format(parseISO(value), "dd MMM")}
          tick={{ fontSize: 11, fill: colors.mutedForeground }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(value: number) => formatAmountCompact(value)}
          tick={{ fontSize: 11, fill: colors.mutedForeground }}
          axisLine={false}
          tickLine={false}
          width={72}
        />
        <Tooltip content={<DailyTooltip />} cursor={{ fill: colors.muted }} />
        <Bar dataKey="spent" fill={colors.danger} radius={[2, 2, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function DailyTooltip({ active, payload }: { active?: boolean; payload?: { payload: DayStat }[] }) {
  if (!active || !payload?.length) return null
  const day = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md">
      <div className="text-xs font-medium text-text-secondary">{format(parseISO(day.date), "dd MMM yyyy")}</div>
      <div className="mt-1 text-sm font-semibold text-danger">Spent: {formatAmount(day.spent)}</div>
      <div className="text-sm font-semibold text-success">Received: {formatAmount(day.received)}</div>
    </div>
  )
}

function WeeklyChart({ data, colors }: { data: WeekStat[]; colors: ChartColors }) {
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={colors.border} />
        <XAxis
          dataKey="week"
          tick={{ fontSize: 11, fill: colors.mutedForeground }}
          axisLine={{ stroke: colors.border }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(value: number) => formatAmountCompact(value)}
          tick={{ fontSize: 11, fill: colors.mutedForeground }}
          axisLine={false}
          tickLine={false}
          width={72}
        />
        <Tooltip content={<WeeklyTooltip />} cursor={{ stroke: colors.border }} />
        <Area
          type="monotone"
          dataKey="spent"
          stroke={colors.danger}
          strokeWidth={2}
          fill={colors.danger}
          fillOpacity={0.15}
          dot={{ r: 4, fill: colors.danger, strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
        <Area
          type="monotone"
          dataKey="received"
          stroke={colors.success}
          strokeWidth={2}
          fill={colors.success}
          fillOpacity={0.15}
          dot={{ r: 4, fill: colors.success, strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function WeeklyTooltip({ active, payload }: { active?: boolean; payload?: { payload: WeekStat }[] }) {
  if (!active || !payload?.length) return null
  const week = payload[0].payload
  const net = week.received - week.spent
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md">
      <div className="text-xs font-medium text-text-secondary">
        {week.week} · {week.date_range}
      </div>
      <div className="mt-1 text-sm font-semibold text-danger">Spent: {formatAmount(week.spent)}</div>
      <div className="text-sm font-semibold text-success">Received: {formatAmount(week.received)}</div>
      <div className={`text-sm font-semibold ${net >= 0 ? "text-success" : "text-danger"}`}>
        Net: {formatAmount(net)}
      </div>
    </div>
  )
}
