import type { ReactNode } from "react"
import { format, parseISO } from "date-fns"
import { useMutationState } from "@tanstack/react-query"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useStatistics } from "@/hooks/useStatistics"
import { cn } from "@/lib/utils"

interface SummaryCardsProps {
  dateFrom: string
  dateTo: string
  isSyncing: boolean
}

const currencyFormatter = new Intl.NumberFormat("de-BE", {
  style: "currency",
  currency: "EUR",
})

function formatAmount(value: number | undefined) {
  return currencyFormatter.format(value ?? 0)
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

export function SummaryCards({ dateFrom, dateTo, isSyncing }: SummaryCardsProps) {
  // enabled: false — reads whatever useDashboard's sync mutation already put
  // in the cache under this key, never fetches on its own.
  const { data } = useStatistics(dateFrom, dateTo)
  const summary = data?.summary

  // Same mutation useDashboard's sync button runs, observed by key rather
  // than re-invoked — that's how this reflects a failed sync without making
  // any network call of its own.
  const mutations = useMutationState({ filters: { mutationKey: ["syncStatistics"] } })
  const lastMutation = mutations[mutations.length - 1]
  const hasError = !isSyncing && lastMutation?.status === "error"
  const isEmpty = !isSyncing && !hasError && (!summary || summary.transaction_count === 0)

  const errorSubtitle = summary ? "Couldn't refresh — showing last synced data" : "Couldn't load data"

  const net = summary?.net ?? 0
  const netColorClass = isEmpty
    ? "text-primary"
    : net > 0
      ? "text-success"
      : net < 0
        ? "text-danger"
        : "text-primary"

  const expense = summary?.biggest_expense ?? null

  return (
    <div className="grid grid-cols-4 gap-6">
      <StatCard title="Total Spent" loading={isSyncing}>
        <p className="text-2xl font-semibold text-danger">{formatAmount(summary?.total_spent)}</p>
        <p className={cn("mt-1 text-sm", hasError ? "text-danger" : "text-text-secondary")}>
          {hasError
            ? errorSubtitle
            : isEmpty
              ? "No data for this period"
              : `across ${summary?.transaction_count ?? 0} transactions`}
        </p>
      </StatCard>

      <StatCard title="Total Received" loading={isSyncing}>
        <p className="text-2xl font-semibold text-success">{formatAmount(summary?.total_received)}</p>
        <p className={cn("mt-1 text-sm", hasError ? "text-danger" : "text-text-secondary")}>
          {hasError ? errorSubtitle : isEmpty ? "No data for this period" : "income & transfers"}
        </p>
      </StatCard>

      <StatCard title="Net Balance" loading={isSyncing}>
        <p className={cn("text-2xl font-semibold", netColorClass)}>{formatAmount(net)}</p>
        <p className={cn("mt-1 text-sm", hasError ? "text-danger" : "text-text-secondary")}>
          {hasError ? errorSubtitle : isEmpty ? "No data for this period" : "for this period"}
        </p>
      </StatCard>

      <StatCard title="Biggest Expense" loading={isSyncing}>
        <p className="text-2xl font-semibold text-danger">{formatAmount(expense?.amount)}</p>
        <p className="mt-1 truncate text-sm text-text-primary">
          {hasError ? errorSubtitle : isEmpty || !expense?.description ? "No data for this period" : truncate(expense.description, 24)}
        </p>
        {!hasError && !isEmpty && expense && (
          <p className="mt-0.5 text-xs text-text-secondary">{format(parseISO(expense.date), "d MMM yyyy")}</p>
        )}
      </StatCard>
    </div>
  )
}

function StatCard({ title, loading, children }: { title: string; loading: boolean; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs font-medium tracking-wide text-text-secondary uppercase">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-4 w-36" />
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}