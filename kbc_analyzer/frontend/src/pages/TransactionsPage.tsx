import { useMemo, useState } from "react"
import { format, parseISO } from "date-fns"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { DateRangePicker } from "@/components/shared/DateRangePicker"
import { CategoryFilterDropdown } from "@/components/transactions/CategoryFilterDropdown"
import { TransactionsTable } from "@/components/transactions/TransactionsTable"
import { useCategories } from "@/hooks/useCategories"
import { useCategoryOptions } from "@/hooks/useCategoryOptions"
import { useDateRangeParam } from "@/hooks/useDateRangeParam"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { useTransactionSearch } from "@/hooks/useTransactionSearch"
import { useTransactionsList } from "@/hooks/useTransactionsList"
import { getThisMonthRange, type DateRangePreset } from "@/lib/dateRangePresets"
import type { AmountFilter } from "@/lib/types"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300

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
  // The full categories table (S3-01), not just categories present in this
  // date range — this is what lets a category like "Income" (never part of
  // by_category, see useCategoryOptions) still get a real pill color.
  const { data: categoryList } = useCategories()
  const colorByCategory = useMemo(
    () => new Map((categoryList ?? []).map((c) => [c.name, c.color])),
    [categoryList]
  )

  const { data, isLoading } = useTransactionsList(dateFrom, dateTo, page, PAGE_SIZE, categories, amountType)

  // S3-07 Item 4: search now goes to GET /api/transactions/search — across
  // every synced transaction, not just whatever page/date-range/category
  // filters happen to be active — instead of filtering the current page's
  // 50 rows client-side (the old S2-07 behavior).
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS)
  const isSearching = debouncedSearch.trim().length > 0

  const subtitle = isSearching
    ? undefined
    : data
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
                placeholder="Search all transactions..."
                className="h-7 min-w-[180px] flex-1 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>

            {isSearching ? (
              <SearchResults query={debouncedSearch} colorByCategory={colorByCategory} categoryList={categoryList} />
            ) : (
              <>
                {isLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <Skeleton key={i} className="h-9 w-full" />
                    ))}
                  </div>
                ) : (data?.transactions.length ?? 0) === 0 ? (
                  <div className="flex min-h-[200px] items-center justify-center text-sm text-text-secondary">
                    No transactions found for the selected filters.
                  </div>
                ) : (
                  <TransactionsTable
                    transactions={data?.transactions ?? []}
                    colorByCategory={colorByCategory}
                    categories={categoryList ?? []}
                  />
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
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </>
  )
}

function SearchResults({
  query,
  colorByCategory,
  categoryList,
}: {
  query: string
  colorByCategory: Map<string, string>
  categoryList: ReturnType<typeof useCategories>["data"]
}) {
  const { data, isLoading } = useTransactionSearch(query)

  if (isLoading) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center gap-2 text-sm text-text-secondary">
        <span>Searching all transactions...</span>
      </div>
    )
  }

  if (!data || data.transactions.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-text-secondary">
        No transactions found for &quot;{query}&quot;.
      </div>
    )
  }

  return (
    <>
      <p className="text-xs text-text-secondary">
        {data.total} match{data.total === 1 ? "" : "es"} for &quot;{query}&quot; across all transactions
      </p>
      <TransactionsTable
        transactions={data.transactions}
        colorByCategory={colorByCategory}
        categories={categoryList ?? []}
      />
    </>
  )
}
