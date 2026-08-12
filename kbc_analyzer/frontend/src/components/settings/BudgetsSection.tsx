import { useState } from "react"
import { Pencil, Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useBudgets } from "@/hooks/useBudgets"
import { useCreateBudget, useDeleteBudget, usePatchBudgetAmount } from "@/hooks/useBudgetMutations"
import { useCategories } from "@/hooks/useCategories"
import type { Budget, BudgetStatus, Category } from "@/lib/types"

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

function formatEuro(amount: number) {
  return `€${amount.toFixed(2)}`
}

export function BudgetsSection() {
  const { data: budgets } = useBudgets()
  const { data: categories } = useCategories()
  const createMutation = useCreateBudget()
  const patchMutation = usePatchBudgetAmount()
  const deleteMutation = useDeleteBudget()
  const [isAdding, setIsAdding] = useState(false)

  const colorByCategory = new Map((categories ?? []).map((c) => [c.name, c.color]))
  const budgetedCategories = new Set((budgets ?? []).map((b) => b.category))
  const availableCategories = (categories ?? []).filter((c) => !budgetedCategories.has(c.name))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Budgets</CardTitle>
        <p className="text-xs text-text-secondary">Monthly spending limits per category</p>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          {(budgets ?? []).map((budget) => (
            <BudgetCard
              key={budget.category}
              budget={budget}
              color={colorByCategory.get(budget.category) ?? "#94A3B8"}
              onSaveAmount={(amount) => patchMutation.mutateAsync({ category: budget.category, amount })}
              onDelete={() => deleteMutation.mutate(budget.category)}
              isSaving={patchMutation.isPending && patchMutation.variables?.category === budget.category}
              isDeleting={deleteMutation.isPending && deleteMutation.variables === budget.category}
            />
          ))}

          {isAdding ? (
            <AddBudgetForm
              categories={availableCategories}
              onCancel={() => setIsAdding(false)}
              onCreate={(category, amount) => createMutation.mutateAsync({ category, amount })}
              onCreated={() => setIsAdding(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              disabled={availableCategories.length === 0}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-border p-3 text-sm text-text-secondary hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="size-4" />
              {availableCategories.length === 0 ? "Every category already has a budget" : "Set budget"}
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

interface BudgetCardProps {
  budget: Budget
  color: string
  onSaveAmount: (amount: number) => Promise<unknown>
  onDelete: () => void
  isSaving: boolean
  isDeleting: boolean
}

function BudgetCard({ budget, color, onSaveAmount, onDelete, isSaving, isDeleting }: BudgetCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [amount, setAmount] = useState(String(budget.amount))

  const save = async () => {
    const parsed = Number(amount)
    if (!(parsed > 0)) return
    await onSaveAmount(parsed)
    setIsEditing(false)
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center gap-2">
        <span className="size-3 shrink-0 rounded-full" style={{ backgroundColor: color }} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">{budget.category}</span>
        <button
          type="button"
          onClick={() => setIsEditing((v) => !v)}
          aria-label={`Edit budget for ${budget.category}`}
          className="rounded p-1 text-text-secondary hover:bg-muted hover:text-text-primary"
        >
          <Pencil className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={isDeleting}
          aria-label={`Delete budget for ${budget.category}`}
          className="rounded p-1 text-text-secondary hover:bg-muted hover:text-danger disabled:opacity-50"
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>

      {isEditing ? (
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
          <Button size="sm" disabled={isSaving} onClick={save}>
            {isSaving ? "Saving…" : "Save"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <>
          <Progress value={budget.percentage_used} status={budget.status} />
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>
              {formatEuro(budget.spent_this_month)} spent of {formatEuro(budget.amount)}
            </span>
            <span className={STATUS_TEXT_CLASS[budget.status]}>{STATUS_LABEL[budget.status]}</span>
          </div>
        </>
      )}
    </div>
  )
}

function AddBudgetForm({
  categories,
  onCancel,
  onCreate,
  onCreated,
}: {
  categories: Category[]
  onCancel: () => void
  onCreate: (category: string, amount: number) => Promise<unknown>
  onCreated: () => void
}) {
  const [category, setCategory] = useState(categories[0]?.name ?? "")
  const [amount, setAmount] = useState("")

  const parsedAmount = Number(amount)
  const canSave = category !== "" && parsedAmount > 0

  const save = async () => {
    if (!canSave) return
    await onCreate(category, parsedAmount)
    onCreated()
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-dashed border-border p-3">
      <select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        className="h-9 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {categories.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
      <input
        type="number"
        min="0.01"
        step="0.01"
        placeholder="Amount"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="h-9 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <Button size="sm" disabled={!canSave} onClick={save}>
        Save
      </Button>
      <Button variant="outline" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  )
}
