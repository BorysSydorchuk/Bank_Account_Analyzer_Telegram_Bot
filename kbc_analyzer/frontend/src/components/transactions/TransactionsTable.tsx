import { format, parseISO } from "date-fns"

import { formatAmount } from "@/lib/format"
import type { TransactionItem } from "@/lib/types"
import { cn } from "@/lib/utils"
import { CategoryPill } from "./CategoryPill"

interface TransactionsTableProps {
  transactions: TransactionItem[]
  colorByCategory: Map<string, string>
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

export function TransactionsTable({ transactions, colorByCategory }: TransactionsTableProps) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-text-secondary">
          <th className="py-2 pr-4 font-medium">Date</th>
          <th className="py-2 pr-4 font-medium">Description</th>
          <th className="py-2 pr-4 font-medium">Category</th>
          <th className="py-2 pl-4 text-right font-medium">Amount</th>
        </tr>
      </thead>
      <tbody>
        {transactions.map((t) => (
          <tr key={t.id} className="border-b border-border last:border-0">
            <td className="py-2.5 pr-4 whitespace-nowrap text-text-secondary">
              {t.booking_date ? format(parseISO(t.booking_date), "d MMM yyyy") : "—"}
            </td>
            <td className="py-2.5 pr-4 text-text-primary" title={t.description ?? undefined}>
              {truncate(t.description ?? "—", 35)}
            </td>
            <td className="py-2.5 pr-4">
              <CategoryPill
                category={t.category}
                color={t.category ? colorByCategory.get(t.category) : undefined}
              />
            </td>
            <td className={cn("py-2.5 pl-4 text-right font-medium", t.amount < 0 ? "text-danger" : "text-success")}>
              {formatAmount(t.amount)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
