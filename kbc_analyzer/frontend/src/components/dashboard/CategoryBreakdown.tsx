import { useMemo, useRef, useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useStatistics } from "@/hooks/useStatistics"
import { assignCategoryColors } from "@/lib/categoryColors"
import { formatAmount } from "@/lib/format"
import type { CategoryStat } from "@/lib/types"
import { cn } from "@/lib/utils"

interface CategoryBreakdownProps {
  dateFrom: string
  dateTo: string
  isSyncing: boolean
}

// Categories the LLM taxonomy defines as having subcategories — shown with a
// chevron even before any transaction has a subcategory value, so "Other"
// looks like an intentional drill-down rather than a dead end. Any category
// that DOES carry subcategory data (subcategories.length > 0) also gets one,
// so this isn't the only way in once the LLM sprint backfills more categories.
const KNOWN_EXPANDABLE_CATEGORIES = new Set(["Other", "Traveling"])

function isExpandable(category: CategoryStat) {
  return KNOWN_EXPANDABLE_CATEGORIES.has(category.category) || category.subcategories.length > 0
}

// Resolves a CSS custom property to its actual computed color so it can be
// handed to Recharts' SVG <Cell fill>, which (unlike a plain DOM element's
// style) can't reliably resolve var() itself. index.css stays the one place
// the hex values are written.
function resolveCssVar(name: string): string {
  if (typeof window === "undefined") return "#94a3b8"
  const match = /var\((--[\w-]+)\)/.exec(name)
  if (!match) return name
  const value = getComputedStyle(document.documentElement).getPropertyValue(match[1]).trim()
  return value || "#94a3b8"
}

interface Slice extends CategoryStat {
  color: string
}

