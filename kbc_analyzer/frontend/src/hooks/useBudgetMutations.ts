import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, createBudget, deleteBudget, patchBudgetAmount } from "@/lib/api"
import { budgetsKey } from "./useBudgets"

// All three mutations touch the same budgets list, read by both the Settings
// section and the dashboard widget — invalidating is enough to keep both in
// sync, same reasoning as useCategoryMutations.
function useInvalidateBudgets() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: budgetsKey })
}

export function useCreateBudget() {
  const invalidate = useInvalidateBudgets()
  return useMutation({
    mutationFn: ({ category, amount }: { category: string; amount: number }) => createBudget(category, amount),
    onSuccess: invalidate,
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Could not create this budget.")
    },
  })
}

export function usePatchBudgetAmount() {
  const invalidate = useInvalidateBudgets()
  return useMutation({
    mutationFn: ({ category, amount }: { category: string; amount: number }) => patchBudgetAmount(category, amount),
    onSuccess: invalidate,
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Could not update this budget.")
    },
  })
}

export function useDeleteBudget() {
  const invalidate = useInvalidateBudgets()
  return useMutation({
    mutationFn: (category: string) => deleteBudget(category),
    onSuccess: invalidate,
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Could not delete this budget.")
    },
  })
}
