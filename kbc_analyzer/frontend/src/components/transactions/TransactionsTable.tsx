import { useState } from "react"

import { usePatchTransaction } from "@/hooks/usePatchTransaction"
import type { Category, PatchTransactionRequest, TransactionItem } from "@/lib/types"
import { EditableTransactionRow } from "./EditableTransactionRow"

interface TransactionsTableProps {
  transactions: TransactionItem[]
  colorByCategory: Map<string, string>
  categories: Category[]
}

export function TransactionsTable({ transactions, colorByCategory, categories }: TransactionsTableProps) {
  // Only one row edits at a time, so this lives here rather than being
  // threaded down from TransactionsPage — nothing outside the table needs
  // to know which row, if any, is mid-edit.
  const [editingId, setEditingId] = useState<string | null>(null)
  const patchMutation = usePatchTransaction()

  function save(id: string, updates: PatchTransactionRequest) {
    patchMutation.mutate({ id, updates }, { onSuccess: () => setEditingId(null) })
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-text-secondary">
          <th className="py-2 pr-4 font-medium">Date</th>
          <th className="py-2 pr-4 font-medium">Description</th>
          <th className="py-2 pr-4 font-medium">Category</th>
          <th className="py-2 pl-4 text-right font-medium">Amount</th>
          <th className="w-8"></th>
        </tr>
      </thead>
      <tbody>
        {transactions.map((t) => (
          <EditableTransactionRow
            key={t.id}
            transaction={t}
            color={t.category ? colorByCategory.get(t.category) : undefined}
            categories={categories}
            isEditing={editingId === t.id}
            isSaving={patchMutation.isPending && editingId === t.id}
            onStartEdit={() => setEditingId(t.id)}
            onCancelEdit={() => setEditingId(null)}
            onSave={(updates) => save(t.id, updates)}
          />
        ))}
      </tbody>
    </table>
  )
}
