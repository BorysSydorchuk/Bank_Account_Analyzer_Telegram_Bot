import { useNavigate } from "react-router-dom"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useBudgets } from "@/hooks/useBudgets"
import type { BudgetStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

const STATUS_LABEL: Record<BudgetStatus, string> = {
  on_track: "On track",
  warning: "Warning",
  exceeded: "Exceeded",
}

const STATUS_TEXT_CLASS: Record<BudgetStatus, string> = {
  on_track: "text-success",
  warning: "text-warning",
  exceeded: "text-danger",
}

// spent_this_month is always the calendar month of today (S4-05) — unlike
// every other dashboard widget, this one deliberately ignores the
// dashboard's selected date range rather than accepting dateFrom/dateTo
// props it wouldn't actually use.
export function BudgetsWidget() {
  const { data: budgets } = useBudgets()
  const navigate = useNavigate()

  if (!budgets || budgets.length === 0) return null

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Budgets</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {budgets.map((budget) => (
            <button
              key={budget.category}
              type="button"
              onClick={() => navigate("/settings")}
              className="flex flex-col gap-2 rounded-lg border border-border p-3 text-left transition-colors hover:bg-muted"
            >
              <span className="truncate text-sm font-medium text-text-primary">{budget.category}</span>
              <Progress value={budget.percentage_used} status={budget.status} className="h-1.5" />
              <span className={cn("text-xs font-medium", STATUS_TEXT_CLASS[budget.status])}>
                {STATUS_LABEL[budget.status]}
              </span>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
