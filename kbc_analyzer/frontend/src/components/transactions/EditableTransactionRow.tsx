import { useState } from "react"
import { format, parseISO } from "date-fns"
import { Check, Pencil, X } from "lucide-react"

import { formatAmount } from "@/lib/format"
import { SUBCATEGORIES_BY_CATEGORY } from "@/lib/subcategories"
import type { Category, PatchTransactionRequest, TransactionItem } from "@/lib/types"
import { cn } from "@/lib/utils"
import { CategoryEditDropdown } from "./CategoryEditDropdown"
import { CategoryPill } from "./CategoryPill"

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

interface EditableTransactionRowProps {
  transaction: TransactionItem
  color: string | undefined
  categories: Category[]
  isEditing: boolean
  isSaving: boolean
  onStartEdit: () => void
  onCancelEdit: () => void
  onSave: (updates: PatchTransactionRequest) => void
}

// Inline instead of a modal — see the S3-05 WHEN DONE explanation, but in
// short: a modal disconnects the field being corrected from the row it
// belongs to (amount, date, existing category all scroll out of view behind
// it), and one-transaction-at-a-time is the normal editing pattern here, so
// there's no need for a modal's exclusive-focus behavior either.
export function EditableTransactionRow({
  transaction,
  color,
  categories,
  isEditing,
  isSaving,
  onStartEdit,
  onCancelEdit,
  onSave,
}: EditableTransactionRowProps) {
  const [description, setDescription] = useState(transaction.description ?? "")
  const [category, setCategory] = useState<string | null>(transaction.category)
  const [subcategory, setSubcategory] = useState<string | null>(transaction.subcategory)

  const subcategoryOptions = category ? SUBCATEGORIES_BY_CATEGORY[category] : undefined

  function startEdit() {
    setDescription(transaction.description ?? "")
    setCategory(transaction.category)
    setSubcategory(transaction.subcategory)
    onStartEdit()
  }

  function changeCategory(next: string | null) {
    setCategory(next)
    // A subcategory only makes sense under Other/Traveling — switching away
    // from either has to clear it, or a stale subcategory from the old
    // category could get saved silently alongside the new one.
    if (!next || !SUBCATEGORIES_BY_CATEGORY[next]) {
      setSubcategory(null)
    }
  }

  function save() {
    onSave({ category, subcategory, description })
  }

  if (!isEditing) {
    return (
      <tr className="group border-b border-border last:border-0">
        <td className="py-2.5 pr-4 whitespace-nowrap text-text-secondary">
          {transaction.booking_date ? format(parseISO(transaction.booking_date), "d MMM yyyy") : "—"}
        </td>
        <td className="py-2.5 pr-4 text-text-primary" title={transaction.description ?? undefined}>
          {truncate(transaction.description ?? "—", 35)}
        </td>
        <td className="py-2.5 pr-4">
          <CategoryPill category={transaction.category} color={color} manuallyEdited={transaction.manually_edited} />
        </td>
        <td
          className={cn("py-2.5 pl-4 text-right font-medium", transaction.amount < 0 ? "text-danger" : "text-success")}
        >
          {formatAmount(transaction.amount)}
        </td>
        <td className="w-8 py-2.5 pl-2">
          <button
            type="button"
            onClick={startEdit}
            aria-label="Edit transaction"
            className="rounded p-1 text-text-secondary opacity-0 hover:bg-muted hover:text-text-primary group-hover:opacity-100"
          >
            <Pencil className="size-3.5" />
          </button>
        </td>
      </tr>
    )
  }

  return (
    <tr className="border-b border-border bg-muted/40 last:border-0">
      <td className="py-2.5 pr-4 align-top whitespace-nowrap text-text-secondary">
        {transaction.booking_date ? format(parseISO(transaction.booking_date), "d MMM yyyy") : "—"}
      </td>
      <td className="py-2 pr-4 align-top">
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="h-8 w-full rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </td>
      <td className="py-2 pr-4 align-top">
        <div className="flex flex-col gap-1.5">
          <CategoryEditDropdown categories={categories} value={category} onChange={changeCategory} />
          {subcategoryOptions && (
            <select
              value={subcategory ?? ""}
              onChange={(e) => setSubcategory(e.target.value || null)}
              className="h-8 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">No subcategory</option>
              {subcategoryOptions.map((sub) => (
                <option key={sub} value={sub}>
                  {sub}
                </option>
              ))}
            </select>
          )}
        </div>
      </td>
      <td
        className={cn(
          "py-2.5 pl-4 text-right align-top font-medium",
          transaction.amount < 0 ? "text-danger" : "text-success"
        )}
      >
        {formatAmount(transaction.amount)}
      </td>
      <td className="w-16 py-2.5 pl-2 align-top">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={save}
            disabled={isSaving}
            aria-label="Save"
            className="rounded p-1 text-success hover:bg-muted disabled:opacity-50"
          >
            <Check className="size-4" />
          </button>
          <button
            type="button"
            onClick={onCancelEdit}
            disabled={isSaving}
            aria-label="Cancel"
            className="rounded p-1 text-text-secondary hover:bg-muted disabled:opacity-50"
          >
            <X className="size-4" />
          </button>
        </div>
      </td>
    </tr>
  )
}
