import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, patchTransaction } from "@/lib/api"
import type { PatchTransactionRequest, TransactionItem, TransactionsListResponse } from "@/lib/types"

interface PatchArgs {
  id: string
  updates: PatchTransactionRequest
}

// Updates whichever cached transactionsList page(s) currently hold this row
// directly (S3-05's own requirement) — no refetch, since the edit already
// tells us exactly what changed and a refetch would just re-fetch the same
// page for no reason.
export function usePatchTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, updates }: PatchArgs) => patchTransaction(id, updates),
    onSuccess: (updated: TransactionItem) => {
      queryClient.setQueriesData<TransactionsListResponse>({ queryKey: ["transactionsList"] }, (old) => {
        if (!old) return old
        return { ...old, transactions: old.transactions.map((t) => (t.id === updated.id ? updated : t)) }
      })
      // A re-categorized row changes each of these too — unlike the list
      // above, there's no cheap local patch for a total or a category count,
      // so these are invalidated rather than hand-updated. Without this
      // (S3-08 fix), the Transactions filter dropdown and the dashboard donut
      // chart kept showing whatever they'd already fetched before the edit
      // until the next full page load.
      queryClient.invalidateQueries({ queryKey: ["statistics"] })
      queryClient.invalidateQueries({ queryKey: ["categoryOptions"] })
      toast.success("Transaction updated")
    },
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Could not update this transaction.")
    },
  })
}
