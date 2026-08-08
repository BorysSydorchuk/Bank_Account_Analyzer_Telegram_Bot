import { useMutation, useQueryClient } from "@tanstack/react-query"

import { createCategory, patchCategoryColor, resetCategoryColor } from "@/lib/api"
import { categoriesKey } from "./useCategories"

// All three mutations touch the same categories list, and every consumer of
// it (the donut chart, transaction pills, the manual editor's dropdown) is a
// normal auto-fetching query — invalidating is enough to propagate a color
// change everywhere at once, no manual cache surgery needed.
function useInvalidateCategories() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: categoriesKey })
}

export function usePatchCategoryColor() {
  const invalidate = useInvalidateCategories()
  return useMutation({
    mutationFn: ({ name, color }: { name: string; color: string }) => patchCategoryColor(name, color),
    onSuccess: invalidate,
  })
}

export function useCreateCategory() {
  const invalidate = useInvalidateCategories()
  return useMutation({
    mutationFn: ({ name, color }: { name: string; color: string }) => createCategory(name, color),
    onSuccess: invalidate,
  })
}

export function useResetCategoryColor() {
  const invalidate = useInvalidateCategories()
  return useMutation({
    mutationFn: (name: string) => resetCategoryColor(name),
    onSuccess: invalidate,
  })
}