export function CategoryBreakdown({ dateFrom, dateTo, isSyncing }: CategoryBreakdownProps) {
  const { data } = useStatistics(dateFrom, dateTo)
  const categories = useMemo(
    () => (data?.by_category ?? []).filter((c) => c.total > 0),
    [data]
  )
  const totalSpent = data?.summary.total_spent ?? 0

  const slices: Slice[] = useMemo(() => {
    const colorByCategory = assignCategoryColors(categories.map((c) => c.category))
    return categories.map((c) => ({ ...c, color: resolveCssVar(colorByCategory.get(c.category)!) }))
  }, [categories])

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const rowRefs = useRef<Map<string, HTMLLIElement>>(new Map())

  function toggleExpanded(category: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(category)) next.delete(category)
      else next.add(category)
      return next
    })
  }

  function handleSliceClick(category: string) {
    setSelectedCategory(category)
    rowRefs.current.get(category)?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }

  const isEmpty = !isSyncing && categories.length === 0
  const maxTotal = slices.reduce((max, c) => Math.max(max, c.total), 0)

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Spending by Category</CardTitle>
      </CardHeader>
      <CardContent>
        {isSyncing ? (
          <div className="grid min-h-[300px] grid-cols-2 gap-8">
            <div className="flex items-center justify-center">
              <Skeleton className="size-48 rounded-full" />
            </div>
            <div className="space-y-3 py-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          </div>
        ) : isEmpty ? (
          <div className="flex min-h-[300px] items-center justify-center text-sm text-text-secondary">
            No spending data for this period.
          </div>
        ) : (
          <div className="grid min-h-[300px] grid-cols-2 gap-8">
            <div className="relative">
              <ResponsiveContainer width="100%" height="100%" minHeight={300}>
                <PieChart>
                  <Pie
                    data={slices}
                    dataKey="total"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius="60%"
                    outerRadius="90%"
                    paddingAngle={slices.length > 1 ? 2 : 0}
                    stroke="none"
                    onMouseEnter={(_, index) => setHoveredIndex(index)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    onClick={(_, index) => handleSliceClick(slices[index].category)}
                    style={{ cursor: "pointer" }}
                  >
                    {slices.map((slice, index) => (
                      <Cell
                        key={slice.category}
                        fill={slice.color}
                        opacity={hoveredIndex === null || hoveredIndex === index ? 1 : 0.45}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CategoryTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-semibold text-text-primary">{formatAmount(totalSpent)}</span>
                <span className="text-sm text-text-secondary">Total Spent</span>
              </div>
            </div>

            <ul className="flex max-h-[340px] flex-col justify-center gap-1 overflow-y-auto">
              {slices.map((category) => (
                <CategoryRow
                  key={category.category}
                  category={category}
                  maxTotal={maxTotal}
                  selected={selectedCategory === category.category}
                  expandable={isExpandable(category)}
                  isExpanded={expanded.has(category.category)}
                  onToggleExpanded={() => toggleExpanded(category.category)}
                  registerRef={(el) => {
                    if (el) rowRefs.current.set(category.category, el)
                    else rowRefs.current.delete(category.category)
                  }}
                />
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function CategoryTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: { payload: Slice }[]
}) {
  if (!active || !payload?.length) return null
  const slice = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md">
      <div className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
        <span className="inline-block size-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
        {slice.category}
      </div>
      <div className="mt-1 text-sm font-semibold text-text-primary">{formatAmount(slice.total)}</div>
      <div className="text-xs text-text-secondary">{slice.percentage}% of total spent</div>
    </div>
  )
}

function CategoryRow({
  category,
  maxTotal,
  selected,
  expandable,
  isExpanded,
  onToggleExpanded,
  registerRef,
}: {
  category: Slice
  maxTotal: number
  selected: boolean
  expandable: boolean
  isExpanded: boolean
  onToggleExpanded: () => void
  registerRef: (el: HTMLLIElement | null) => void
}) {
  const widthPct = maxTotal > 0 ? (category.total / maxTotal) * 100 : 0

  return (
    <li
      ref={registerRef}
      className={cn(
        "rounded-lg px-2 py-1.5 transition-colors",
        selected && "bg-primary/10 ring-1 ring-primary/40"
      )}
    >
      <div className="flex items-center gap-3">
        <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: category.color }} />
        <span className="w-28 shrink-0 truncate text-sm text-text-primary">{category.category}</span>
        <div className="relative h-2 flex-1 overflow-hidden rounded-full">
          <div className="absolute inset-0 rounded-full" style={{ backgroundColor: category.color, opacity: 0.2 }} />
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{ width: `${widthPct}%`, backgroundColor: category.color }}
          />
        </div>
        <span className="w-20 shrink-0 text-right text-sm text-text-primary">{formatAmount(category.total)}</span>
        <span className="w-12 shrink-0 text-right text-xs text-text-secondary">{category.percentage}%</span>
        {expandable ? (
          <button
            type="button"
            onClick={onToggleExpanded}
            aria-label={isExpanded ? `Collapse ${category.category}` : `Expand ${category.category}`}
            className="shrink-0 rounded p-0.5 text-text-secondary hover:bg-muted hover:text-text-primary"
          >
            {isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </button>
        ) : (
          <span className="size-4 shrink-0" />
        )}
      </div>

      {expandable && isExpanded && (
        <ul className="mt-1.5 ml-4 flex flex-col gap-1 border-l border-border pl-3">
          {category.subcategories.length === 0 ? (
            <li className="py-1 text-xs text-text-secondary">No subcategory data yet</li>
          ) : (
            category.subcategories.map((sub) => (
              <li key={sub.category} className="flex items-center gap-3">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: `color-mix(in srgb, ${category.color} 55%, white)` }}
                />
                <span className="w-24 shrink-0 truncate text-xs text-text-primary">{sub.category}</span>
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full">
                  <div
                    className="absolute inset-0 rounded-full"
                    style={{ backgroundColor: category.color, opacity: 0.15 }}
                  />
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${category.total > 0 ? (sub.total / category.total) * 100 : 0}%`,
                      backgroundColor: `color-mix(in srgb, ${category.color} 55%, white)`,
                    }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right text-xs text-text-primary">{formatAmount(sub.total)}</span>
                <span className="w-10 shrink-0 text-right text-[11px] text-text-secondary">{sub.percentage}%</span>
              </li>
            ))
          )}
        </ul>
      )}
    </li>
  )
}