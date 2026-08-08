import { useState } from "react"
import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useCategories } from "@/hooks/useCategories"
import { useCreateCategory, usePatchCategoryColor, useResetCategoryColor } from "@/hooks/useCategoryMutations"
import type { Category } from "@/lib/types"
import { CategoryColorPicker } from "./CategoryColorPicker"

const DEFAULT_NEW_CATEGORY_COLOR = "#64748B"

function sourceBadgeLabel(source: Category["source"]) {
  if (source === "ai") return "AI"
  if (source === "user") return "You"
  return "Default"
}

export function CategoriesSection() {
  const { data: categories } = useCategories()
  const patchMutation = usePatchCategoryColor()
  const resetMutation = useResetCategoryColor()
  const createMutation = useCreateCategory()
  const [isAdding, setIsAdding] = useState(false)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">Categories</CardTitle>
        <p className="text-xs text-text-secondary">AI-assigned colors · click any swatch to override</p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {(categories ?? []).map((category) => (
            <CategoryCard
              key={category.name}
              category={category}
              onSaveColor={(color) => patchMutation.mutateAsync({ name: category.name, color })}
              onReset={() => resetMutation.mutate(category.name)}
              isResetting={resetMutation.isPending && resetMutation.variables === category.name}
            />
          ))}

          {isAdding ? (
            <AddCategoryCard
              onCancel={() => setIsAdding(false)}
              onCreate={(name, color) => createMutation.mutateAsync({ name, color })}
              onCreated={() => setIsAdding(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-border p-4 text-sm text-text-secondary hover:bg-muted"
            >
              <Plus className="size-4" />
              Add category
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

interface CategoryCardProps {
  category: Category
  onSaveColor: (color: string) => Promise<unknown>
  onReset: () => void
  isResetting: boolean
}

function CategoryCard({ category, onSaveColor, onReset, isResetting }: CategoryCardProps) {
  // Only offered when there's something concrete to go back to — a category
  // the AI never colored (a brand-new custom one) has no ai_color at all.
  const canReset = category.source === "user" && category.ai_color !== null

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border p-3">
      <CategoryColorPicker color={category.color} onSave={onSaveColor}>
        <button
          type="button"
          className="size-10 shrink-0 rounded-full border border-border transition-transform hover:scale-105"
          style={{ backgroundColor: category.color }}
          aria-label={`Change color for ${category.name}`}
        />
      </CategoryColorPicker>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="truncate text-sm font-medium text-text-primary">{category.name}</span>
        <div className="flex items-center gap-2">
          <span className="inline-flex w-fit items-center rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-text-secondary">
            {sourceBadgeLabel(category.source)}
          </span>
          {canReset && (
            <button
              type="button"
              onClick={onReset}
              disabled={isResetting}
              className="text-[11px] text-primary hover:underline disabled:opacity-50"
            >
              {isResetting ? "Resetting…" : "Reset to AI"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function AddCategoryCard({
  onCancel,
  onCreate,
  onCreated,
}: {
  onCancel: () => void
  onCreate: (name: string, color: string) => Promise<unknown>
  onCreated: () => void
}) {
  const [name, setName] = useState("")

  return (
    <div className="flex items-center gap-2 rounded-lg border border-dashed border-border p-3">
      <CategoryColorPicker
        color={DEFAULT_NEW_CATEGORY_COLOR}
        saveLabel="Add"
        onSave={(color) => onCreate(name.trim(), color).then(onCreated)}
      >
        <button
          type="button"
          disabled={!name.trim()}
          className="size-10 shrink-0 rounded-full border border-border disabled:cursor-not-allowed disabled:opacity-40"
          style={{ backgroundColor: DEFAULT_NEW_CATEGORY_COLOR }}
          aria-label="Pick a color for the new category"
        />
      </CategoryColorPicker>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Category name..."
        className="h-9 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <Button variant="outline" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  )
}
