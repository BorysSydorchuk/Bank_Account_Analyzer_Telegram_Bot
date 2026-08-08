import { useState } from "react"
import { ChevronDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { Category } from "@/lib/types"

interface CategoryEditDropdownProps {
  categories: Category[]
  value: string | null
  onChange: (next: string | null) => void
}

// Single-select sibling of CategoryFilterDropdown's multi-select — same
// Popover shell, but each option carries the category's real color swatch
// (S3-05's own acceptance criterion) rather than a plain checkbox, since
// this picks the transaction's actual category rather than filtering by one.
export function CategoryEditDropdown({ categories, value, onChange }: CategoryEditDropdownProps) {
  const [open, setOpen] = useState(false)
  const selected = categories.find((c) => c.name === value)

  function choose(name: string | null) {
    onChange(name)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 w-full justify-between gap-1.5 font-normal">
          <span className="flex min-w-0 items-center gap-1.5">
            <span
              className="size-2.5 shrink-0 rounded-full border border-border"
              style={{ backgroundColor: selected?.color }}
            />
            <span className="truncate">{selected?.name ?? "Uncategorized"}</span>
          </span>
          <ChevronDown className="size-3.5 shrink-0 text-text-secondary" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="max-h-64 w-56 overflow-y-auto p-1" align="start">
        <button
          type="button"
          onClick={() => choose(null)}
          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
        >
          <span className="size-2.5 shrink-0 rounded-full border border-border" />
          <span className="truncate text-text-secondary">Uncategorized</span>
        </button>
        {categories.map((category) => (
          <button
            key={category.name}
            type="button"
            onClick={() => choose(category.name)}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
          >
            <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: category.color }} />
            <span className="truncate">{category.name}</span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
