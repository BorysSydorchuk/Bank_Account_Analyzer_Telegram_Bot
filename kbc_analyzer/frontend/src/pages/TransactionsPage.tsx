import { useMemo, useState } from "react"
import { format, parseISO } from "date-fns"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { DateRangePicker } from "@/components/shared/DateRangePicker"
import { CategoryFilterDropdown } from "@/components/transactions/CategoryFilterDropdown"
import { TransactionsTable } from "@/components/transactions/TransactionsTable"
import { useCategoryOptions } from "@/hooks/useCategoryOptions"
import { useDateRangeParam } from "@/hooks/useDateRangeParam"
import { useTransactionsList } from "@/hooks/useTransactionsList"
import { assignCategoryColors } from "@/lib/categoryColors"
import { getThisMonthRange, type DateRangePreset } from "@/lib/dateRangePresets"
import type { AmountFilter } from "@/lib/types"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 50

const AMOUNT_FILTERS: { value: AmountFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "spent", label: "Spent only" },
  { value: "received", label: "Received only" },
]

export function TransactionsPage() {
  // Its own instance, independent of the Dashboard's — this page has no sync
  // concept, so there's no auto-sync-on-mount effect here to worry about
  // duplicating (unlike useDashboard, safe to call more than once anywhere).
  const { dateFrom: urlFrom, dateTo: urlTo, setRange } = useDateRangeParam()
  const defaultRange = useMemo(() => getThisMonthRange(), [])
  const dateFrom = urlFrom ?? defaultRange.dateFrom
  const dateTo = urlTo ?? defaultRange.dateTo

  const [page, setPage] = useState(1)
  const [categories, setCategories] = useState<string[]>([])
  const [amountType, setAmountType] = useState<AmountFilter>("all")
  const [search, setSearch] = useState("")

  function changeRange(nextFrom: string, nextTo: string) {
    setRange(nextFrom, nextTo)
    setPage(1)
  }

  function changeCategories(next: string[]) {
    setCategories(next)
    setPage(1)
  }

  function changeAmountType(next: AmountFilter) {
    setAmountType(next)
    setPage(1)
  }

  const categoryOptions = useCategoryOptions(dateFrom, dateTo)
  const colorByCategory = useMemo(() => assignCategoryColors(categoryOptions), [categoryOptions])

  const { data, isLoading } = useTransactionsList(dateFrom, dateTo, page, PAGE_SIZE, categories, amountType)

  // Client-side only, on whatever page is currently loaded — see the S2-07
  // WHEN DONE answer for why this doesn't hit the API on every keystroke.
  const visibleTransactions = useMemo(() => {
    const rows = data?.transactions ?? []
    if (!search.trim()) return rows
    const needle = search.toLowerCase()
    return rows.filter((t) => t.description?.toLowerCase().includes(needle))
  }, [data, search])

  const subtitle = data
    ? `${data.total} transaction${data.total === 1 ? "" : "s"} · ${format(parseISO(dateFrom), "MMM d")} – ${format(parseISO(dateTo), "MMM d, yyyy")}`
    : undefined

  return (
    <>
      <header className="flex flex-col gap-0.5 border-b border-border bg-card px-6 py-4">
        <h1 className="text-xl font-semibold text-text-primary">Transactions</h1>
        {subtitle && <p className="text-sm text-text-secondary">{subtitle}</p>}
      </header>
      <main className="flex-1 overflow-y-auto bg-background p-6">
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <DateRangePicker
                dateFrom={dateFrom}
                dateTo={dateTo}
                onPresetSelect={(preset: DateRangePreset) => {
                  const next = preset.range()
                  changeRange(next.dateFrom, next.dateTo)
                }}
                onManualChange={changeRange}
              />
              <CategoryFilterDropdown options={categoryOptions} selected={categories} onChange={changeCategories} />
              <div className="flex items-center gap-1">
                {AMOUNT_FILTERS.map((filter) => (
                  <Button
                    key={filter.value}
                    variant={amountType === filter.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => changeAmountType(filter.value)}
                  >
                    {filter.label}
                  </Button>
                ))}
              </div>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search description..."
                className="h-7 min-w-[180px] flex-1 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>

            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-9 w-full" />
                ))}
              </div>
            ) : visibleTransactions.length === 0 ? (
              <div className="flex min-h-[200px] items-center justify-center text-sm text-text-secondary">
                No transactions found for the selected filters.
              </div>
            ) : (
              <TransactionsTable transactions={visibleTransactions} colorByCategory={colorByCategory} />
            )}

            {data && data.pages > 1 && (
              <div className="flex items-center justify-between pt-2">
                <Button variant="outline" size="sm" onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>
                  Previous
                </Button>
                <span className={cn("text-sm text-text-secondary")}>
                  Page {data.page} of {data.pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= data.pages}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </>
  )
}
